#!/usr/bin/env python3
"""Jul 21 compliant HF corpus → Modal T4 GPU extraction → local graph rebuild.

Meeting rules:
  - Books: index / TOC / structure metadata only (no chapter body)
  - Papers: full text allowed (priority content)
  - Source: Prataykarali/archipelago-books-cs (local mirror under
    pdfs/archipelago-books-cs/) + open-access pilot papers under pdfs/papers/

GPU: Modal app `okf-extract` (T4). Local NVIDIA is currently in an NVML error
state (nvidia-smi fails); Modal is the reliable GPU path.

Usage:
    python scripts/run_hf_compliant_gpu_ingest.py
    python scripts/run_hf_compliant_gpu_ingest.py --shards 4
    python scripts/run_hf_compliant_gpu_ingest.py --skip-extract   # reuse raw file
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

CHUNKS_OUT = BASE / "pilot_corpus" / "_compliant_chunks.json"
RAW_OUT = BASE / "okf_raw_outputs.compliant.json"
DB_PATH = BASE / "okf_graph.db"


def build_corpus() -> list:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_compliant_corpus",
        BASE / "scripts" / "build_compliant_corpus.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Full paper chunks from OA + HF; all index/TOC + structure for books.
    mod.build(
        str(CHUNKS_OUT),
        max_oa_chunks_per_paper=999,
        max_structure_chunks=200,
    )
    chunks = json.load(open(CHUNKS_OUT))
    # Modal extract requires "text"
    fixed = 0
    for c in chunks:
        if not c.get("text") and c.get("text_passage"):
            c["text"] = c["text_passage"]
            fixed += 1
        if not c.get("chunk_id"):
            c["chunk_id"] = f"auto_{fixed}"
    if fixed:
        json.dump(chunks, open(CHUNKS_OUT, "w"), indent=1)
        print(f"  normalized text field on {fixed} chunks")
    return chunks


def verify_guidelines(chunks: list) -> None:
    bad = []
    for c in chunks:
        did = c.get("doc_id") or ""
        if did.startswith("papers/"):
            continue
        stem = did.lower()
        sec = (c.get("section_title") or "").strip().lower()
        cid = (c.get("chunk_id") or "").lower()
        if "structure" in cid or sec in (
            "index", "contents", "table of contents", "contents (structure metadata)"
        ):
            continue
        if any(k in stem for k in ("index", "content", "toc")):
            continue
        bad.append(did)
    if bad:
        raise SystemExit(f"GUIDELINE VIOLATION: {len(bad)} body book chunks: {bad[:5]}")
    books = {c["doc_id"].split("/")[0] for c in chunks if not c["doc_id"].startswith("papers/")}
    papers = {c["doc_id"] for c in chunks if c["doc_id"].startswith("papers/")}
    print(f"  guidelines OK — book folders={len(books)} (metadata only), papers={len(papers)}")


def modal_extract(chunks: list, shards: int) -> list:
    print(f"\n[GPU] Modal T4 extraction: {len(chunks)} chunks, {shards} shards")
    import modal
    extract_fn = modal.Function.from_name("okf-extract", "extract_chunks")
    # Fan out
    shard_lists = [chunks[i::shards] for i in range(shards)]
    # Drop empty shards
    shard_lists = [s for s in shard_lists if s]
    t0 = time.time()
    merged = []
    for part in extract_fn.map(shard_lists):
        merged.extend(part)
        print(f"  received shard batch, total raw records so far: {len(merged)}", flush=True)
    print(f"  Modal done: {len(merged)} records in {(time.time()-t0)/60:.1f} min")
    json.dump(merged, open(RAW_OUT, "w"))
    print(f"  saved {RAW_OUT}")
    return merged


def parse_and_build(raw: list, chunks: list) -> None:
    from okf.extraction import _extract_json_payload, normalize_okf_item
    from okf.pipeline import finalize_and_build
    from catalog_bridge import auto_link_resources, generate_coverage_report

    by_key = {(c["doc_id"], str(c.get("chunk_id"))): c for c in chunks}
    results, parsed_ok, empty, failed = [], 0, 0, 0
    for rec in raw:
        key = (rec.get("doc_id"), str(rec.get("chunk_id")))
        chunk = by_key.get(key, {})
        raw_text = rec.get("raw_response") or ""
        try:
            payload = _extract_json_payload(raw_text)
            data = json.loads(payload) if payload else []
        except Exception:
            failed += 1
            continue
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not data:
            empty += 1
            continue
        parsed_ok += 1
        passage = (chunk.get("text") or chunk.get("text_passage") or "")[:1600]
        for item in data[:5]:
            norm = normalize_okf_item(
                item,
                doc_id=rec.get("doc_id", ""),
                chunk_id=str(rec.get("chunk_id", "")),
                page_number=rec.get("page_number", 0) or 0,
                section_title=rec.get("section_title", "") or "",
                doc_hash=rec.get("doc_hash"),
                page_count=rec.get("page_count"),
                doc_title=rec.get("doc_title"),
                edition=rec.get("edition"),
                page_label_map=chunk.get("page_label_map"),
            )
            if norm:
                norm["source_passage"] = passage
                results.append(norm)

    print(f"\n[parse] chunks={len(raw)} parsed={parsed_ok} empty={empty} fail={failed}")
    print(f"  concept records: {len(results)}")
    if not results:
        raise SystemExit("No concepts parsed — aborting graph rebuild")

    finalize_and_build(
        results,
        total_chunks=len(raw),
        successful_chunk_count=parsed_ok,
        chunks=chunks,
    )

    print("\n[bridge] Resource ↔ Document ...")
    stats = auto_link_resources(str(DB_PATH))
    print("  ", stats)
    print("  ", generate_coverage_report(str(DB_PATH)))

    # Graph summary
    import kuzu
    db = kuzu.Database(str(DB_PATH), read_only=True)
    conn = kuzu.Connection(db)
    print("\n[verify] counts:")
    for t in ("Document", "Chunk", "Concept", "Subject", "Resource", "JournalIssue"):
        n = conn.execute(f"MATCH (n:{t}) RETURN count(n)").get_next()[0]
        print(f"  {t:16s} {n}")
    for t in ("HAS_CHUNK", "MENTIONS", "PROVIDES_TEXT", "CATEGORIZES"):
        n = conn.execute(f"MATCH ()-[r:{t}]->() RETURN count(r)").get_next()[0]
        print(f"  {t:16s} {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", type=int, default=4)
    ap.add_argument("--skip-extract", action="store_true",
                    help=f"Reuse existing {RAW_OUT.name}")
    ap.add_argument("--skip-build-corpus", action="store_true")
    args = ap.parse_args()

    print("=" * 70)
    print("  HF compliant GPU ingest (Modal T4)")
    print("  Jul 21: books=index/TOC only, papers=full text")
    print("=" * 70)

    if args.skip_build_corpus and CHUNKS_OUT.exists():
        chunks = json.load(open(CHUNKS_OUT))
        print(f"  reusing corpus {len(chunks)} chunks")
    else:
        chunks = build_corpus()
    verify_guidelines(chunks)

    if args.skip_extract and RAW_OUT.exists():
        raw = json.load(open(RAW_OUT))
        print(f"  reusing raw {len(raw)} records from {RAW_OUT}")
    else:
        raw = modal_extract(chunks, shards=args.shards)

    parse_and_build(raw, chunks)
    print("\nDONE — compliant pilot graph ready")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Jul 21 2026 pilot-compliant ingestion end-to-end.

1. Loads pilot_corpus/_compliant_chunks.json
   - books: index / TOC / structure metadata only (no body text)
   - papers: full text (approved priority content)
2. Extracts concepts via Ollama (or local model)
3. finalize_and_build → rebuilds concept graph (catalog tables preserved)
4. Re-links Resource↔Document via catalog_bridge.auto_link_resources
5. Prints verification summary

Usage:
    python scripts/run_compliant_pilot_ingest.py [--ollama] [--limit N]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

CHUNKS = BASE / "pilot_corpus" / "_compliant_chunks.json"
DB_PATH = BASE / "okf_graph.db"


def verify_guidelines(chunks: list) -> None:
    """Fail fast if book body text slipped into the compliant set."""
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
        raise SystemExit(
            f"GUIDELINE VIOLATION: {len(bad)} non-metadata book chunks in corpus "
            f"(sample: {bad[:3]})"
        )
    papers = {c["doc_id"] for c in chunks if c["doc_id"].startswith("papers/")}
    books = {c["doc_id"].split("/")[0] for c in chunks if not c["doc_id"].startswith("papers/")}
    print(f"  guideline check OK — books={len(books)} (metadata only), papers={len(papers)}")


def rebridge_catalog() -> dict:
    from catalog_bridge import auto_link_resources, generate_coverage_report
    print("\n[bridge] Re-linking Resource ↔ Document (PROVIDES_TEXT)...")
    stats = auto_link_resources(str(DB_PATH))
    report = generate_coverage_report(str(DB_PATH))
    print(f"  auto_link stats: {stats}")
    print(f"  coverage: {report}")
    return stats


def print_graph_summary() -> None:
    import kuzu
    db = kuzu.Database(str(DB_PATH), read_only=True)
    conn = kuzu.Connection(db)
    print("\n[verify] Graph counts after ingest:")
    for t in ("Document", "Chunk", "Concept", "Subject", "Resource", "JournalIssue"):
        n = conn.execute(f"MATCH (n:{t}) RETURN count(n)").get_next()[0]
        print(f"  {t:16s} {n}")
    for t in ("HAS_CHUNK", "MENTIONS", "PROVIDES_TEXT", "CATEGORIZES", "HAS_ISSUE",
              "REQUIRES", "UNLOCKS", "RELATED"):
        n = conn.execute(f"MATCH ()-[r:{t}]->() RETURN count(r)").get_next()[0]
        print(f"  {t:16s} {n}")
    # sample page-view query
    r = conn.execute("""
        MATCH (chk:Chunk)<-[:HAS_CHUNK]-(d:Document)
        OPTIONAL MATCH (res:Resource)-[p:PROVIDES_TEXT]->(d)
        RETURN d.id, chk.page_number, d.pdf_url, p.pdf_url
        LIMIT 1
    """)
    if r.has_next():
        print("  page-view sample row:", r.get_next())


def main():
    use_ollama = "--ollama" in sys.argv or True  # default ollama (no CUDA here)
    if "--local" in sys.argv:
        use_ollama = False
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    print("=" * 70)
    print("  Jul 21 pilot-compliant ingestion")
    print("=" * 70)

    chunks = json.load(open(CHUNKS))
    if limit:
        chunks = chunks[:limit]
    print(f"  chunks: {len(chunks)} from {CHUNKS}")
    verify_guidelines(chunks)

    import okf.extraction as ex
    from okf.pipeline import finalize_and_build

    if use_ollama:
        ex.LOCAL_MODE = False
        print(f"  extraction mode: Ollama ({ex.MODEL_NAME if hasattr(ex,'MODEL_NAME') else 'qwen3.5:0.8b'})")
    else:
        ex.load_local_model()
        if not ex.is_model_loaded():
            print("  local model failed — falling back to Ollama")
            ex.LOCAL_MODE = False
        else:
            print("  extraction mode: local PyTorch")

    t0 = time.time()
    results, ok = ex.extract_chunks_with_model(chunks)
    dt = time.time() - t0
    print(f"\n  extracted {len(results)} concept records from {ok}/{len(chunks)} chunks "
          f"in {dt/60:.1f} min")

    # Save intermediate so a crash in finalize is recoverable
    mid = BASE / "okf_results.compliant_raw.json"
    with open(mid, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  wrote intermediate {mid.name}")

    finalize_and_build(
        results,
        total_chunks=len(chunks),
        successful_chunk_count=ok,
        chunks=chunks,
    )

    rebridge_catalog()
    print_graph_summary()
    print("\nINGESTION COMPLETE (compliant pilot graph ready)")
    print("=" * 70)


if __name__ == "__main__":
    main()

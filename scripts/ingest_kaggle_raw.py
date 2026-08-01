#!/usr/bin/env python3
"""Merge Kaggle GPU raw extractions back into the local OKF pipeline.

The Kaggle kernel (okf-extract-gpu) runs ONLY the SLM generation step and
saves raw model text per chunk to okf_raw_outputs.json. This script does
everything the local pipeline would have done after generation: JSON payload
parsing, normalize_okf_item, source_passage attachment, cleanup/canonicalize,
relation filtering, save to okf_results.json and Kùzu graph rebuild.

Usage:
    python scripts/ingest_kaggle_raw.py /path/to/okf_raw_outputs.json
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from okf.extraction import _extract_json_payload, normalize_okf_item
from okf.pipeline import finalize_and_build


def main(raw_path: str):
    raw = json.load(open(raw_path))
    chunks_path = BASE / "pdfs" / "archipelago-books-cs" / "_pdf_chunks.json"
    chunks = {(c["doc_id"], c["chunk_id"]): c for c in json.load(open(chunks_path))}

    results, parsed_ok, empty, failed = [], 0, 0, 0
    for rec in raw:
        key = (rec["doc_id"], rec["chunk_id"])
        chunk = chunks.get(key, {})
        try:
            data = json.loads(_extract_json_payload(rec["raw_response"]))
        except Exception:
            failed += 1
            continue
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not data:
            empty += 1
            continue
        parsed_ok += 1
        passage = (chunk.get("text") or "")[:1600]
        for item in data[:5]:
            norm = normalize_okf_item(
                item,
                doc_id=rec["doc_id"],
                chunk_id=rec["chunk_id"],
                page_number=rec.get("page_number", 0),
                section_title=rec.get("section_title", ""),
                doc_hash=rec.get("doc_hash"),
                page_count=rec.get("page_count"),
                doc_title=rec.get("doc_title"),
                edition=rec.get("edition"),
                page_label_map=chunk.get("page_label_map"),
            )
            if norm:
                norm["source_passage"] = passage
                results.append(norm)

    print(f"chunks: {len(raw)}  parsed: {parsed_ok}  empty: {empty}  unparseable: {failed}")
    print(f"raw concept records: {len(results)}")

    # finalize_and_build runs clean_pipeline + filter_extracted_relations +
    # canonicalization + Kùzu build when given the chunks.
    finalize_and_build(results, total_chunks=len(raw),
                       successful_chunk_count=parsed_ok,
                       chunks=list(chunks.values()))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])

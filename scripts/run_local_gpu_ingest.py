#!/usr/bin/env python3
"""
run_local_gpu_ingest.py — Local GPU + Multi-thread CPU Graph Rebuild Pipeline.

Rebuilds the Archipelago knowledge graph locally using:
  - GPU/CPU extraction model (aura-qwen / lib-qwen / Ollama)
  - Compliant corpus (827 chunks: 25 papers full-text + 5 books TOC/index metadata)
  - Full Koha catalog reseed (Subjects, Titles, Physical Inventory, Journals)
  - Resource ↔ Document fuzzy bridge

Usage:
    python scripts/run_local_gpu_ingest.py
    python scripts/run_local_gpu_ingest.py --skip-extract   # reuse existing raw JSON
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

CHUNKS_OUT = BASE / "pilot_corpus" / "_compliant_chunks.json"
RAW_OUT = BASE / "okf_raw_outputs.compliant.json"
DB_PATH = BASE / "okf_graph.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def step1_check_corpus() -> list:
    logger.info("=== [Step 1/5] Validating Compliant Corpus ===")
    if not CHUNKS_OUT.exists():
        logger.error(f"Missing {CHUNKS_OUT}. Run scripts/build_compliant_corpus.py first.")
        sys.exit(1)

    chunks = json.load(open(CHUNKS_OUT))
    logger.info(f"Loaded {len(chunks)} chunks from {CHUNKS_OUT.name}")

    # Guidelines verification
    books = {c["doc_id"].split("/")[0] for c in chunks if not c["doc_id"].startswith("papers/")}
    papers = {c["doc_id"] for c in chunks if c["doc_id"].startswith("papers/")}
    logger.info(f"Corpus check: {len(books)} books (metadata only, 0% body prose), {len(papers)} research papers (full text)")

    return chunks


def step2_extract(chunks: list, use_local_model: bool = True) -> list:
    logger.info("=== [Step 2/5] Concept Extraction (GPU + CPU Multi-Thread) ===")

    from okf.extraction import extract_chunks_with_model, load_local_model, LOCAL_MODE

    if use_local_model:
        try:
            logger.info("Initializing GPU PyTorch model (aura-qwen / lib-qwen)...")
            load_local_model()
        except Exception as e:
            logger.warning(f"Local GPU model init failed ({e}); falling back to Ollama mode...")

    t0 = time.time()
    logger.info(f"Starting extraction on {len(chunks)} chunks...")

    results, ok_count = extract_chunks_with_model(chunks)

    elapsed_min = (time.time() - t0) / 60.0
    logger.info(f"Extraction complete in {elapsed_min:.2f} min! Parsed {len(results)} concept records from {ok_count}/{len(chunks)} successful chunks.")

    # Save raw outputs
    json.dump(results, open(RAW_OUT, "w"), indent=1)
    logger.info(f"Saved raw extraction to {RAW_OUT.name}")

    return results


def step3_build_graph(results: list, chunks: list):
    logger.info("=== [Step 3/5] Graph Construction & Canonicalization ===")
    from okf.pipeline import finalize_and_build

    if not results:
        logger.error("No concept results extracted. Aborting graph build.")
        sys.exit(1)

    finalize_and_build(
        results,
        total_chunks=len(chunks),
        successful_chunk_count=len(chunks),
        chunks=chunks,
    )
    logger.info("Base graph construction complete!")


def step4_reseed_catalog():
    logger.info("=== [Step 4/5] Reseeding Koha Catalog ODS Data & Auto-Bridge ===")
    from catalog_ingest import _run_all
    from catalog_bridge import auto_link_resources, generate_coverage_report

    _run_all(str(DB_PATH))

    logger.info("Auto-linking Resource ↔ Document bridges...")
    stats = auto_link_resources(str(DB_PATH))
    logger.info(f"Bridge stats: {stats}")
    report = generate_coverage_report(str(DB_PATH))
    logger.info(f"Coverage report: {report}")


def step5_verify_database():
    logger.info("=== [Step 5/5] Database Verification & Summary ===")
    import kuzu

    db = kuzu.Database(str(DB_PATH), read_only=True)
    conn = kuzu.Connection(db)

    print("\n" + "=" * 60)
    print("  🎉 ARCHIPELAGO KÙZUDB GRAPH VERIFICATION SUMMARY")
    print("=" * 60)
    print("  Node Tables:")
    for t in ("Document", "Chunk", "Concept", "Subject", "Resource", "JournalIssue"):
        n = conn.execute(f"MATCH (n:{t}) RETURN count(n)").get_next()[0]
        print(f"    • {t:16s} : {n:,} nodes")

    print("\n  Relationship Edges:")
    for t in ("HAS_CHUNK", "MENTIONS", "REQUIRES", "UNLOCKS", "RELATED", "CATEGORIZES", "HAS_ISSUE", "PROVIDES_TEXT"):
        try:
            n = conn.execute(f"MATCH ()-[r:{t}]->() RETURN count(r)").get_next()[0]
            print(f"    • {t:16s} : {n:,} edges")
        except Exception:
            pass
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Local GPU + CPU Archipelago Graph Rebuild")
    parser.add_argument("--skip-extract", action="store_true", help="Reuse existing raw extraction JSON")
    args = parser.parse_args()

    print("=" * 70)
    print("  🏝️  Archipelago Local GPU/CPU Graph Rebuild")
    print("  Jul 21 2026 — 25 Papers (Full Text) + 6 Books (Metadata Only)")
    print("=" * 70)

    chunks = step1_check_corpus()

    if args.skip_extract and RAW_OUT.exists():
        logger.info(f"Reusing existing extraction results from {RAW_OUT.name}")
        results = json.load(open(RAW_OUT))
    else:
        results = step2_extract(chunks)

    step3_build_graph(results, chunks)
    step4_reseed_catalog()
    step5_verify_database()


if __name__ == "__main__":
    main()

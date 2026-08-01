#!/usr/bin/env python3
"""Local ingestion of the copyright-compliant corpus with fine-tuned lib-qwen.

Loads pilot_corpus/_compliant_chunks.json (papers full-text + book index/TOC
metadata only), runs the same extraction loop the main pipeline uses, then
finalize_and_build: cleanup, canonicalization, relation filtering, save to
okf_results.json, and Kùzu graph rebuild.

Usage:
    python scripts/local_ingest_compliant.py [--ollama] [--limit N]
"""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

CHUNKS = BASE / "pilot_corpus" / "_compliant_chunks.json"


def main():
    use_ollama = "--ollama" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    import okf.extraction as ex
    from okf.pipeline import finalize_and_build

    chunks = json.load(open(CHUNKS))
    if limit:
        chunks = chunks[:limit]
    print(f"{len(chunks)} compliant chunks "
          f"({'ollama' if use_ollama else 'local pytorch'} mode)", flush=True)

    if not use_ollama:
        ex.load_local_model()
        if not ex.is_model_loaded():
            sys.exit("local model failed to load; try --ollama")
    else:
        ex.LOCAL_MODE = False

    t0 = time.time()
    results, ok = ex.extract_chunks_with_model(chunks)
    dt = time.time() - t0
    print(f"extracted {len(results)} records from {ok}/{len(chunks)} chunks "
          f"in {dt/60:.1f} min", flush=True)

    finalize_and_build(results, total_chunks=len(chunks),
                       successful_chunk_count=ok, chunks=chunks)
    print("INGESTION COMPLETE", flush=True)


if __name__ == "__main__":
    main()

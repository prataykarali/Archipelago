"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import json
import os
from collections import Counter
from okf import config, extraction
from okf.config import MODEL_NAME, _local_path, infer_source_category
from okf.extraction import extract_chunks_with_model, load_local_model
from . import _deps as _rt  # noqa: F401


def add_document(path: str, limit: int = None, evaluate_gold_path: str = None):
    """Incrementally ingest ONE document with the LOCAL model and rebuild the
    merged graph. Re-adding a doc replaces its previous entries (no duplicates).

    limit: optional cap on prose chunks processed (fast testing on CPU).
    """
    from archipelago.ingestion.pdf_io import ingest_document

    print("=" * 70)
    print("ARCHIPELAGO PIPELINE - INCREMENTAL ADD (single document)")
    print("=" * 70)

    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}")
        return

    doc_id = _rt.compute_doc_id(path)
    print(f"\n  Document: {path}")
    print(f"  doc_id:   {doc_id}")

    # ── Stage 1: Chunking (this document only) ──
    print("\n[1] STAGE 1: Section-Aware Document Chunking")
    print("-" * 50)

    chunks = ingest_document(path, max_pages=config.MAX_PAGES_PER_DOC)
    for chunk in chunks:
        chunk["doc_id"] = doc_id

    kind_counts = Counter(c.get("chunk_kind", "prose") for c in chunks)
    prose_chunks = [c for c in chunks if c.get("chunk_kind", "prose") == "prose"]
    new_chunk_total = len(prose_chunks)

    print(f"\n  Total chunks: {len(chunks)}  ->  {new_chunk_total} prose sent to SLM")
    dropped = {k: v for k, v in kind_counts.items() if k != "prose"}
    if dropped:
        print(f"  Dropped non-prose: {dropped}")

    if not prose_chunks:
        print("ERROR: No prose chunks to extract from!")
        return

    if limit is not None and limit < len(prose_chunks):
        print(f"  --limit {limit}: processing only the first {limit} prose chunks")
        prose_chunks = prose_chunks[:limit]

    # ── Stage 2: OKF v1.5 Extraction (LOCAL model preferred; fine-tuned Ollama ok) ──
    print(f"\n[2] STAGE 2: OKF v1.5 Extraction via local model: {_local_path}")
    print("-" * 50)

    if extraction.LOCAL_MODEL is None:
        load_local_model()
    if extraction.LOCAL_MODE and extraction.LOCAL_MODEL is not None:
        # Preferred path: PyTorch lib-qwen / aura-qwen loaded from disk.
        pass
    else:
        # No local PyTorch model. Ollama is acceptable ONLY when MODEL_NAME is
        # a fine-tuned extractor (lib-qwen family). Refusing all other names
        # preserves the invariant that we never extract with the untuned base
        # qwen3.5:0.8b.
        from okf.config import MODEL_NAME as _okf_model
        fine_tuned_prefixes = ("lib-qwen", "aura-qwen", "lora")
        if any(_okf_model.startswith(p) for p in fine_tuned_prefixes):
            print(
                f"  Local PyTorch model missing; using fine-tuned Ollama model "
                f"'{_okf_model}' for extraction."
            )
        else:
            print(
                "ERROR: local model unavailable and Ollama model "
                f"'{_okf_model}' is not a fine-tuned extractor — "
                "--add never falls back to the untuned base model. Aborting."
            )
            return

    new_results, new_successful = extract_chunks_with_model(prose_chunks)
    print(f"\n  Extracted: {len(new_results)} concepts from {len(prose_chunks)} chunks")

    if not new_results:
        # Every chunk failed. Proceeding would delete the doc's previous
        # entries and replace them with nothing — abort instead so a bad run
        # can never destroy existing data.
        print("ERROR: extraction produced 0 concepts — leaving existing results untouched.")
        return

    # ── Merge with existing results (replace prior entries for this doc) ──
    print("\n[2a] MERGE WITH EXISTING RESULTS")
    print("-" * 50)

    saved_file = _rt.BASE_DIR / "okf_results.json"
    existing = []
    if saved_file.exists():
        with open(saved_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
    before = len(existing)
    # Existing entries already carry page_number/section_title/source_passage;
    # leave them untouched — only this doc's records are replaced.
    existing = [r for r in existing if r.get("doc_id") != doc_id]
    replaced = before - len(existing)
    if replaced > 0:
        print(f"  Replaced {replaced} prior entries for {doc_id}")
    else:
        print(f"  No prior entries for {doc_id}")
    okf_results = existing + new_results
    print(f"  Merged total: {len(okf_results)} concepts "
          f"({len(existing)} existing + {len(new_results)} new)")

    # Chunk counts for the merged evaluation: distinct extracted chunks from the
    # kept existing results plus every prose chunk processed in this run.
    existing_chunk_count = len({
        (r.get("doc_id", ""), r.get("chunk_id", ""))
        for r in existing if r.get("chunk_id")
    })
    total_chunks = existing_chunk_count + len(prose_chunks)
    successful_chunk_count = existing_chunk_count + new_successful

    return _rt.finalize_and_build(okf_results, total_chunks, successful_chunk_count, chunks=prose_chunks, evaluate_gold_path=evaluate_gold_path)

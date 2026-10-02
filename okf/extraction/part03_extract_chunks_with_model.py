"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import sys
import time
from . import _deps as _rt  # noqa: F401


def extract_chunks_with_model(chunks: list) -> tuple[list, int]:
    """Run OKF extraction over prose chunks with per-chunk progress output.

    Returns (okf_results, successful_chunk_count). Shared by run_pipeline and
    add_document so the extraction loop stays identical in both modes.
    """
    okf_results = []
    successful_chunk_count = 0
    for i, chunk in enumerate(chunks):
        progress = f"[{i+1}/{len(chunks)}]"
        section = chunk.get("section_title", "?")[:40]
        # Skip bibliography / references chunks entirely (page-14 LoRA noise)
        try:
            from okf.cleanup_parts.directionality import is_bibliography_section
            if is_bibliography_section(chunk.get("section_title") or ""):
                print(f"  Skipping bibliography chunk {chunk.get('chunk_id')}: {section}")
                continue
        except Exception:
            pass
        print(f"  {progress} {chunk['doc_id']} | {section} (p.{chunk['page_number']})", end="")
        sys.stdout.flush()

        start_time = time.time()
        results = _rt.extract_okf_v15(
            text=chunk["text"],
            doc_id=chunk["doc_id"],
            chunk_id=chunk["chunk_id"],
            page_number=chunk["page_number"],
            section_title=chunk["section_title"],
            doc_hash=chunk.get("doc_hash"),
            page_count=chunk.get("page_count"),
            doc_title=chunk.get("doc_title"),
            edition=chunk.get("edition"),
            page_label_map=chunk.get("page_label_map"),
        )
        elapsed = time.time() - start_time

        if results:
            # Attach the original source passage so the UI can show the
            # highlighted chunk and deep-link back to the source page.
            passage = chunk["text"][:1600]
            for r in results:
                r["source_passage"] = passage
                r.setdefault("section_title", chunk.get("section_title", ""))
            okf_results.extend(results)
            successful_chunk_count += 1
            names = ", ".join(r["concept_name"] for r in results[:3])
            if len(results) > 3:
                names += f", +{len(results) - 3} more"
            print(f" -> {len(results)} concepts: {names[:70]} ({elapsed:.1f}s)")
        else:
            print(f" -> FAILED ({elapsed:.1f}s)")

    return okf_results, successful_chunk_count

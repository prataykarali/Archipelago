"""Production output hygiene: strip internal lineage + raw source dumps."""
from __future__ import annotations

import re


# Bare "p.N ↗" chips outside markdown links.
_BARE_PAGE_ARROW_RE = re.compile(r"\bp\.\d+\s*\u2197")
# Linked page chips "[p.N ↗](/api/page-view?...)" — removed whole, including
# the wrapper, while genuine "[S1](/api/page-view?...)" evidence links survive.
_LINKED_PAGE_CHIP_RE = re.compile(r"\[p\.\d+\s*\u2197\]\([^)]*\)")
# Legacy doc_id lineage brackets:
#   [doc_id: x.pdf -> chunk_006 -> page 2]
#   [Edge2024_GraphRAG.pdf: papers/Edge2024_GraphRAG.pdf_chunk_006 -> page 2]
_DOC_ID_LINEAGE_RE = re.compile(r"\[doc_id:\s*.*?\]", re.DOTALL)
_CHUNK_LINEAGE_RE = re.compile(r"\[[^\]]*_chunk_\d+[^\]]*\]")
# Raw per-chunk source lines: " papers/Edge2024_GraphRAG.pdf_chunk_030, page 8"
_RAW_SOURCE_LINE_RE = re.compile(
    r"(?m)^\s*\S*_chunk_\d+,\s*page\s*\d+\s*$"
)
# The raw source-list header block that must never ship.
_SOURCE_CITATIONS_HEADER_RE = re.compile(r"(?m)^\s*Source Citations:\s*$")
_ORPHAN_QUERY_RE = re.compile(r"(?im)^\s*(?:c_id|doc_id|page|highlight)=[^\n]*$")


def strip_production_leaks(text: str) -> str:
    """Remove internal doc_id lineage markers and raw page references from text.

    Keeps verified evidence links like ``[S1](/api/page-view?...)``; removes
    everything that leaks chunk/page bookkeeping to the reader.
    """
    t = text or ""
    t = _LINKED_PAGE_CHIP_RE.sub("", t)
    t = _BARE_PAGE_ARROW_RE.sub("", t)
    t = _DOC_ID_LINEAGE_RE.sub("", t)
    t = _CHUNK_LINEAGE_RE.sub("", t)
    t = _RAW_SOURCE_LINE_RE.sub("", t)
    t = _SOURCE_CITATIONS_HEADER_RE.sub("", t)
    t = _ORPHAN_QUERY_RE.sub("", t)
    # Drop exact duplicate paragraphs introduced by overlapping stream frames.
    blocks = re.split(r"\n\s*\n", t)
    unique: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        clean = re.sub(r"[ \t]{2,}", " ", block).strip()
        if clean and clean not in seen:
            unique.append(clean)
            seen.add(clean)
    return "\n\n".join(unique).strip()


def sanitize_stream_final(text: str) -> str:
    """Final sanitisation pass for streamed output before display."""
    return strip_production_leaks(text)


def sanitize_archipelago_output(text: str) -> str:
    """Sanitize overall output text for display."""
    return sanitize_stream_final(text)

"""Deterministic evidence selection without padding or neighborhood dilution.

One concern: rank and select anchor-relevant citations with a focused budget,
filter low-signal end-matter/boilerplate, respect withdrawal and metadata-only
constraints, and never pad citations to an arbitrary 10.
"""

from __future__ import annotations

import re
from typing import Any

from .docmap import hf_doc_path
from .provenance import (
    CANONICAL_CHUNK_RE,
    CLAIM_SUPPORT_NOT_ASSESSED,
    PROVENANCE_CHUNK_AMBIGUOUS,
    PROVENANCE_CHUNK_UNMATCHED,
    PROVENANCE_METADATA_ONLY,
    PROVENANCE_NO_PASSAGE,
    PROVENANCE_NONE,
    PROVENANCE_VERIFIED,
    PROVENANCE_WITHDRAWN,
    build_chunk_provenance_index,
    build_grounding_trace,
    norm_text_hash,
    verify_chunk_provenance,
)
from .source_resolution import is_hf_resolvable_doc, is_toc_or_index_doc
from .text import tokens
from .withdrawal import is_citable_source, withdrawn_documents

# Small focused evidence budget — never pad citations to an arbitrary 10.
MAX_ANCHOR_CITATIONS = 3
# Minimum characters for a passage to be considered substantive prose.
MIN_PASSAGE_CHARS = 40
# Thresholds for detecting boilerplate / attention-vis / index / bibliography dumps.
SINGLE_WORD_LINE_MIN_LINES = 8
SINGLE_WORD_LINE_RATIO = 0.6
INDEX_ENTRY_MIN_HITS = 4
BIB_YEAR_MIN_HITS = 3
# Deterministic scoring weights for anchor source ranking.
SOURCE_OVERLAP_WEIGHT = 10
SOURCE_LATER_PAGE_BONUS = 2
CANONICAL_PAPER_BONUS = 50
UNIQUE_CHUNK_BONUS = 15
HF_RESOLVABLE_BONUS = 30
UNRESOLVABLE_DOC_PENALTY = -30
TOC_INDEX_DOC_PENALTY = -50
RAW_UPLOAD_PENALTY = -25
LOW_SIGNAL_PENALTY = -40
# Additional passages beyond rank 1 must have direct lexical relevance.
EXTRA_PASSAGE_MIN_OVERLAP = 2
SECONDARY_CONCEPT_MIN_OVERLAP = 2
TEXT_DEDUP_PREFIX_LEN = 160

_INDEX_ENTRY_RE = re.compile(r"\b[a-z][a-z\s-]{2,30},\s*\d+(?:[\u2013-]\d+)?")
_BIB_YEAR_RE = re.compile(r"\((?:19|20)\d{2}[a-z]?\)")
_FRONTMATTER_RE = re.compile(
    r"(?:book:\s*about the authors|chapter file:\s*about-the-authors|"
    r"contents\s*/\s*section headings:|table of contents\b)",
    re.I,
)

# Primary paper doc_id hints for foundational concepts so canonical primary
# sources outrank secondary passing mentions on the same concept node.
PRIMARY_PAPER_HINTS: dict[str, tuple[str, ...]] = {
    "transformer": ("vaswani",),
    "self_attention": ("vaswani",),
    "multi_head_attention": ("vaswani",),
    "bert": ("devlin",),
    "masked_language_modeling": ("devlin",),
    "rag": ("lewis",),
    "retrieval_augmented_generation": ("lewis",),
    "dpr": ("karpukhin",),
    "dense_passage_retrieval": ("karpukhin",),
    "bm25": ("karpukhin",),
    "flashattention": ("dao", "upload_cb7badb2"),
    "low_rank_adaptation": ("hu2021",),
    "qlora": ("dettmers",),
    "kv_cache": ("kwon",),
    "paged_attention": ("kwon",),
    "graph_rag": ("edge2024",),
}


def is_low_signal_passage(text: str) -> bool:
    """True when a passage is end-matter, index, bibliography, or line-per-word dump."""
    cleaned = (text or "").strip()
    if len(cleaned) < MIN_PASSAGE_CHARS:
        return True
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) >= SINGLE_WORD_LINE_MIN_LINES:
        single_word = sum(1 for line in lines if len(line.split()) == 1)
        if (single_word / len(lines)) >= SINGLE_WORD_LINE_RATIO:
            return True
    if _FRONTMATTER_RE.search(cleaned):
        return True
    if len(_INDEX_ENTRY_RE.findall(cleaned)) >= INDEX_ENTRY_MIN_HITS:
        return True
    return len(_BIB_YEAR_RE.findall(cleaned)) >= BIB_YEAR_MIN_HITS


def _primary_paper_bonus(cid: str, raw_doc_id: str, canonical_doc_id: str) -> int:
    hints = PRIMARY_PAPER_HINTS.get(cid, ())
    if not hints:
        return 0
    combined = f"{raw_doc_id} {canonical_doc_id}".lower()
    return CANONICAL_PAPER_BONUS if any(h in combined for h in hints) else 0


def score_source_for_concept(
    cid: str,
    concept_label: str,
    source: dict[str, Any],
    query: str,
) -> tuple[int, int]:
    """Return ``(total_score, token_overlap)`` for ranking one source passage."""
    passage = str(source.get("text_passage") or "")
    wanted = set(tokens(query)) | set(tokens(concept_label))
    overlap = len(wanted & set(tokens(passage)))
    raw_doc = str(source.get("doc_id") or "")
    canonical_doc = hf_doc_path(raw_doc)
    chunk_id = str(source.get("chunk_id") or "")
    page = int(source.get("page_number") or 0)

    total = overlap * SOURCE_OVERLAP_WEIGHT
    if page > 1:
        total += SOURCE_LATER_PAGE_BONUS
    total += _primary_paper_bonus(cid, raw_doc, canonical_doc)
    if CANONICAL_CHUNK_RE.match(chunk_id) and not canonical_doc.startswith("upload_"):
        total += UNIQUE_CHUNK_BONUS
    if is_toc_or_index_doc(raw_doc) or is_toc_or_index_doc(canonical_doc):
        total += TOC_INDEX_DOC_PENALTY
    elif is_hf_resolvable_doc(canonical_doc) or is_hf_resolvable_doc(raw_doc):
        total += HF_RESOLVABLE_BONUS
    else:
        total += UNRESOLVABLE_DOC_PENALTY
    if canonical_doc.startswith("upload_"):
        total += RAW_UPLOAD_PENALTY
    if is_low_signal_passage(passage):
        total += LOW_SIGNAL_PENALTY
    return total, overlap


def _dedup_key(record: dict[str, Any]) -> tuple[str, str]:
    """Canonical deduplication key — never conflates distinct chunks on the same page."""
    doc_id = str(record.get("doc_id") or record.get("url") or record.get("label") or "")
    chunk_id = str(record.get("chunk_id") or "").strip()
    if chunk_id:
        return (doc_id, chunk_id)
    text_hash = norm_text_hash(str(record.get("text_passage") or ""))
    return (doc_id, f"p{record.get('page_number')}_{text_hash}")


def _text_fingerprint(record: dict[str, Any]) -> str:
    """Normalized passage prefix to deduplicate identical uploaded copies."""
    norm = re.sub(r"\s+", " ", str(record.get("text_passage") or "").strip().lower())
    return norm[:TEXT_DEDUP_PREFIX_LEN] if norm else ""


def _ranked_live_sources(
    graph: Any,
    cid: str,
    query: str,
    retired: set[str],
) -> tuple[list[tuple[int, int, dict[str, Any]]], bool]:
    """Return live sources for ``cid`` sorted best-first, plus ``all_withdrawn``."""
    raw_sources = [
        s for s in (graph.nodes.get(cid) or {}).get("sources") or [] if isinstance(s, dict)
    ]
    if not raw_sources:
        return [], False
    live = [s for s in raw_sources if is_citable_source(s, retired)]
    if not live:
        return [], True

    label = graph.label(cid)
    non_low_signal = [
        s for s in live if not is_low_signal_passage(str(s.get("text_passage") or ""))
    ]
    pool = non_low_signal if non_low_signal else live

    canonical_pool = [
        s for s in pool if not hf_doc_path(str(s.get("doc_id") or "")).startswith("upload_")
    ]
    if canonical_pool:
        pool = canonical_pool

    scored = []
    for src in pool:
        total, overlap = score_source_for_concept(cid, label, src, query)
        scored.append((total, overlap, src))
    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            str(item[2].get("doc_id") or ""),
            str(item[2].get("chunk_id") or ""),
        )
    )
    return scored, False


def select_evidence_citations(
    graph: Any,
    anchor_cid: str,
    query: str,
    max_citations: int = MAX_ANCHOR_CITATIONS,
) -> list[dict[str, Any]]:
    """Select anchor-relevant citations without padding or neighborhood dilution."""
    if not anchor_cid or anchor_cid not in graph.nodes:
        return []

    retired = withdrawn_documents()
    scored_anchor, all_withdrawn = _ranked_live_sources(graph, anchor_cid, query, retired)
    if all_withdrawn:
        return [graph.cite_record(anchor_cid, query, index=1)]

    collected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_texts: set[str] = set()

    def _try_append(cid: str, src: dict[str, Any]) -> bool:
        rec = graph.cite_record(cid, query, index=len(collected) + 1, source_override=src)
        if not (rec.get("label") or rec.get("doc_id") or rec.get("url")):
            return False
        dkey = _dedup_key(rec)
        tfp = _text_fingerprint(rec)
        if dkey in seen_keys or (tfp and tfp in seen_texts):
            return False
        seen_keys.add(dkey)
        if tfp:
            seen_texts.add(tfp)
        collected.append(rec)
        return True

    primary_doc = ""
    for rank_idx, (_score, overlap, src) in enumerate(scored_anchor):
        if len(collected) >= max_citations:
            break
        src_doc = hf_doc_path(str(src.get("doc_id") or ""))
        if rank_idx == 0:
            if _try_append(anchor_cid, src):
                primary_doc = src_doc
            continue
        if overlap < EXTRA_PASSAGE_MIN_OVERLAP:
            continue
        if PRIMARY_PAPER_HINTS.get(anchor_cid) and primary_doc and src_doc != primary_doc:
            continue
        _try_append(anchor_cid, src)

    if len(collected) < max_citations:
        for other_cid in graph.phrase_hits(query):
            if len(collected) >= max_citations:
                break
            if other_cid == anchor_cid or other_cid not in graph.nodes:
                continue
            other_scored, other_withdrawn = _ranked_live_sources(graph, other_cid, query, retired)
            if other_withdrawn or not other_scored:
                continue
            _score, overlap, src = other_scored[0]
            if overlap >= SECONDARY_CONCEPT_MIN_OVERLAP:
                _try_append(other_cid, src)

    return collected


__all__ = [
    "CLAIM_SUPPORT_NOT_ASSESSED",
    "MAX_ANCHOR_CITATIONS",
    "PRIMARY_PAPER_HINTS",
    "PROVENANCE_CHUNK_AMBIGUOUS",
    "PROVENANCE_CHUNK_UNMATCHED",
    "PROVENANCE_METADATA_ONLY",
    "PROVENANCE_NONE",
    "PROVENANCE_NO_PASSAGE",
    "PROVENANCE_VERIFIED",
    "PROVENANCE_WITHDRAWN",
    "build_chunk_provenance_index",
    "build_grounding_trace",
    "is_low_signal_passage",
    "score_source_for_concept",
    "select_evidence_citations",
    "verify_chunk_provenance",
]

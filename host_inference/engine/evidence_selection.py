"""Deterministic evidence selection without padding or neighborhood dilution.

One concern: rank and select anchor-relevant citations with a focused budget,
filter low-signal end-matter/boilerplate, respect withdrawal and metadata-only
constraints, and never pad citations to an arbitrary 10.
"""

from __future__ import annotations

import re
from typing import Any

from .access_profile import is_open_access_profile, is_pearson_url
from .corpus_titles import clean_bibliographic_title
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
from .source_resolution import (
    SOURCE_CAT_PEARSON,
    SOURCE_CAT_TOC_INDEX,
    is_hf_resolvable_doc,
    is_toc_or_index_doc,
    resolve_source_target,
)
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
# Direct catalog passage scoring when graph node sources are absent or weak.
CATALOG_TOKEN_WEIGHT = 4
CATALOG_CONCEPT_WEIGHT = 2
CATALOG_PHRASE_BONUS = 12
CATALOG_MIN_SCORE = 6
CATALOG_PASSAGE_CHAR_LIMIT = 700

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
    "paging": ("08_paging",),
    "tlb": ("09_tlbs",),
    "address_translation": ("07_address_translation",),
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

    if collected and len(collected) < max_citations:
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


def _query_bigrams(raw: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{2,}", (raw or "").lower())
    return [f"{words[idx]} {words[idx + 1]}" for idx in range(len(words) - 1)]


def _build_catalog_citation(
    entry: dict[str, Any],
    anchor_cid: str,
    index: int,
    chunk_index: dict[tuple[str, str], dict[str, Any]] | None,
) -> dict[str, Any]:
    raw_doc_id = str(entry.get("doc_id") or "").strip()
    doc_id = hf_doc_path(raw_doc_id)
    page_val = entry.get("page")
    page_int = int(page_val) if isinstance(page_val, int) and page_val > 0 else 1
    chunk_id = str(entry.get("passage_id") or entry.get("chunk_id") or "").strip() or None
    resolved = resolve_source_target(
        raw_doc_id=raw_doc_id,
        canonical_doc_id=doc_id,
        page_number=page_int,
        title="",
        all_withdrawn=False,
    )
    source_category = str(resolved["source_category"])
    source_type = str(resolved["source_type"])
    reader_resolvable = bool(resolved["reader_resolvable"])
    page = resolved["page_number"]
    hf_url = str(resolved["url"] or "")
    doc_title = resolved["resolved_title"] or (doc_id.split("/")[-1] if doc_id else "")
    if not resolved["is_pearson"] and (doc_id or doc_title):
        doc_title = clean_bibliographic_title(doc_id, doc_title)
    if not doc_title:
        label = ""
    elif source_category == SOURCE_CAT_PEARSON and hf_url:
        label = f"[S{index}: {doc_title} (Pearson catalogue-only — institutional login)]"
    elif source_category == SOURCE_CAT_TOC_INDEX:
        label = f"[S{index}: {doc_title} (TOC/index metadata only)]"
    elif hf_url:
        label = f"[S{index}: {doc_title}{f', #page={page}' if page else ''}]"
    else:
        label = f"[S{index}: {doc_title} (source unavailable — metadata only)]"

    passage_text = str(entry.get("text") or "")[:CATALOG_PASSAGE_CHAR_LIMIT]
    provenance = verify_chunk_provenance(
        raw_doc_id=raw_doc_id,
        canonical_doc_id=doc_id,
        chunk_id=chunk_id,
        page_number=page,
        hf_url=hf_url,
        text_passage=passage_text,
        all_withdrawn=False,
        chunk_index=chunk_index,
        source_category=source_category,
        reader_resolvable=reader_resolvable,
    )
    return {
        "label": label,
        "evidence_id": f"S{index}",
        "source_type": source_type,
        "source_category": source_category,
        "reader_resolvable": reader_resolvable,
        "page_verified": bool(resolved["page_verified"]),
        "is_pearson": bool(resolved["is_pearson"]),
        "book_id": str(resolved["book_id"] or ""),
        "book_type": str(resolved["book_type"] or ""),
        "hf_path": str(resolved["hf_path"] or ""),
        "concept_id": str(entry.get("concept_id") or anchor_cid),
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "canonical_passage_id": provenance["canonical_passage_id"],
        "provenance_status": provenance["provenance_status"],
        "chunk_provenance_match": provenance["chunk_provenance_match"],
        "claim_support_status": provenance["claim_support_status"],
        "doc_title": doc_title,
        "authors": "",
        "page_number": page,
        "printed_page": entry.get("printed_page"),
        "pdf_url": hf_url,
        "url": hf_url,
        "withdrawn": False,
        "notice": "",
        "text_passage": passage_text,
        "passage": passage_text,
        "section": None,
        "doi": None,
        "publication_year": None,
        "source_provider": None,
        "retrieved_at": None,
        "verification_status": provenance["verification_status"],
        "status_level": provenance["status_level"],
        "access_status": str(resolved["access_status"]),
    }


def select_catalog_passages(
    catalog: Any,
    query: str,
    concept_label: str = "",
    anchor_cid: str = "",
    max_citations: int = MAX_ANCHOR_CITATIONS,
    open_access_only: bool | None = None,
    chunk_index: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rank indexed ``catalog.passages`` by lexical and bigram overlap when graph sources lack coverage."""
    passages = list(getattr(catalog, "passages", None) or [])
    if not passages or max_citations <= 0:
        return []

    q_toks = set(tokens(query))
    c_toks = set(tokens(f"{anchor_cid.replace('_', ' ')} {concept_label}"))
    bigrams = list(dict.fromkeys(_query_bigrams(query) + _query_bigrams(concept_label)))
    if not (q_toks or c_toks or bigrams):
        return []

    retired = withdrawn_documents()
    oa_mode = is_open_access_profile() if open_access_only is None else open_access_only
    scored: list[tuple[int, dict[str, Any]]] = []

    for entry in passages:
        if not isinstance(entry, dict):
            continue
        raw_doc = str(entry.get("doc_id") or "").strip()
        if not raw_doc:
            continue
        canon_doc = hf_doc_path(raw_doc)
        if not is_citable_source({"doc_id": raw_doc}, retired):
            continue
        if is_toc_or_index_doc(raw_doc) or is_toc_or_index_doc(canon_doc):
            continue
        if oa_mode and (
            is_pearson_url(raw_doc)
            or "pearson" in raw_doc.lower()
            or "pearson" in canon_doc.lower()
        ):
            continue
        text = str(entry.get("text") or "")
        if is_low_signal_passage(text):
            continue

        doc_tokens = set(entry.get("tokens") or ()) or tokens(text)
        doc_lower = text.lower()
        q_overlap = len(q_toks & doc_tokens)
        c_overlap = len(c_toks & doc_tokens)
        phrase_hits = sum(1 for bg in bigrams if bg in doc_lower)
        score = (
            q_overlap * CATALOG_TOKEN_WEIGHT
            + c_overlap * CATALOG_CONCEPT_WEIGHT
            + phrase_hits * CATALOG_PHRASE_BONUS
        )
        score += _primary_paper_bonus(anchor_cid, raw_doc, canon_doc)
        if score >= CATALOG_MIN_SCORE and (q_overlap >= 1 or phrase_hits >= 1):
            scored.append((score, entry))

    scored.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("doc_id") or ""),
            int(item[1].get("page") or 0),
            str(item[1].get("passage_id") or ""),
        )
    )

    collected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_texts: set[str] = set()
    for _score, entry in scored:
        if len(collected) >= max_citations:
            break
        rec = _build_catalog_citation(entry, anchor_cid, len(collected) + 1, chunk_index)
        dkey = _dedup_key(rec)
        tfp = _text_fingerprint(rec)
        if dkey in seen_keys or (tfp and tfp in seen_texts):
            continue
        if oa_mode and rec.get("is_pearson"):
            continue
        seen_keys.add(dkey)
        if tfp:
            seen_texts.add(tfp)
        collected.append(rec)
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
    "select_catalog_passages",
    "select_evidence_citations",
    "verify_chunk_provenance",
]

"""Canonical chunk provenance, 4-state source contract, and printed-to-PDF page mapping.

One concern: enforce the unified 4-state source provenance contract
(``verified_full_text_passage``, ``metadata_only_record``,
``institutional_licensed``, ``unavailable_document``) alongside fine-grained
evidence states, verify unique canonical ``chunk_id`` provenance, and resolve
printed-page-to-PDF-page mapping with strict page-bounds validation.
"""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any

from .access_profile import (
    d14_canonical_oa_url,
    is_d14_approved_oa,
    is_d14_excluded_commercial,
    is_institutional_card,
    is_open_access_profile,
    is_pearson_url,
    load_d14_source_registry,
    lookup_d14_source,
)
from .corpus_titles import clean_bibliographic_title
from .docmap import hf_doc_path

PROVENANCE_HASH_LEN = 16
CANONICAL_CHUNK_RE = re.compile(r"^(?:chunk_\d+|[a-z0-9_]+_seed_\d+)$", re.I)
UPLOAD_CHUNK_RE = re.compile(r"^upload_[0-9a-f]+_p\d+_\d+$", re.I)
_OSTEP_FILE_RE = re.compile(r"^(\d{2})_([a-z0-9_]+)\.pdf$", re.I)
_RAW_FILENAME_EXT_RE = re.compile(r"\.(?:pdf|txt|md|json|html|htm)$", re.I)

# Unified 4-state Source Provenance Contract (D14).
SOURCE_KIND_VERIFIED_FULL_TEXT = "verified_full_text_passage"
SOURCE_KIND_METADATA_ONLY = "metadata_only_record"
SOURCE_KIND_INSTITUTIONAL = "institutional_licensed"
SOURCE_KIND_UNAVAILABLE = "unavailable_document"

ALL_SOURCE_KINDS: frozenset[str] = frozenset({
    SOURCE_KIND_VERIFIED_FULL_TEXT, SOURCE_KIND_METADATA_ONLY,
    SOURCE_KIND_INSTITUTIONAL, SOURCE_KIND_UNAVAILABLE,
})
SOURCE_KIND_LABELS: dict[str, str] = {
    SOURCE_KIND_VERIFIED_FULL_TEXT: "Verified Full-Text Passage",
    SOURCE_KIND_METADATA_ONLY: "Metadata-Only Record",
    SOURCE_KIND_INSTITUTIONAL: "Institutional Licensed",
    SOURCE_KIND_UNAVAILABLE: "Unavailable Document",
}

CLAIM_SUPPORT_NOT_ASSESSED = "not_assessed"
PROVENANCE_VERIFIED = "provenance_verified"
PROVENANCE_CHUNK_UNMATCHED = "chunk_unmatched"
PROVENANCE_CHUNK_AMBIGUOUS = "chunk_ambiguous"
PROVENANCE_METADATA_ONLY = "metadata_only"
PROVENANCE_WITHDRAWN = "withdrawn"
PROVENANCE_NO_PASSAGE = "no_passage"
PROVENANCE_NONE = "none"

EVIDENCE_STATE_RELEVANT_SUPPORTING = "RELEVANT_SUPPORTING_PASSAGE"
EVIDENCE_STATE_AVAILABLE_FULL_TEXT = "AVAILABLE_FULL_TEXT_PASSAGE"
EVIDENCE_STATE_RETRIEVED_UNASSESSED = "RETRIEVED_UNASSESSED_SUPPORT"
EVIDENCE_STATE_METADATA_ONLY = "METADATA_ONLY_REFERENCE"
EVIDENCE_STATE_AUTHORIZED_EXTERNAL = "AUTHORIZED_EXTERNAL_LINK"
EVIDENCE_STATE_UNAVAILABLE = "UNAVAILABLE_DOCUMENT"

ALL_EVIDENCE_STATES: frozenset[str] = frozenset({
    EVIDENCE_STATE_RELEVANT_SUPPORTING, EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
    EVIDENCE_STATE_RETRIEVED_UNASSESSED, EVIDENCE_STATE_METADATA_ONLY,
    EVIDENCE_STATE_AUTHORIZED_EXTERNAL, EVIDENCE_STATE_UNAVAILABLE,
})
FULL_TEXT_EVIDENCE_STATES: frozenset[str] = frozenset({
    EVIDENCE_STATE_RELEVANT_SUPPORTING, EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
    EVIDENCE_STATE_RETRIEVED_UNASSESSED,
})
FOLLOW_UP_ELIGIBLE_STATES: frozenset[str] = frozenset({
    EVIDENCE_STATE_RELEVANT_SUPPORTING, EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
})
EVIDENCE_STATE_LABELS: dict[str, str] = {
    EVIDENCE_STATE_RELEVANT_SUPPORTING: "Relevant Supporting Passage",
    EVIDENCE_STATE_AVAILABLE_FULL_TEXT: "Available Full-Text Passage",
    EVIDENCE_STATE_RETRIEVED_UNASSESSED: "Retrieved · Support Unassessed",
    EVIDENCE_STATE_METADATA_ONLY: "Metadata-Only Reference",
    EVIDENCE_STATE_AUTHORIZED_EXTERNAL: "Authorized External Link",
    EVIDENCE_STATE_UNAVAILABLE: "Unavailable Document",
}
_SUPPORTED_CLAIM_STATUSES = frozenset({"supported", "relevant_supporting", "verified", "claim_supported"})

DEISENROTH_FRONT_MATTER_PAGES = 16
DEISENROTH_PAGE_COUNT = 417
LSTM_PRINTED_OFFSET = 1734
LSTM_PAGE_COUNT = 32
CONVNETS_PRINTED_OFFSET = 2277
CONVNETS_PAGE_COUNT = 46
BACKPROP_PRINTED_OFFSET = 532
BACKPROP_PAGE_COUNT = 4
MIN_VALID_PAGE = 1

DOCUMENT_PAGE_MAP: dict[str, dict[str, int]] = {
    "deisenroth_math_for_ml.pdf": {"printed_offset": -DEISENROTH_FRONT_MATTER_PAGES, "front_matter_pages": DEISENROTH_FRONT_MATTER_PAGES, "page_count": DEISENROTH_PAGE_COUNT},
    "hochreiter1997_lstm.pdf": {"printed_offset": LSTM_PRINTED_OFFSET, "front_matter_pages": 0, "page_count": LSTM_PAGE_COUNT},
    "lecun1998_convnets.pdf": {"printed_offset": CONVNETS_PRINTED_OFFSET, "front_matter_pages": 0, "page_count": CONVNETS_PAGE_COUNT},
    "rumelhart1986_backpropagation.pdf": {"printed_offset": BACKPROP_PRINTED_OFFSET, "front_matter_pages": 0, "page_count": BACKPROP_PAGE_COUNT},
}


def norm_text_hash(text: str) -> str:
    """Stable short hash of whitespace-normalized passage text."""
    return sha256(re.sub(r"\s+", " ", (text or "").strip()).encode("utf-8")).hexdigest()[:PROVENANCE_HASH_LEN]


def ostep_chapter_info(doc_id: str) -> dict[str, Any] | None:
    """Return OSTEP local chapter metadata when ``doc_id`` is an OSTEP chapter PDF."""
    base = (doc_id or "").strip().rsplit("/", 1)[-1].lower()
    match = _OSTEP_FILE_RE.match(base)
    if not match or ("ostep" not in (doc_id or "").lower() and not match):
        return None
    local_num = int(match.group(1))
    entry = lookup_d14_source(base)
    title = entry["title"] if entry else match.group(2).replace("_", " ").title()
    return {"ostep_chapter_number": local_num, "ostep_chapter_title": title, "ostep_local_file_number": local_num}


def format_canonical_title(doc_id: str, raw_title: str = "") -> str:
    """Return a clean bibliographic title using corpus_titles and D14 inventory metadata."""
    clean_doc = (doc_id or "").strip()
    if clean_doc:
        cleaned_corpus = clean_bibliographic_title(clean_doc, "")
        if cleaned_corpus and not _RAW_FILENAME_EXT_RE.search(cleaned_corpus) and cleaned_corpus not in {clean_doc, "Source"}:
            return cleaned_corpus
        entry = lookup_d14_source(clean_doc)
        if entry and entry.get("title"):
            return str(entry["title"])
    title = clean_bibliographic_title(clean_doc, raw_title)
    if _RAW_FILENAME_EXT_RE.search(title):
        title = _RAW_FILENAME_EXT_RE.sub("", title)
    title = re.sub(r"\s{2,}", " ", title.replace("_", " ")).strip()
    return title or "Untitled Source"


def _doc_page_metadata(doc_id: str) -> dict[str, int | None]:
    base = (doc_id or "").strip().rsplit("/", 1)[-1].lower()
    meta = dict(DOCUMENT_PAGE_MAP.get(base, {}))
    known_pages: int | None = meta.get("page_count")
    if known_pages is None:
        entry = lookup_d14_source(doc_id)
        if entry is not None:
            known_pages = entry.get("page_count")
    return {
        "printed_offset": int(meta.get("printed_offset", 0)),
        "front_matter_pages": int(meta.get("front_matter_pages", 0)),
        "page_count": known_pages,
    }


def printed_to_pdf_page(doc_id: str, printed_page: int | str | None) -> int | None:
    """Convert a printed page number into a validated 1-based physical PDF page."""
    if isinstance(printed_page, bool) or printed_page is None:
        return None
    raw = str(printed_page).strip()
    if not raw.isdigit():
        return None
    parsed = int(raw)
    if parsed < MIN_VALID_PAGE:
        return None
    meta = _doc_page_metadata(doc_id)
    pdf_page = parsed - int(meta["printed_offset"] or 0)
    if pdf_page < MIN_VALID_PAGE:
        return None
    max_pages = meta.get("page_count")
    if isinstance(max_pages, int) and max_pages > 0 and pdf_page > max_pages:
        return None
    return pdf_page


def resolve_page_provenance(
    doc_id: str,
    pdf_page: int | None,
    printed_page: int | str | None = None,
) -> dict[str, Any]:
    """Resolve physical PDF page vs printed page and validate against known bounds."""
    meta = _doc_page_metadata(doc_id)
    offset = int(meta["printed_offset"] or 0)
    front_matter = int(meta["front_matter_pages"] or 0)
    max_pages = meta.get("page_count")

    valid_pdf = (
        pdf_page
        if isinstance(pdf_page, int) and not isinstance(pdf_page, bool) and pdf_page >= MIN_VALID_PAGE
        else None
    )
    if valid_pdf is None and printed_page is not None:
        valid_pdf = printed_to_pdf_page(doc_id, printed_page)

    page_in_bounds = True
    if valid_pdf is not None and isinstance(max_pages, int) and max_pages > 0:
        page_in_bounds = MIN_VALID_PAGE <= valid_pdf <= max_pages

    resolved_printed: int | str | None = None
    if printed_page is not None and str(printed_page).strip():
        raw_p = str(printed_page).strip()
        resolved_printed = int(raw_p) if raw_p.isdigit() else raw_p
    elif valid_pdf is not None and offset != 0:
        if front_matter > 0 and valid_pdf <= front_matter:
            resolved_printed = f"front matter (p. {valid_pdf})"
        elif valid_pdf + offset >= MIN_VALID_PAGE:
            resolved_printed = valid_pdf + offset

    pages_differ = (
        valid_pdf is not None
        and resolved_printed is not None
        and str(resolved_printed) != str(valid_pdf)
    )
    if valid_pdf is None:
        page_display = f"printed p. {resolved_printed}" if resolved_printed is not None else ""
    elif pages_differ:
        page_display = f"PDF p. {valid_pdf} (printed p. {resolved_printed})"
    else:
        page_display = f"PDF p. {valid_pdf}"

    return {
        "pdf_page": valid_pdf,
        "printed_page": resolved_printed,
        "page_offset": offset,
        "page_display": page_display,
        "pages_differ": pages_differ,
        "known_page_count": max_pages,
        "page_in_bounds": page_in_bounds,
    }


def classify_evidence_state(record: dict[str, Any], *, open_access_only: bool | None = None) -> str:
    """Map any citation/source record onto the unified Evidence-State Contract."""
    oa_only = is_open_access_profile() if open_access_only is None else open_access_only
    if not isinstance(record, dict) or record.get("withdrawn") or str(record.get("source_type") or "").strip().lower() == "withdrawn":
        return EVIDENCE_STATE_UNAVAILABLE
    if is_d14_excluded_commercial(record):
        return EVIDENCE_STATE_METADATA_ONLY

    source_kind = str(record.get("source_kind") or "").strip().lower()
    source_cat = str(record.get("source_category") or "").strip().lower()
    source_type = str(record.get("source_type") or "").strip().lower()
    prov_status = str(record.get("provenance_status") or "").strip().lower()
    claim_status = str(record.get("claim_support_status") or "").strip().lower()
    raw_url = str(record.get("url") or record.get("pdf_url") or "").strip()

    if source_kind == SOURCE_KIND_UNAVAILABLE:
        return EVIDENCE_STATE_UNAVAILABLE
    if source_kind == SOURCE_KIND_METADATA_ONLY or source_cat == "toc_index_only_textbook" or source_type in {"toc_index_only", "metadata_only", "catalog_metadata"}:
        return EVIDENCE_STATE_METADATA_ONLY
    if source_kind == SOURCE_KIND_INSTITUTIONAL or source_cat == "pearson_catalogue_only" or is_institutional_card(record):
        if oa_only:
            return EVIDENCE_STATE_UNAVAILABLE
        if raw_url and record.get("reader_resolvable", True) and not raw_url.startswith("/chat"):
            return EVIDENCE_STATE_AUTHORIZED_EXTERNAL
        return EVIDENCE_STATE_UNAVAILABLE

    has_passage = bool(str(record.get("text_passage") or record.get("passage") or "").strip())
    if raw_url.startswith("https://") and not is_pearson_url(raw_url) and not has_passage:
        return EVIDENCE_STATE_AUTHORIZED_EXTERNAL

    is_readable = (
        source_kind == SOURCE_KIND_VERIFIED_FULL_TEXT
        or is_d14_approved_oa(record)
        or (bool(raw_url) and raw_url.startswith(("/read?", "/api/page-view?", "/papers/", "https://")) and record.get("reader_resolvable", True) is not False)
    )
    if not is_readable:
        return EVIDENCE_STATE_UNAVAILABLE

    page_ok = bool(record.get("page_verified")) or (isinstance(record.get("page_number"), int) and record["page_number"] >= MIN_VALID_PAGE)
    if claim_status in _SUPPORTED_CLAIM_STATUSES or record.get("claim_supported") is True or record.get("relevance_verified") is True:
        return EVIDENCE_STATE_RELEVANT_SUPPORTING
    if prov_status == PROVENANCE_VERIFIED or (page_ok and has_passage and prov_status not in {PROVENANCE_CHUNK_UNMATCHED, PROVENANCE_CHUNK_AMBIGUOUS}):
        return EVIDENCE_STATE_AVAILABLE_FULL_TEXT
    return EVIDENCE_STATE_RETRIEVED_UNASSESSED


def source_kind_for_evidence_state(ev_state: str, record: dict[str, Any] | None = None) -> str:
    """Map an ``evidence_state`` + optional ``record`` onto the 4-state ``source_kind``."""
    if record and is_d14_excluded_commercial(record):
        return SOURCE_KIND_METADATA_ONLY
    if ev_state in FULL_TEXT_EVIDENCE_STATES:
        return SOURCE_KIND_VERIFIED_FULL_TEXT
    if ev_state == EVIDENCE_STATE_METADATA_ONLY:
        return SOURCE_KIND_METADATA_ONLY
    if ev_state == EVIDENCE_STATE_AUTHORIZED_EXTERNAL:
        if record and (is_institutional_card(record) or is_pearson_url(record.get("url"))):
            return SOURCE_KIND_INSTITUTIONAL
        return SOURCE_KIND_VERIFIED_FULL_TEXT
    return SOURCE_KIND_UNAVAILABLE


def is_follow_up_eligible(record: dict[str, Any]) -> bool:
    """True only when ``record`` has verified full-text passage support for follow-ups."""
    if not isinstance(record, dict) or record.get("withdrawn"):
        return False
    state = str(record.get("evidence_state") or "").strip()
    if state not in ALL_EVIDENCE_STATES:
        state = classify_evidence_state(record)
    return state in FOLLOW_UP_ELIGIBLE_STATES and bool(record.get("reader_resolvable", True))


def build_chunk_provenance_index(nodes: dict[str, dict[str, Any]]) -> dict[tuple[str, str], set[str]]:
    """Map ``(canonical_doc_id, chunk_id)`` to distinct passage text hashes."""
    index: dict[tuple[str, str], set[str]] = {}
    for node in nodes.values():
        for src in node.get("sources") or []:
            if not isinstance(src, dict):
                continue
            raw_doc, chunk_id = str(src.get("doc_id") or "").strip(), str(src.get("chunk_id") or "").strip()
            if raw_doc and chunk_id:
                index.setdefault((hf_doc_path(raw_doc), chunk_id), set()).add(norm_text_hash(str(src.get("text_passage") or "")))
    return index


def _prov_rec(
    pid: str | None, prov: str, match: str, ver: str, level: str, ev: str, sk: str
) -> dict[str, Any]:
    return {
        "canonical_passage_id": pid,
        "provenance_status": prov,
        "chunk_provenance_match": match,
        "claim_support_status": CLAIM_SUPPORT_NOT_ASSESSED,
        "verification_status": ver,
        "status_level": level,
        "evidence_state": ev,
        "evidence_state_label": EVIDENCE_STATE_LABELS[ev],
        "source_kind": sk,
        "source_kind_label": SOURCE_KIND_LABELS[sk],
    }


def verify_chunk_provenance(
    *,
    raw_doc_id: str,
    canonical_doc_id: str,
    chunk_id: str | None,
    page_number: int | None,
    hf_url: str,
    text_passage: str,
    all_withdrawn: bool,
    chunk_index: dict[tuple[str, str], set[str]] | None = None,
    source_category: str = "",
    reader_resolvable: bool = True,
) -> dict[str, Any]:
    """Verify canonical ``chunk_id`` uniqueness and return 4-state + provenance metadata."""
    if all_withdrawn:
        return _prov_rec(None, PROVENANCE_WITHDRAWN, "withdrawn", "Withdrawn — unavailable", "withdrawn", EVIDENCE_STATE_UNAVAILABLE, SOURCE_KIND_UNAVAILABLE)
    if is_d14_excluded_commercial(raw_doc_id) or is_d14_excluded_commercial(canonical_doc_id):
        return _prov_rec(None, PROVENANCE_METADATA_ONLY, "unmatched_metadata_only", "Metadata-only holding — excluded under open-access license gate", "source_linked", EVIDENCE_STATE_METADATA_ONLY, SOURCE_KIND_METADATA_ONLY)
    cid = str(chunk_id or "").strip()
    if UPLOAD_CHUNK_RE.match(cid):
        ev = EVIDENCE_STATE_RETRIEVED_UNASSESSED if (reader_resolvable and hf_url) else EVIDENCE_STATE_UNAVAILABLE
        sk = SOURCE_KIND_VERIFIED_FULL_TEXT if ev == EVIDENCE_STATE_RETRIEVED_UNASSESSED else SOURCE_KIND_UNAVAILABLE
        return _prov_rec(None, PROVENANCE_CHUNK_UNMATCHED, "upload_chunk_unmatched", "Passage located — canonical chunk unmatched", "chunk_unmatched", ev, sk)
    if source_category == "pearson_catalogue_only":
        oa = is_open_access_profile()
        return _prov_rec(None, PROVENANCE_METADATA_ONLY, "unmatched_metadata_only", "Pearson catalogue-only — institutional login required", "source_linked", EVIDENCE_STATE_UNAVAILABLE if oa else EVIDENCE_STATE_AUTHORIZED_EXTERNAL, SOURCE_KIND_METADATA_ONLY if oa else SOURCE_KIND_INSTITUTIONAL)
    if source_category in {"toc_index_only_textbook", "missing_or_unsupported_source"} or not reader_resolvable:
        return _prov_rec(None, PROVENANCE_METADATA_ONLY, "unmatched_metadata_only", "Source linked — not independently audited", "source_linked", EVIDENCE_STATE_METADATA_ONLY, SOURCE_KIND_METADATA_ONLY)
    if (canonical_doc_id.startswith("textbooks/") and source_category != "oa_full_text_textbook") or not hf_url or not (text_passage or "").strip():
        return _prov_rec(None, PROVENANCE_METADATA_ONLY, "unmatched_metadata_only", "Source linked — not independently audited", "source_linked", EVIDENCE_STATE_METADATA_ONLY, SOURCE_KIND_METADATA_ONLY)
    if not cid or canonical_doc_id.startswith("upload_") or not CANONICAL_CHUNK_RE.match(cid):
        return _prov_rec(None, PROVENANCE_CHUNK_UNMATCHED, "missing_chunk_id" if not cid else "non_canonical_chunk_id", "Passage located — canonical chunk unmatched", "chunk_unmatched", EVIDENCE_STATE_RETRIEVED_UNASSESSED, SOURCE_KIND_VERIFIED_FULL_TEXT)
    if chunk_index is not None and len(chunk_index.get((canonical_doc_id, cid)) or ()) > 1:
        return _prov_rec(None, PROVENANCE_CHUNK_AMBIGUOUS, "ambiguous_chunk_id", "Passage located — ambiguous chunk ID", "chunk_unmatched", EVIDENCE_STATE_RETRIEVED_UNASSESSED, SOURCE_KIND_VERIFIED_FULL_TEXT)
    if not page_number or page_number < MIN_VALID_PAGE:
        return _prov_rec(None, PROVENANCE_CHUNK_UNMATCHED, "missing_page_number", "Passage located — page unverified", "chunk_unmatched", EVIDENCE_STATE_RETRIEVED_UNASSESSED, SOURCE_KIND_VERIFIED_FULL_TEXT)
    return _prov_rec(f"{canonical_doc_id}::{cid}", PROVENANCE_VERIFIED, "exact_unique_canonical_chunk", "Provenance verified (claim support unassessed)", "provenance_verified", EVIDENCE_STATE_AVAILABLE_FULL_TEXT, SOURCE_KIND_VERIFIED_FULL_TEXT)


def summarize_evidence_states(citations: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Compute authoritative turn-level 4-state and 6-state evidence summary."""
    counts = dict.fromkeys(sorted(ALL_EVIDENCE_STATES), 0)
    kind_counts = dict.fromkeys(sorted(ALL_SOURCE_KINDS), 0)
    eligible_docs, seen_docs, oa_only = [], set(), is_open_access_profile()

    for cite in citations or []:
        if not isinstance(cite, dict):
            continue
        state = str(cite.get("evidence_state") or "").strip()
        if state not in ALL_EVIDENCE_STATES:
            state = classify_evidence_state(cite, open_access_only=oa_only)
        counts[state] += 1
        sk = str(cite.get("source_kind") or "").strip()
        if sk not in ALL_SOURCE_KINDS:
            sk = source_kind_for_evidence_state(state, cite)
        kind_counts[sk] += 1
        if state in FOLLOW_UP_ELIGIBLE_STATES and not cite.get("withdrawn"):
            doc_id = str(cite.get("doc_id") or "").strip()
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                eligible_docs.append(doc_id)

    full_text_count = sum(counts[s] for s in FULL_TEXT_EVIDENCE_STATES)
    order = (
        EVIDENCE_STATE_RELEVANT_SUPPORTING,
        EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
        EVIDENCE_STATE_RETRIEVED_UNASSESSED,
        EVIDENCE_STATE_AUTHORIZED_EXTERNAL,
        EVIDENCE_STATE_METADATA_ONLY,
    )
    turn_state = next((s for s in order if counts[s] > 0), EVIDENCE_STATE_UNAVAILABLE)
    turn_sk = source_kind_for_evidence_state(turn_state)
    return {
        "turn_evidence_state": turn_state,
        "turn_evidence_state_label": EVIDENCE_STATE_LABELS[turn_state],
        "turn_source_kind": turn_sk,
        "turn_source_kind_label": SOURCE_KIND_LABELS[turn_sk],
        "evidence_backed": full_text_count > 0,
        "full_text_passage_count": full_text_count,
        "state_counts": counts,
        "source_kind_counts": kind_counts,
        "follow_up_eligible_docs": eligible_docs,
    }


def build_grounding_trace(
    *,
    route: str,
    anchor_id: str | None,
    anchor_label: str | None,
    hops: int,
    citations: list[dict[str, Any]],
    provider: str,
    latency_s: float,
    latency_ms: int,
) -> dict[str, Any]:
    """Assemble the trace dictionary strictly synced with the unified provenance contract."""
    dict_cites = [c for c in citations if isinstance(c, dict)]
    withdrawn_only = bool(dict_cites) and all(c.get("withdrawn") for c in dict_cites)
    summary = summarize_evidence_states(dict_cites)
    turn_state = summary["turn_evidence_state"]
    trace_map: dict[str, tuple[str, str, str, str, str]] = {
        EVIDENCE_STATE_RELEVANT_SUPPORTING: ("Relevant supporting passage · Verified full-text", "verified", "relevant_supporting_passage", PROVENANCE_VERIFIED, "Graph-Assisted Traversal (OKF + Relevant Supporting Passages)"),
        EVIDENCE_STATE_AVAILABLE_FULL_TEXT: ("Provenance verified · Claim support unassessed", "verified", "provenance_verified_claim_unassessed", PROVENANCE_VERIFIED, "Graph-Assisted Traversal (OKF + Available Full-Text Passages)"),
        EVIDENCE_STATE_RETRIEVED_UNASSESSED: ("Retrieved passage · Support unassessed", "partial", "retrieved_unassessed_support", PROVENANCE_CHUNK_UNMATCHED, "Graph-Assisted Traversal (OKF + Retrieved Unassessed Passages)"),
        EVIDENCE_STATE_AUTHORIZED_EXTERNAL: ("Authorized external link · No local full-text passage", "source_linked", "authorized_external_link", PROVENANCE_METADATA_ONLY, "Graph-Assisted Traversal (OKF + Authorized External Link)"),
        EVIDENCE_STATE_METADATA_ONLY: ("Metadata only · No full-text passage evidence", "source_linked", "metadata_only_reference", PROVENANCE_METADATA_ONLY, "Graph-Assisted Traversal (OKF + Metadata-Only Reference)"),
    }
    if withdrawn_only:
        badge, state, detail, prov_status, mode = ("Source withdrawn · Unavailable", "unmatched", "source_withdrawn", PROVENANCE_WITHDRAWN, "Withdrawn Source Notice")
    elif turn_state in trace_map:
        badge, state, detail, prov_status, mode = trace_map[turn_state]
    elif anchor_id:
        badge, state, detail, prov_status, mode = ("Concept resolved · No supporting full-text passage", "partial", "no_direct_passage", PROVENANCE_NO_PASSAGE, "Graph-Assisted Traversal (OKF Only)")
    else:
        badge, state, detail, prov_status, mode = ("No graph match or supporting passage", "unmatched", "no_graph_match", PROVENANCE_NONE, "Direct Abstention / Catalog Fallback")

    return {
        "intent": route,
        "concept_id": anchor_id,
        "concept_label": anchor_label,
        "graph_hops": hops,
        "retrieval_mode": mode,
        "provider": provider or "pending",
        "grounded_passages": summary["full_text_passage_count"],
        "evidence_backed": summary["evidence_backed"],
        "source_kind": summary["turn_source_kind"],
        "source_kind_label": summary["turn_source_kind_label"],
        "source_kind_counts": summary["source_kind_counts"],
        "evidence_state": turn_state,
        "evidence_state_label": EVIDENCE_STATE_LABELS[turn_state],
        "evidence_state_counts": summary["state_counts"],
        "follow_up_eligible_docs": summary["follow_up_eligible_docs"],
        "grounding_status": state,
        "grounding_detail": detail,
        "grounding_badge": badge,
        "provenance_status": prov_status,
        "claim_support_status": "supported" if turn_state == EVIDENCE_STATE_RELEVANT_SUPPORTING else CLAIM_SUPPORT_NOT_ASSESSED,
        "reader_page_verified": False,
        "explanation_status": "general_explanation" if route == "GENERAL_EXPLANATION" else "route_specific",
        "latency_s": latency_s,
        "latency_ms": latency_ms,
    }


__all__ = [
    "ALL_EVIDENCE_STATES", "ALL_SOURCE_KINDS", "CANONICAL_CHUNK_RE", "CLAIM_SUPPORT_NOT_ASSESSED",
    "DOCUMENT_PAGE_MAP", "EVIDENCE_STATE_AUTHORIZED_EXTERNAL", "EVIDENCE_STATE_AVAILABLE_FULL_TEXT",
    "EVIDENCE_STATE_LABELS", "EVIDENCE_STATE_METADATA_ONLY", "EVIDENCE_STATE_RELEVANT_SUPPORTING",
    "EVIDENCE_STATE_RETRIEVED_UNASSESSED", "EVIDENCE_STATE_UNAVAILABLE", "FOLLOW_UP_ELIGIBLE_STATES",
    "FULL_TEXT_EVIDENCE_STATES", "PROVENANCE_CHUNK_AMBIGUOUS", "PROVENANCE_CHUNK_UNMATCHED",
    "PROVENANCE_METADATA_ONLY", "PROVENANCE_NONE", "PROVENANCE_NO_PASSAGE", "PROVENANCE_VERIFIED",
    "PROVENANCE_WITHDRAWN", "SOURCE_KIND_INSTITUTIONAL", "SOURCE_KIND_LABELS",
    "SOURCE_KIND_METADATA_ONLY", "SOURCE_KIND_UNAVAILABLE", "SOURCE_KIND_VERIFIED_FULL_TEXT",
    "UPLOAD_CHUNK_RE", "build_chunk_provenance_index", "build_grounding_trace",
    "classify_evidence_state", "d14_canonical_oa_url", "format_canonical_title",
    "is_d14_approved_oa", "is_d14_excluded_commercial", "is_follow_up_eligible",
    "load_d14_source_registry", "lookup_d14_source", "norm_text_hash", "ostep_chapter_info",
    "printed_to_pdf_page", "resolve_page_provenance", "source_kind_for_evidence_state",
    "summarize_evidence_states", "verify_chunk_provenance",
]

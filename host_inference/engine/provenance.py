"""Canonical chunk provenance verification and grounding trace assembly.

One concern: verify unique canonical ``chunk_id`` provenance without mapping
or guessing across same-page chunks, and emit structured provenance vs
claim-support status so provenance checks are never mislabeled as semantic
claim support.
"""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any

from .docmap import hf_doc_path

PROVENANCE_HASH_LEN = 16
CANONICAL_CHUNK_RE = re.compile(r"^(?:chunk_\d+|[a-z0-9_]+_seed_\d+)$", re.I)
UPLOAD_CHUNK_RE = re.compile(r"^upload_[0-9a-f]+_p\d+_\d+$", re.I)

# Grounding / provenance status constants (provenance-verified != claim-supported).
CLAIM_SUPPORT_NOT_ASSESSED = "not_assessed"
PROVENANCE_VERIFIED = "provenance_verified"
PROVENANCE_CHUNK_UNMATCHED = "chunk_unmatched"
PROVENANCE_CHUNK_AMBIGUOUS = "chunk_ambiguous"
PROVENANCE_METADATA_ONLY = "metadata_only"
PROVENANCE_WITHDRAWN = "withdrawn"
PROVENANCE_NO_PASSAGE = "no_passage"
PROVENANCE_NONE = "none"


def norm_text_hash(text: str) -> str:
    """Stable short hash of whitespace-normalized passage text."""
    norm = re.sub(r"\s+", " ", (text or "").strip())
    return sha256(norm.encode("utf-8")).hexdigest()[:PROVENANCE_HASH_LEN]


def build_chunk_provenance_index(
    nodes: dict[str, dict[str, Any]],
) -> dict[tuple[str, str], set[str]]:
    """Map ``(canonical_doc_id, chunk_id)`` to distinct passage text hashes."""
    index: dict[tuple[str, str], set[str]] = {}
    for node in nodes.values():
        for src in node.get("sources") or []:
            if not isinstance(src, dict):
                continue
            raw_doc = str(src.get("doc_id") or "").strip()
            chunk_id = str(src.get("chunk_id") or "").strip()
            if not raw_doc or not chunk_id:
                continue
            canonical_doc = hf_doc_path(raw_doc)
            passage = str(src.get("text_passage") or "").strip()
            index.setdefault((canonical_doc, chunk_id), set()).add(norm_text_hash(passage))
    return index


def _provenance_record(
    *,
    canonical_passage_id: str | None,
    provenance_status: str,
    chunk_provenance_match: str,
    verification_status: str,
    status_level: str,
) -> dict[str, Any]:
    return {
        "canonical_passage_id": canonical_passage_id,
        "provenance_status": provenance_status,
        "chunk_provenance_match": chunk_provenance_match,
        "claim_support_status": CLAIM_SUPPORT_NOT_ASSESSED,
        "verification_status": verification_status,
        "status_level": status_level,
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
    """Verify canonical ``chunk_id`` uniqueness and return provenance metadata."""
    del raw_doc_id  # Retained in signature for caller traceability.
    if all_withdrawn:
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_WITHDRAWN,
            chunk_provenance_match="withdrawn",
            verification_status="Withdrawn — unavailable",
            status_level="withdrawn",
        )

    cid = str(chunk_id or "").strip()
    if UPLOAD_CHUNK_RE.match(cid):
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_CHUNK_UNMATCHED,
            chunk_provenance_match="upload_chunk_unmatched",
            verification_status="Passage located — canonical chunk unmatched",
            status_level="chunk_unmatched",
        )

    non_fulltext_categories = {
        "toc_index_only_textbook",
        "pearson_catalogue_only",
        "missing_or_unsupported_source",
    }
    if source_category in non_fulltext_categories or not reader_resolvable:
        is_textbook_ref = canonical_doc_id.startswith("textbooks/")
        status_msg = (
            "TOC/index metadata only — full text not indexed"
            if source_category == "toc_index_only_textbook"
            else (
                "Pearson catalogue-only — institutional login required"
                if source_category == "pearson_catalogue_only"
                else (
                    "Source linked — not independently audited"
                    if is_textbook_ref
                    else "Source unavailable — metadata only"
                )
            )
        )
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_METADATA_ONLY,
            chunk_provenance_match="unmatched_metadata_only",
            verification_status=status_msg,
            status_level="source_linked",
        )

    is_unverified_textbook = (
        canonical_doc_id.startswith("textbooks/") and source_category != "oa_full_text_textbook"
    )
    if is_unverified_textbook or not hf_url or not (text_passage or "").strip():
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_METADATA_ONLY,
            chunk_provenance_match="unmatched_metadata_only",
            verification_status=(
                "Source linked — not independently audited"
                if is_unverified_textbook
                else "Metadata only — unverified"
            ),
            status_level="source_linked",
        )

    cid = str(chunk_id or "").strip()
    if not cid:
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_CHUNK_UNMATCHED,
            chunk_provenance_match="missing_chunk_id",
            verification_status="Passage located — canonical chunk unmatched",
            status_level="chunk_unmatched",
        )

    if canonical_doc_id.startswith("upload_"):
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_CHUNK_UNMATCHED,
            chunk_provenance_match="unverified_upload_source",
            verification_status="Passage located — unverified upload source",
            status_level="chunk_unmatched",
        )

    if UPLOAD_CHUNK_RE.match(cid) or not CANONICAL_CHUNK_RE.match(cid):
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_CHUNK_UNMATCHED,
            chunk_provenance_match=(
                "upload_chunk_unmatched" if UPLOAD_CHUNK_RE.match(cid) else "non_canonical_chunk_id"
            ),
            verification_status="Passage located — canonical chunk unmatched",
            status_level="chunk_unmatched",
        )

    if chunk_index is not None:
        hashes = chunk_index.get((canonical_doc_id, cid))
        if hashes is not None and len(hashes) > 1:
            return _provenance_record(
                canonical_passage_id=None,
                provenance_status=PROVENANCE_CHUNK_AMBIGUOUS,
                chunk_provenance_match="ambiguous_chunk_id",
                verification_status="Passage located — ambiguous chunk ID",
                status_level="chunk_unmatched",
            )

    if not page_number or page_number <= 0:
        return _provenance_record(
            canonical_passage_id=None,
            provenance_status=PROVENANCE_CHUNK_UNMATCHED,
            chunk_provenance_match="missing_page_number",
            verification_status="Passage located — page unverified",
            status_level="chunk_unmatched",
        )

    return _provenance_record(
        canonical_passage_id=f"{canonical_doc_id}::{cid}",
        provenance_status=PROVENANCE_VERIFIED,
        chunk_provenance_match="exact_unique_canonical_chunk",
        verification_status="Provenance verified (claim support unassessed)",
        status_level="provenance_verified",
    )


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
    """Assemble the trace dictionary distinguishing provenance from claim support."""
    dict_cites = [c for c in citations if isinstance(c, dict)]
    withdrawn_cites = [c for c in dict_cites if c.get("withdrawn")]
    valid_cites = [
        c
        for c in dict_cites
        if c.get("text_passage") or c.get("passage") or c.get("label") or c.get("doc_id")
    ]
    cites_count = len(valid_cites)
    has_withdrawn_only = bool(withdrawn_cites) and len(withdrawn_cites) == len(dict_cites)
    has_provenance_verified = any(
        c.get("provenance_status") == PROVENANCE_VERIFIED
        and c.get("source_type") == "ingested_pdf"
        and c.get("reader_resolvable", True)
        and c.get("url")
        and not c.get("withdrawn")
        for c in valid_cites
    )
    has_unmatched_pdf = any(
        (
            c.get("provenance_status") == PROVENANCE_CHUNK_UNMATCHED
            or (
                c.get("source_type") == "ingested_pdf"
                and c.get("reader_resolvable", True)
                and c.get("url")
            )
        )
        and not c.get("withdrawn")
        for c in valid_cites
    )

    if has_withdrawn_only:
        badge = "Source withdrawn · Unavailable"
        state = "unmatched"
        detail = "source_withdrawn"
        prov_status = PROVENANCE_WITHDRAWN
        mode = "Withdrawn Source Notice"
    elif anchor_id and cites_count > 0:
        if has_provenance_verified:
            badge = "Provenance verified · Claim support unassessed"
            state = "verified"
            detail = "provenance_verified_claim_unassessed"
            prov_status = PROVENANCE_VERIFIED
            mode = "Graph-Assisted Traversal (OKF + Provenance-Verified Passages)"
        elif has_unmatched_pdf:
            badge = "Passage located (canonical chunk unmatched) · Claim support unassessed"
            state = "partial"
            detail = "chunk_unmatched_claim_unassessed"
            prov_status = PROVENANCE_CHUNK_UNMATCHED
            mode = "Graph-Assisted Traversal (OKF + Unmatched Chunk Passages)"
        else:
            badge = "Metadata only · Provenance and claim support unassessed"
            state = "source_linked"
            detail = "metadata_only_unassessed"
            prov_status = PROVENANCE_METADATA_ONLY
            mode = "Graph-Assisted Traversal (OKF + Source-Linked Metadata)"
    elif anchor_id:
        badge = "OKF structure resolved · No direct passage"
        state = "partial"
        detail = "no_direct_passage"
        prov_status = PROVENANCE_NO_PASSAGE
        mode = "Graph-Assisted Traversal (OKF Only)"
    elif cites_count > 0:
        badge = "No Verified Graph Match · Lexical literature fallback"
        state = "general"
        detail = "no_graph_match"
        prov_status = PROVENANCE_NONE
        mode = "Lexical Literature Retrieval (Unindexed Concept)"
    else:
        badge = "No Verified Graph Match · Clean abstention"
        state = "unmatched"
        detail = "no_graph_match"
        prov_status = PROVENANCE_NONE
        mode = "Direct Abstention / Catalog Fallback"

    return {
        "intent": route,
        "concept_id": anchor_id,
        "concept_label": anchor_label,
        "graph_hops": hops,
        "retrieval_mode": mode,
        "provider": provider or "Deterministic Rule-Based OKF Fallback",
        "grounded_passages": cites_count,
        "grounding_status": state,
        "grounding_detail": detail,
        "grounding_badge": badge,
        "provenance_status": prov_status,
        "claim_support_status": CLAIM_SUPPORT_NOT_ASSESSED,
        "latency_s": latency_s,
        "latency_ms": latency_ms,
    }


__all__ = [
    "CANONICAL_CHUNK_RE",
    "CLAIM_SUPPORT_NOT_ASSESSED",
    "PROVENANCE_CHUNK_AMBIGUOUS",
    "PROVENANCE_CHUNK_UNMATCHED",
    "PROVENANCE_METADATA_ONLY",
    "PROVENANCE_NONE",
    "PROVENANCE_NO_PASSAGE",
    "PROVENANCE_VERIFIED",
    "PROVENANCE_WITHDRAWN",
    "UPLOAD_CHUNK_RE",
    "build_chunk_provenance_index",
    "build_grounding_trace",
    "norm_text_hash",
    "verify_chunk_provenance",
]

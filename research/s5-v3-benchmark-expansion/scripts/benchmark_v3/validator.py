"""Programmatic validator for the S5-v3 proposed query benchmark."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .constants import (
    ANSWERABILITY_STATUS_UNVERIFIED,
    CAT_CROSS_DOC_MULTI,
    CAT_NEGATIVE_CONTROL,
    CAT_SAME_DOC_MULTI,
    FORBIDDEN_PUBLIC_TEXT_KEYS,
    MAX_QUERY_COUNT,
    MIN_CROSS_DOC_SOURCES,
    MIN_MULTI_PASSAGE_EVIDENCE,
    MIN_QUERY_COUNT,
    MIN_QUERY_TOKENS,
    PROVENANCE_STATUS_PROPOSED,
    SHA256_HEX_LENGTH,
    VALID_CATEGORIES,
    VALID_GRAPH_REGIMES,
    VALID_SPLITS,
)
from .graph_anchors import GraphAnchorIndex
from .leakage import check_dev_test_leakage, check_v21_reuse, normalized_text
from .schema import CorpusPassageMeta, QuerySpec, ValidationIssue, ValidationReport

_HEX_RE = re.compile(r"^[0-9a-f]+$")


def _check_no_forbidden_keys(
    payload: Any,
    query_id: str,
    issues: list[ValidationIssue],
) -> None:
    """Ensure no raw copyrighted passage text keys exist in public payload."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN_PUBLIC_TEXT_KEYS:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        query_id=query_id,
                        code="FORBIDDEN_RAW_TEXT_FIELD",
                        message=f"Forbidden raw text key '{key}' in manifest.",
                    )
                )
            _check_no_forbidden_keys(value, query_id, issues)
    elif isinstance(payload, list):
        for item in payload:
            _check_no_forbidden_keys(item, query_id, issues)


def _validate_evidence_refs(
    query: QuerySpec,
    corpus_index: dict[str, CorpusPassageMeta],
    issues: list[ValidationIssue],
) -> None:
    """Verify every supporting_evidence ref matches Corpus v3 metadata."""
    seen_pids: set[str] = set()
    for ref in query.supporting_evidence:
        if ref.passage_id in seen_pids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="DUPLICATE_EVIDENCE_PASSAGE",
                    message=f"Duplicate passage_id {ref.passage_id}.",
                )
            )
        seen_pids.add(ref.passage_id)

        if ref.page_start < 1 or ref.page_end < ref.page_start:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="INVALID_PAGE_RANGE",
                    message=(
                        f"Invalid page range {ref.page_start}-{ref.page_end} "
                        f"for {ref.passage_id}."
                    ),
                )
            )
        if (
            len(ref.passage_sha256) != SHA256_HEX_LENGTH
            or not _HEX_RE.match(ref.passage_sha256)
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="INVALID_PASSAGE_SHA256",
                    message=f"Malformed SHA-256 for {ref.passage_id}.",
                )
            )

        meta = corpus_index.get(ref.passage_id)
        if meta is None:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="PASSAGE_NOT_IN_CORPUS",
                    message=(
                        f"passage_id '{ref.passage_id}' does not exist in "
                        "Corpus v3."
                    ),
                )
            )
            continue
        if meta.source_doc_id != ref.source_doc_id:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="SOURCE_DOC_MISMATCH",
                    message=(
                        f"{ref.passage_id} source_doc_id={ref.source_doc_id} "
                        f"!= corpus {meta.source_doc_id}."
                    ),
                )
            )
        if (meta.page_start, meta.page_end) != (ref.page_start, ref.page_end):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="PAGE_REF_MISMATCH",
                    message=(
                        f"{ref.passage_id} pages {ref.page_start}-{ref.page_end} "
                        f"!= corpus {meta.page_start}-{meta.page_end}."
                    ),
                )
            )
        if meta.passage_sha256 != ref.passage_sha256:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="PASSAGE_SHA256_MISMATCH",
                    message=f"{ref.passage_id} passage_sha256 mismatch.",
                )
            )


def _validate_necessity_and_negative_controls(
    query: QuerySpec,
    issues: list[ValidationIssue],
) -> None:
    """Enforce negative-control and multi-passage/cross-doc consistency."""
    ev_by_id = {ref.passage_id: ref for ref in query.supporting_evidence}
    min_set = query.minimum_required_evidence_set

    if not query.single_passage_shortcut_check.rationale.strip():
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="EMPTY_SHORTCUT_RATIONALE",
                message="single_passage_shortcut_check.rationale is empty.",
            )
        )

    for pid in min_set:
        if pid not in ev_by_id:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="MIN_EVIDENCE_NOT_IN_SUPPORTING",
                    message=(
                        f"minimum_required_evidence_set entry '{pid}' not in "
                        "supporting_evidence."
                    ),
                )
            )

    if query.category == CAT_NEGATIVE_CONTROL:
        if query.answer_exists_in_eligible_corpus:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="NEG_CONTROL_MARKED_ANSWERABLE",
                    message="Negative control must have answer_exists=False.",
                )
            )
        if query.supporting_evidence or min_set:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="NEG_CONTROL_HAS_EVIDENCE",
                    message="Negative control must have empty evidence lists.",
                )
            )
        if query.multi_document_truly_necessary:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="NEG_CONTROL_MULTI_DOC",
                    message="Negative control cannot require multi-document.",
                )
            )
        return

    if not query.answer_exists_in_eligible_corpus:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="POSITIVE_QUERY_UNANSWERABLE",
                message="Non-negative-control must have answer_exists=True.",
            )
        )
    if not query.supporting_evidence or not min_set:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="MISSING_REQUIRED_EVIDENCE",
                message="Positive query requires >= 1 evidence passage.",
            )
        )

    min_docs = {
        ev_by_id[pid].source_doc_id for pid in min_set if pid in ev_by_id
    }
    if query.category == CAT_SAME_DOC_MULTI:
        if len(min_set) < MIN_MULTI_PASSAGE_EVIDENCE:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="SAME_DOC_MULTI_TOO_FEW_PASSAGES",
                    message="same_doc_multi_passage requires >= 2 passages.",
                )
            )
        if len(min_docs) != 1:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="SAME_DOC_MULTI_MULTIPLE_DOCS",
                    message="same_doc_multi_passage must span exactly 1 doc.",
                )
            )
        if query.multi_document_truly_necessary:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="SAME_DOC_MARKED_MULTI_DOC",
                    message="same_doc_multi_passage cannot set multi_doc=True.",
                )
            )
        if query.single_passage_shortcut_check.shortcut_found:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="MULTI_PASSAGE_SHORTCUT_FOUND",
                    message="same_doc_multi_passage has shortcut_found=True.",
                )
            )

    if query.category == CAT_CROSS_DOC_MULTI:
        if not query.multi_document_truly_necessary:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="CROSS_DOC_FLAG_FALSE",
                    message="cross_doc_multi_passage must set multi_doc=True.",
                )
            )
        if len(min_docs) < MIN_CROSS_DOC_SOURCES:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="CROSS_DOC_TOO_FEW_SOURCES",
                    message="cross_doc_multi_passage requires >= 2 source docs.",
                )
            )
        if query.single_passage_shortcut_check.shortcut_found:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="CROSS_DOC_SHORTCUT_FOUND",
                    message="cross_doc_multi_passage has shortcut_found=True.",
                )
            )

    if query.multi_document_truly_necessary:
        if len(min_docs) < MIN_CROSS_DOC_SOURCES:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="MULTI_DOC_NECESSARY_SINGLE_SOURCE",
                    message="multi_document_truly_necessary needs >= 2 docs.",
                )
            )
        if query.single_passage_shortcut_check.shortcut_found:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="MULTI_DOC_SHORTCUT_CONTRADICTION",
                    message="multi_doc=True contradicts shortcut_found=True.",
                )
            )


def _validate_single_query(
    query: QuerySpec,
    corpus_index: dict[str, CorpusPassageMeta],
    graph_index: GraphAnchorIndex | None,
    issues: list[ValidationIssue],
) -> None:
    """Validate one QuerySpec against schema, provenance, corpus, and graph."""
    if len(normalized_text(query.query_text).split()) < MIN_QUERY_TOKENS:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="QUERY_TOO_SHORT",
                message=f"Query has fewer than {MIN_QUERY_TOKENS} tokens.",
            )
        )
    if query.split not in VALID_SPLITS:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="INVALID_SPLIT",
                message=f"Invalid split '{query.split}'.",
            )
        )
    if query.category not in VALID_CATEGORIES:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="INVALID_CATEGORY",
                message=f"Invalid category '{query.category}'.",
            )
        )
    if query.graph_anchor_regime not in VALID_GRAPH_REGIMES:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="INVALID_GRAPH_REGIME",
                message=f"Invalid graph_anchor_regime '{query.graph_anchor_regime}'.",
            )
        )
    if not query.exact_information_need.strip():
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="EMPTY_INFO_NEED",
                message="exact_information_need must be non-empty.",
            )
        )
    if query.provenance_status != PROVENANCE_STATUS_PROPOSED:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="INVALID_PROVENANCE_STATUS",
                message=(
                    f"provenance_status must be '{PROVENANCE_STATUS_PROPOSED}', "
                    f"got '{query.provenance_status}'."
                ),
            )
        )
    if query.answerability_verification_status != ANSWERABILITY_STATUS_UNVERIFIED:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id=query.query_id,
                code="INVALID_ANSWERABILITY_STATUS",
                message=(
                    "answerability_verification_status must be "
                    f"'{ANSWERABILITY_STATUS_UNVERIFIED}'."
                ),
            )
        )

    _validate_evidence_refs(query, corpus_index, issues)
    _validate_necessity_and_negative_controls(query, issues)

    if graph_index is not None:
        computed_regime, computed_matches = graph_index.classify_regime(
            query.query_text
        )
        if computed_regime != query.graph_anchor_regime:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=query.query_id,
                    code="GRAPH_REGIME_MISMATCH",
                    message=(
                        f"Declared regime='{query.graph_anchor_regime}' != "
                        f"computed='{computed_regime}' "
                        f"(matches={list(computed_matches)})."
                    ),
                )
            )


def validate_benchmark(
    queries: list[QuerySpec],
    corpus_index: dict[str, CorpusPassageMeta],
    graph_index: GraphAnchorIndex | None = None,
    v21_queries: list[tuple[str, str]] | None = None,
    enforce_size_bounds: bool = True,
) -> ValidationReport:
    """Run all schema, provenance, evidence, graph, and leakage checks."""
    issues: list[ValidationIssue] = []

    if enforce_size_bounds and not (
        MIN_QUERY_COUNT <= len(queries) <= MAX_QUERY_COUNT
    ):
        issues.append(
            ValidationIssue(
                severity="ERROR",
                query_id="__BENCHMARK__",
                code="QUERY_COUNT_OUT_OF_RANGE",
                message=(
                    f"Expected {MIN_QUERY_COUNT}-{MAX_QUERY_COUNT} queries, "
                    f"got {len(queries)}."
                ),
            )
        )

    seen_ids: set[str] = set()
    seen_texts: dict[str, str] = {}
    for q in queries:
        if q.query_id in seen_ids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=q.query_id,
                    code="DUPLICATE_QUERY_ID",
                    message=f"Duplicate query_id '{q.query_id}'.",
                )
            )
        seen_ids.add(q.query_id)

        q_norm = normalized_text(q.query_text)
        if q_norm in seen_texts:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=q.query_id,
                    code="DUPLICATE_QUERY_TEXT",
                    message=f"Duplicate query text with {seen_texts[q_norm]}.",
                )
            )
        seen_texts[q_norm] = q.query_id

        _check_no_forbidden_keys(q.to_dict(), q.query_id, issues)
        _validate_single_query(q, corpus_index, graph_index, issues)

    issues.extend(check_dev_test_leakage(queries))
    if v21_queries:
        issues.extend(check_v21_reuse(queries, v21_queries))

    return ValidationReport(
        issues=issues,
        total_queries=len(queries),
        split_counts=dict(Counter(q.split for q in queries)),
        category_counts=dict(Counter(q.category for q in queries)),
        regime_counts=dict(Counter(q.graph_anchor_regime for q in queries)),
    )

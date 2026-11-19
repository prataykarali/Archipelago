"""Programmatic validator for the S5-v3.1 proposed query benchmark."""

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
    FORBIDDEN_RELEVANCE_GRADE_KEYS,
    MAX_QUERY_COUNT,
    MIN_CROSS_DOC_SOURCES,
    MIN_MULTI_PASSAGE_EVIDENCE,
    MIN_QUERY_COUNT,
    MIN_QUERY_TOKENS,
    PROVENANCE_STATUS_PROPOSED,
    PROVISIONAL_STATUS,
    SHA256_HEX_LENGTH,
    VALID_CATEGORIES,
    VALID_GRAPH_REGIMES,
    VALID_SPLITS,
)
from .graph_anchors import GraphAnchorIndex
from .leakage import check_dev_test_leakage, check_v21_reuse, normalized_text
from .schema import (
    CorpusPassageMeta,
    QuerySpec,
    ValidationIssue,
    ValidationReport,
)

_HEX_RE = re.compile(r"^[0-9a-f]+$")


def _check_no_forbidden_keys(
    payload: Any,
    query_id: str,
    issues: list[ValidationIssue],
) -> None:
    """Reject raw passage text keys and relevance grade keys in public JSON."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            low = str(key).lower()
            if low in FORBIDDEN_PUBLIC_TEXT_KEYS:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        query_id,
                        "FORBIDDEN_RAW_TEXT_FIELD",
                        f"Forbidden raw text key '{key}' in public manifest.",
                    )
                )
            if low in FORBIDDEN_RELEVANCE_GRADE_KEYS:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        query_id,
                        "FORBIDDEN_RELEVANCE_GRADE_FIELD",
                        f"Forbidden relevance grade key '{key}' in manifest.",
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
    """Verify every supporting_evidence ref matches Corpus v3.1 metadata."""
    seen_pids: set[str] = set()
    for ref in query.supporting_evidence:
        if ref.passage_id in seen_pids:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "DUPLICATE_EVIDENCE_PASSAGE",
                    f"Duplicate passage_id {ref.passage_id}.",
                )
            )
        seen_pids.add(ref.passage_id)

        if ref.page_start is not None and (
            ref.page_start < 1
            or ref.page_end is None
            or ref.page_end < ref.page_start
        ):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "INVALID_PAGE_RANGE",
                    f"Invalid page range {ref.page_start}-{ref.page_end}.",
                )
            )

        if (
            len(ref.passage_sha256) != SHA256_HEX_LENGTH
            or not _HEX_RE.match(ref.passage_sha256)
        ):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "INVALID_PASSAGE_SHA256",
                    f"Malformed SHA-256 for {ref.passage_id}.",
                )
            )

        meta = corpus_index.get(ref.passage_id)
        if meta is None:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "PASSAGE_NOT_IN_CORPUS",
                    f"passage_id '{ref.passage_id}' not in Corpus v3.1.",
                )
            )
            continue
        if meta.source_doc_id != ref.source_doc_id:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "SOURCE_DOC_MISMATCH",
                    f"{ref.passage_id} source_doc_id mismatch.",
                )
            )
        if (meta.page_start, meta.page_end) != (ref.page_start, ref.page_end):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "PAGE_REF_MISMATCH",
                    f"{ref.passage_id} page refs mismatch corpus.",
                )
            )
        if meta.passage_sha256 != ref.passage_sha256:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "PASSAGE_SHA256_MISMATCH",
                    f"{ref.passage_id} passage_sha256 mismatch.",
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
                "ERROR",
                query.query_id,
                "EMPTY_SHORTCUT_RATIONALE",
                "single_passage_shortcut_check.rationale is empty.",
            )
        )

    for pid in min_set:
        if pid not in ev_by_id:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "MIN_EVIDENCE_NOT_IN_SUPPORTING",
                    f"min evidence '{pid}' not in supporting_evidence.",
                )
            )

    if query.category == CAT_NEGATIVE_CONTROL:
        if query.answer_exists_in_eligible_corpus:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "NEG_CONTROL_MARKED_ANSWERABLE",
                    "Negative control must have answer_exists=False.",
                )
            )
        if query.supporting_evidence or min_set:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "NEG_CONTROL_HAS_EVIDENCE",
                    "Negative control must have empty evidence lists.",
                )
            )
        if query.multi_document_truly_necessary:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "NEG_CONTROL_MULTI_DOC",
                    "Negative control cannot require multi-document.",
                )
            )
        return

    if not query.answer_exists_in_eligible_corpus:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "POSITIVE_QUERY_UNANSWERABLE",
                "Non-negative-control must have answer_exists=True.",
            )
        )
    if not query.supporting_evidence or not min_set:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "MISSING_REQUIRED_EVIDENCE",
                "Positive query requires >= 1 evidence passage.",
            )
        )

    min_docs = {
        ev_by_id[pid].source_doc_id for pid in min_set if pid in ev_by_id
    }
    if query.category == CAT_SAME_DOC_MULTI:
        if len(min_set) < MIN_MULTI_PASSAGE_EVIDENCE:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "SAME_DOC_MULTI_TOO_FEW_PASSAGES",
                    "same_doc_multi_passage requires >= 2 passages.",
                )
            )
        if len(min_docs) != 1:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "SAME_DOC_MULTI_MULTIPLE_DOCS",
                    "same_doc_multi_passage must span exactly 1 doc.",
                )
            )
        if query.multi_document_truly_necessary:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "SAME_DOC_MARKED_MULTI_DOC",
                    "same_doc_multi_passage cannot set multi_doc=True.",
                )
            )
        if query.single_passage_shortcut_check.shortcut_found:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "MULTI_PASSAGE_SHORTCUT_FOUND",
                    "same_doc_multi_passage has shortcut_found=True.",
                )
            )

    if query.category == CAT_CROSS_DOC_MULTI:
        if not query.multi_document_truly_necessary:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "CROSS_DOC_FLAG_FALSE",
                    "cross_doc_multi_passage must set multi_doc=True.",
                )
            )
        if len(min_docs) < MIN_CROSS_DOC_SOURCES:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "CROSS_DOC_TOO_FEW_SOURCES",
                    "cross_doc_multi_passage requires >= 2 source docs.",
                )
            )
        if query.single_passage_shortcut_check.shortcut_found:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "CROSS_DOC_SHORTCUT_FOUND",
                    "cross_doc_multi_passage has shortcut_found=True.",
                )
            )

    if query.multi_document_truly_necessary:
        if len(min_docs) < MIN_CROSS_DOC_SOURCES:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "MULTI_DOC_NECESSARY_SINGLE_SOURCE",
                    "multi_document_truly_necessary needs >= 2 docs.",
                )
            )
        if query.single_passage_shortcut_check.shortcut_found:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    query.query_id,
                    "MULTI_DOC_SHORTCUT_CONTRADICTION",
                    "multi_doc=True contradicts shortcut_found=True.",
                )
            )


def _validate_single_query(
    query: QuerySpec,
    corpus_index: dict[str, CorpusPassageMeta],
    graph_index: GraphAnchorIndex | None,
    issues: list[ValidationIssue],
) -> None:
    """Validate one QuerySpec against schema, provisional status, corpus."""
    if len(normalized_text(query.query_text).split()) < MIN_QUERY_TOKENS:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "QUERY_TOO_SHORT",
                f"Query has fewer than {MIN_QUERY_TOKENS} tokens.",
            )
        )
    if query.split not in VALID_SPLITS:
        issues.append(
            ValidationIssue(
                "ERROR", query.query_id, "INVALID_SPLIT", "Bad split."
            )
        )
    if query.category not in VALID_CATEGORIES:
        issues.append(
            ValidationIssue(
                "ERROR", query.query_id, "INVALID_CATEGORY", "Bad category."
            )
        )
    if query.category_status != PROVISIONAL_STATUS:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "INVALID_CATEGORY_STATUS",
                f"category_status must be '{PROVISIONAL_STATUS}'.",
            )
        )
    if query.necessity_status != PROVISIONAL_STATUS:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "INVALID_NECESSITY_STATUS",
                f"necessity_status must be '{PROVISIONAL_STATUS}'.",
            )
        )
    if query.graph_anchor_regime not in VALID_GRAPH_REGIMES:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "INVALID_GRAPH_REGIME",
                "Bad graph_anchor_regime.",
            )
        )
    if not query.exact_information_need.strip():
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "EMPTY_INFO_NEED",
                "exact_information_need must be non-empty.",
            )
        )
    if query.provenance_status != PROVENANCE_STATUS_PROPOSED:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "INVALID_PROVENANCE_STATUS",
                f"provenance_status must be '{PROVENANCE_STATUS_PROPOSED}'.",
            )
        )
    if query.answerability_verification_status != ANSWERABILITY_STATUS_UNVERIFIED:
        issues.append(
            ValidationIssue(
                "ERROR",
                query.query_id,
                "INVALID_ANSWERABILITY_STATUS",
                f"answerability must be '{ANSWERABILITY_STATUS_UNVERIFIED}'.",
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
                    "ERROR",
                    query.query_id,
                    "GRAPH_REGIME_MISMATCH",
                    (
                        f"Declared='{query.graph_anchor_regime}' != "
                        f"computed='{computed_regime}' ({list(computed_matches)})."
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
    """Run all schema, provisional-status, evidence, graph, and leakage checks."""
    issues: list[ValidationIssue] = []

    if enforce_size_bounds and not (
        MIN_QUERY_COUNT <= len(queries) <= MAX_QUERY_COUNT
    ):
        issues.append(
            ValidationIssue(
                "ERROR",
                "__BENCHMARK__",
                "QUERY_COUNT_OUT_OF_RANGE",
                f"Expected {MIN_QUERY_COUNT}-{MAX_QUERY_COUNT}, got {len(queries)}.",
            )
        )

    seen_ids: set[str] = set()
    seen_texts: dict[str, str] = {}
    for q in queries:
        if q.query_id in seen_ids:
            issues.append(
                ValidationIssue(
                    "ERROR", q.query_id, "DUPLICATE_QUERY_ID", "Duplicate ID."
                )
            )
        seen_ids.add(q.query_id)
        q_norm = normalized_text(q.query_text)
        if q_norm in seen_texts:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    q.query_id,
                    "DUPLICATE_QUERY_TEXT",
                    f"Duplicates {seen_texts[q_norm]}.",
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
        domain_counts=dict(Counter(q.domain for q in queries)),
        regime_counts=dict(Counter(q.graph_anchor_regime for q in queries)),
    )

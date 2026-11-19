"""Dev/test split leakage and S5-v2.1 query reuse checks for S5-v3.1."""

from __future__ import annotations

import json
from pathlib import Path
import re

from .constants import (
    DEV_TEST_JACCARD_THRESHOLD,
    SPLIT_DEV,
    SPLIT_TEST,
    V21_REUSE_JACCARD_THRESHOLD,
)
from .schema import QuerySpec, ValidationIssue

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "why",
        "with",
    }
)


def content_tokens(text: str) -> frozenset[str]:
    """Extract lowercase content tokens excluding common stopwords."""
    return frozenset(
        tok for tok in _TOKEN_RE.findall(text.lower()) if tok not in _STOPWORDS
    )


def token_jaccard(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity over content tokens."""
    tokens_a = content_tokens(text_a)
    tokens_b = content_tokens(text_b)
    if not tokens_a and not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union)


def normalized_text(text: str) -> str:
    """Normalize text for exact-duplicate comparison."""
    return " ".join(_TOKEN_RE.findall(text.lower()))


def load_v21_queries(path: Path) -> list[tuple[str, str]]:
    """Load (query_id, query_text) tuples from frozen S5-v2.1 query specs."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    results: list[tuple[str, str]] = []
    for item in raw.get("queries", []):
        qid = str(item.get("query_id", ""))
        qtext = str(item.get("query_text", ""))
        if qid or qtext:
            results.append((qid, qtext))
    return results


def check_dev_test_leakage(
    queries: list[QuerySpec],
    jaccard_threshold: float = DEV_TEST_JACCARD_THRESHOLD,
) -> list[ValidationIssue]:
    """Detect exact/near-duplicate queries and evidence overlap across splits."""
    issues: list[ValidationIssue] = []
    dev_queries = [q for q in queries if q.split == SPLIT_DEV]
    test_queries = [q for q in queries if q.split == SPLIT_TEST]

    dev_evidence: dict[str, str] = {}
    for dq in dev_queries:
        for pid in dq.minimum_required_evidence_set:
            dev_evidence.setdefault(pid, dq.query_id)

    for tq in test_queries:
        tq_norm = normalized_text(tq.query_text)
        for dq in dev_queries:
            if tq_norm == normalized_text(dq.query_text):
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        query_id=tq.query_id,
                        code="DEV_TEST_EXACT_DUPLICATE",
                        message=(
                            f"Test query {tq.query_id} duplicates dev query "
                            f"{dq.query_id}."
                        ),
                    )
                )
            else:
                sim = token_jaccard(tq.query_text, dq.query_text)
                if sim >= jaccard_threshold:
                    issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            query_id=tq.query_id,
                            code="DEV_TEST_NEAR_DUPLICATE",
                            message=(
                                f"Test query {tq.query_id} has Jaccard={sim:.2f} "
                                f"with dev query {dq.query_id}."
                            ),
                        )
                    )
        for pid in tq.minimum_required_evidence_set:
            if pid in dev_evidence:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        query_id=tq.query_id,
                        code="DEV_TEST_EVIDENCE_OVERLAP",
                        message=(
                            f"Test query {tq.query_id} shares required evidence "
                            f"passage {pid} with dev query {dev_evidence[pid]}."
                        ),
                    )
                )
    return issues


def check_v21_reuse(
    queries: list[QuerySpec],
    v21_queries: list[tuple[str, str]],
    jaccard_threshold: float = V21_REUSE_JACCARD_THRESHOLD,
) -> list[ValidationIssue]:
    """Ensure zero S5-v2.1 query ID or text reuse in proposed S5-v3.1 queries."""
    issues: list[ValidationIssue] = []
    v21_ids = {qid for qid, _ in v21_queries}
    v21_norms = {normalized_text(text): qid for qid, text in v21_queries}

    for q in queries:
        if q.query_id in v21_ids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=q.query_id,
                    code="V21_ID_REUSE",
                    message=f"Query ID {q.query_id} reuses a frozen v2.1 ID.",
                )
            )
        q_norm = normalized_text(q.query_text)
        if q_norm in v21_norms:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    query_id=q.query_id,
                    code="V21_EXACT_TEXT_REUSE",
                    message=(
                        f"Query {q.query_id} duplicates frozen v2.1 query "
                        f"{v21_norms[q_norm]}."
                    ),
                )
            )
            continue
        for v21_id, v21_text in v21_queries:
            sim = token_jaccard(q.query_text, v21_text)
            if sim >= jaccard_threshold:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        query_id=q.query_id,
                        code="V21_NEAR_TEXT_REUSE",
                        message=(
                            f"Query {q.query_id} has Jaccard={sim:.2f} with "
                            f"frozen v2.1 query {v21_id}."
                        ),
                    )
                )
    return issues

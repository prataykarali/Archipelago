"""Exact (normalized SHA-256) and near-duplicate (n-gram Jaccard) detection."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import re

from .constants import (
    MAX_SHINGLE_POSTING_FREQ,
    MIN_TOKENS_FOR_NEAR_DUP,
    NEAR_DUP_JACCARD_THRESHOLD,
    SHINGLE_SIZE,
)
from .models import DeduplicationReport, DuplicatePair

NORMALIZE_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_for_dedup(text: str) -> str:
    """Normalize text for exact-duplicate hashing (lowercase, alnum, single space)."""
    lowered = text.lower()
    alnum = NORMALIZE_NON_ALNUM_RE.sub(" ", lowered)
    return WHITESPACE_RE.sub(" ", alnum).strip()


def compute_normalized_sha256(text: str) -> str:
    """Compute SHA-256 of normalized passage text."""
    normalized = normalize_for_dedup(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_passage_sha256(text: str) -> str:
    """Compute SHA-256 of canonical UTF-8 passage text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_shingles(text: str, shingle_size: int = SHINGLE_SIZE) -> frozenset[str]:
    """Extract deterministic word n-gram shingles from normalized text."""
    tokens = normalize_for_dedup(text).split()
    if len(tokens) < MIN_TOKENS_FOR_NEAR_DUP or len(tokens) < shingle_size:
        return frozenset()
    return frozenset(
        " ".join(tokens[i : i + shingle_size]) for i in range(len(tokens) - shingle_size + 1)
    )


def compute_jaccard_similarity(
    left: frozenset[str],
    right: frozenset[str],
) -> float:
    """Compute Jaccard similarity between two shingle sets."""
    if not left or not right:
        return 0.0
    union_size = len(left | right)
    if union_size == 0:
        return 0.0
    return len(left & right) / union_size


def detect_duplicates(
    passage_items: list[tuple[str, str, str]],
    near_dup_threshold: float = NEAR_DUP_JACCARD_THRESHOLD,
    shingle_size: int = SHINGLE_SIZE,
) -> tuple[DeduplicationReport, dict[str, str]]:
    """Detect exact and near-duplicates deterministically.

    Args:
        passage_items: Ordered list of (passage_id, text, normalized_text_sha256).
        near_dup_threshold: Minimum shingle Jaccard similarity for near-duplicates.
        shingle_size: Word n-gram width for Jaccard shingling.

    Returns:
        Tuple of (DeduplicationReport, canonical_map mapping passage_id -> canonical_id).
    """
    canonical_by_hash: dict[str, str] = {}
    canonical_map: dict[str, str] = {}
    exact_pairs: list[DuplicatePair] = []

    for passage_id, _text, norm_hash in passage_items:
        if norm_hash in canonical_by_hash:
            canonical_id = canonical_by_hash[norm_hash]
            canonical_map[passage_id] = canonical_id
            exact_pairs.append(
                DuplicatePair(
                    passage_id=passage_id,
                    matched_passage_id=canonical_id,
                    kind="exact",
                    similarity=1.0,
                )
            )
        else:
            canonical_by_hash[norm_hash] = passage_id
            canonical_map[passage_id] = passage_id

    shingles_by_id: dict[str, frozenset[str]] = {}
    inverted_index: dict[str, list[str]] = defaultdict(list)

    for passage_id, text, _norm_hash in passage_items:
        if canonical_map[passage_id] != passage_id:
            continue
        shingles = _extract_shingles(text, shingle_size=shingle_size)
        if not shingles:
            continue
        shingles_by_id[passage_id] = shingles
        for shingle in shingles:
            inverted_index[shingle].append(passage_id)

    candidate_pairs: set[tuple[str, str]] = set()
    for posting in inverted_index.values():
        if len(posting) <= 1 or len(posting) > MAX_SHINGLE_POSTING_FREQ:
            continue
        for idx_a in range(len(posting)):
            for idx_b in range(idx_a + 1, len(posting)):
                id_a = posting[idx_a]
                id_b = posting[idx_b]
                pair = (id_a, id_b) if id_a < id_b else (id_b, id_a)
                candidate_pairs.add(pair)

    near_pairs: list[DuplicatePair] = []
    for id_a, id_b in sorted(candidate_pairs):
        sim = compute_jaccard_similarity(shingles_by_id[id_a], shingles_by_id[id_b])
        if sim >= near_dup_threshold:
            near_pairs.append(
                DuplicatePair(
                    passage_id=id_b,
                    matched_passage_id=id_a,
                    kind="near",
                    similarity=round(sim, 4),
                )
            )

    report = DeduplicationReport(
        total_passages=len(passage_items),
        unique_normalized_hashes=len(canonical_by_hash),
        exact_duplicate_count=len(exact_pairs),
        exact_duplicate_pairs=tuple(exact_pairs),
        near_duplicate_count=len(near_pairs),
        near_duplicate_pairs=tuple(near_pairs),
    )
    return report, canonical_map

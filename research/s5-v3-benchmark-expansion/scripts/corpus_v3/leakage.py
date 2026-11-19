"""Train/dev/test and forbidden-hash leakage guard for Corpus v3."""

from __future__ import annotations

from collections import Counter, defaultdict

from .constants import SPLIT_CORPUS_SHARED, VALID_SPLITS
from .models import DuplicatePair, LeakageCheckResult, PassageRecord


def verify_leakage_guard(
    passages: list[PassageRecord],
    near_duplicate_pairs: tuple[DuplicatePair, ...] = (),
    forbidden_hashes: frozenset[str] = frozenset(),
    enforce_doc_level_isolation: bool = True,
) -> LeakageCheckResult:
    """Enforce zero hash, near-duplicate, and document leakage across splits.

    Passages assigned to `corpus_shared` are treated as the shared retrieval
    corpus (split isolation is enforced across `train`, `dev`, and `test`).
    """
    violations: list[str] = []
    split_counts: Counter[str] = Counter()
    hash_to_splits: dict[str, set[str]] = defaultdict(set)
    doc_to_splits: dict[str, set[str]] = defaultdict(set)
    passage_to_split: dict[str, str] = {}
    forbidden_overlaps = 0

    for rec in passages:
        if rec.split_assignment not in VALID_SPLITS:
            violations.append(
                f"Invalid split_assignment '{rec.split_assignment}' on {rec.passage_id}"
            )
            continue
        split_counts[rec.split_assignment] += 1
        passage_to_split[rec.passage_id] = rec.split_assignment

        if rec.normalized_text_sha256 in forbidden_hashes:
            forbidden_overlaps += 1
            violations.append(
                f"Passage {rec.passage_id} matches forbidden/held-out hash "
                f"{rec.normalized_text_sha256}"
            )

        if rec.split_assignment != SPLIT_CORPUS_SHARED:
            hash_to_splits[rec.normalized_text_sha256].add(rec.split_assignment)
            doc_to_splits[rec.source_doc_id].add(rec.split_assignment)

    cross_split_hash_overlaps = 0
    for norm_hash, splits in sorted(hash_to_splits.items()):
        if len(splits) > 1:
            cross_split_hash_overlaps += 1
            violations.append(
                f"Normalized hash {norm_hash[:16]}... appears in multiple splits: {sorted(splits)}"
            )

    cross_split_doc_overlaps = 0
    if enforce_doc_level_isolation:
        for doc_id, splits in sorted(doc_to_splits.items()):
            if len(splits) > 1:
                cross_split_doc_overlaps += 1
                violations.append(f"Document {doc_id} straddles multiple splits: {sorted(splits)}")

    cross_split_near_dup_overlaps = 0
    for pair in near_duplicate_pairs:
        split_a = passage_to_split.get(pair.passage_id, SPLIT_CORPUS_SHARED)
        split_b = passage_to_split.get(pair.matched_passage_id, SPLIT_CORPUS_SHARED)
        if split_a != SPLIT_CORPUS_SHARED and split_b != SPLIT_CORPUS_SHARED and split_a != split_b:
            cross_split_near_dup_overlaps += 1
            violations.append(
                f"Near-duplicate pair ({pair.passage_id} [{split_a}], "
                f"{pair.matched_passage_id} [{split_b}]) straddles splits "
                f"(jaccard={pair.similarity})"
            )

    return LeakageCheckResult(
        passed=len(violations) == 0,
        violations=tuple(violations),
        split_counts=dict(sorted(split_counts.items())),
        cross_split_exact_hash_overlaps=cross_split_hash_overlaps,
        cross_split_near_dup_overlaps=cross_split_near_dup_overlaps,
        cross_split_doc_overlaps=cross_split_doc_overlaps,
        forbidden_hash_overlaps=forbidden_overlaps,
    )

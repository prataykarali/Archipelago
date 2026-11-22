"""Named constants for S5-v3.1 pool building, adjudication, NC, and gold."""

from __future__ import annotations

BENCHMARK_VERSION: str = "s5v3.1"
GOLD_SCHEMA_VERSION: str = "s5v31_adjudicated_gold_v1"
GOLD_STATUS_FINAL: str = "ADJUDICATED_HUMAN_GOLD_V31_FINAL"
GOLD_STATUS_SYNTHETIC: str = "SYNTHETIC_TEST_GOLD_DO_NOT_PUBLISH"
VALID_GOLD_STATUSES: frozenset[str] = frozenset(
    {GOLD_STATUS_FINAL, GOLD_STATUS_SYNTHETIC}
)

PROVENANCE_INDEPENDENT_HUMAN: str = "INDEPENDENT_HUMAN"
PROVENANCE_ADJUDICATED_HUMAN: str = "ADJUDICATED_HUMAN"
PROVENANCE_ZERO_DISAGREEMENTS: str = "NOT_REQUIRED_ZERO_DISAGREEMENTS"
ASSISTANCE_NONE_HUMAN: str = "NONE_INDEPENDENT_HUMAN"

VALID_GRADES: frozenset[int] = frozenset({0, 1, 2})
VALID_POOL_DEPTHS: frozenset[int] = frozenset({5, 10})
VALID_SPLITS: frozenset[str] = frozenset({"dev", "test", "dev_and_test"})
VALID_NC_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "confirmed_unanswerable",
        "answerable_in_corpus",
        "ambiguous",
        "unsupported_premise",
        "requires_revision",
    }
)

BLIND_POOL_SALT: str = "s5v31-blinded-pool-v1"
MIN_RATIONALE_CHARS: int = 8
SHA256_HEX_LENGTH: int = 64
HASH_READ_CHUNK_BYTES: int = 65536
GRADE_SCALE_MAX_DIFF_SQ: float = 4.0

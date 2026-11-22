"""Named constants for the versioned S5-v3.1 D1 preflight and evaluation pipeline."""

from __future__ import annotations

import re

BENCHMARK_VERSION_V31 = "s5v3.1"
GOLD_SCHEMA_VERSION_V31 = "s5v31_adjudicated_gold_v1"
GOLD_STATUS_FINAL = "ADJUDICATED_HUMAN_GOLD_V31_FINAL"
GOLD_STATUS_SYNTHETIC = "SYNTHETIC_TEST_GOLD_DO_NOT_PUBLISH"

AUTH_SCHEMA_VERSION_V31 = "s5v31_investigator_authorization_v1"
AUTH_APPROVED_STATUS_V31 = "APPROVED_FOR_REAL_S5V31_D1_EXECUTION"
MIN_DECLARATION_CHARS = 8

VALID_POOL_DEPTHS: frozenset[int] = frozenset({5, 10})
VALID_SPLITS: frozenset[str] = frozenset({"dev", "test", "dev_and_test"})
VALID_GRADES: frozenset[int] = frozenset({0, 1, 2})

TOP_K_5 = 5
TOP_K_10 = 10
STRICT_REL_THRESHOLD = 2
LENIENT_REL_THRESHOLD = 1
METRIC_DECIMALS = 4

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LEGACY_V21_QID_PREFIX = "Q-S5B2-"
LEGACY_V21_POOL_MARKER = "s5b2_1"

REQUIRED_REVIEWER_PROVENANCE_CLASS = "INDEPENDENT_HUMAN"
REQUIRED_ASSISTANCE_DECLARATION = "NONE_INDEPENDENT_HUMAN"
VALID_ADJUDICATOR_PROVENANCE_CLASSES: frozenset[str] = frozenset(
    {"ADJUDICATED_HUMAN", "NOT_REQUIRED_ZERO_DISAGREEMENTS"}
)
VALID_ADJUDICATION_SOURCES: frozenset[str] = frozenset(
    {"DUAL_HUMAN_AGREEMENT", "ADJUDICATED_HUMAN"}
)

NC_CONFIRMED_UNANSWERABLE: frozenset[str] = frozenset({"confirmed_unanswerable"})
NC_RECLASSIFIED_ANSWERABLE: frozenset[str] = frozenset({"answerable_in_corpus"})
NC_EXCLUDED_CLASSES: frozenset[str] = frozenset(
    {"ambiguous", "unsupported_premise", "requires_revision"}
)
ALL_NC_CLASSES: frozenset[str] = (
    NC_CONFIRMED_UNANSWERABLE | NC_RECLASSIFIED_ANSWERABLE | NC_EXCLUDED_CLASSES
)

PLACEHOLDER_ID_MARKERS: frozenset[str] = frozenset(
    {
        "<INVESTIGATOR_ID>",
        "<HUMAN_VERIFIER_ID>",
        "<REVIEWER_ID>",
        "<ADJUDICATOR_ID>",
        "TODO",
        "TBD",
        "AUTO",
        "AI",
        "NONE",
        "N/A",
        "LLM",
    }
)

SYSTEM_V31_1HOP = "v31_graph_1hop_backfill"
SYSTEM_V31_2HOP = "v31_graph_2hop_backfill"

SYNTHETIC_BANNER = "SYNTHETIC TEST DATA — NOT REAL S5-V3.1 HUMAN EVALUATION RESULTS"

POOLED_RECALL_DENOMINATOR_DOC = (
    "Total number of pooled passages for this query whose adjudicated final_grade "
    "meets or exceeds the active relevance threshold (strict: grade == 2; lenient: grade >= 1). "
    "This is a pooled recall denominator at depth k, NOT full-corpus recall."
)

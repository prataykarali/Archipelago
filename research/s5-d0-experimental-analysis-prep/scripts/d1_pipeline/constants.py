"""Named constants for the S5-D1 preflight, evaluation, and reporting pipeline."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

DEFAULT_FROZEN_RANKINGS = (
    ROOT
    / "research"
    / "s5-b2-benchmark-correction"
    / "reports"
    / "s5b2_1_frozen_ranked_results.json"
)
DEFAULT_FROZEN_POOL = (
    ROOT
    / "research"
    / "s5-b2-benchmark-correction"
    / "proposed_package_v2_1"
    / "retrieval_query_pool_blinded.json"
)

# Relevance & ranking cutoffs
TOP_K_5 = 5
TOP_K_10 = 10
STRICT_REL_THRESHOLD = 2
LENIENT_REL_THRESHOLD = 1
METRIC_DECIMALS = 4
VALID_GRADES = frozenset({0, 1, 2})

# Schema versions
LEGACY_V1_SCHEMA_VERSION = "s5d0_adjudicated_gold_v1"
AC_V2_SCHEMA_VERSIONS = frozenset({
    "s5d1_adjudicated_gold_ac_v2",
    "s5_gold_label_ac_v2",
})
GOLD_FINAL_STATUSES = frozenset({
    "ADJUDICATED_HUMAN_GOLD_FINAL",
    "ADJUDICATED_HUMAN_GOLD_AC_V2_FINAL",
    "ADJUDICATED_HUMAN_AC_GOLD_FINAL",
})
AUTH_SCHEMA_VERSION = "s5d1_investigator_authorization_v1"
AUTH_APPROVED_STATUS = "APPROVED_FOR_REAL_S5_D1_EXECUTION"
MIN_APPROVAL_DECLARATION_CHARS = 16

# Adjudication & provenance
AGREEMENT_ADJUDICATION_SOURCES = frozenset({
    "DUAL_HUMAN_AGREEMENT",
    "DUAL_HUMAN_AC_AGREEMENT",
})
VALID_ADJUDICATION_SOURCES = AGREEMENT_ADJUDICATION_SOURCES | frozenset({
    "THIRD_PARTY_ADJUDICATION",
    "INVESTIGATOR_ADJUDICATION",
    "HUMAN_ADJUDICATION",
    "ADJUDICATED_HUMAN_AC",
})
VALID_HUMAN_PROVENANCE_CLASSES = frozenset({
    "INDEPENDENT_HUMAN",
    "ADJUDICATED_HUMAN",
})
VALID_ADJUDICATOR_PROVENANCE_CLASSES = frozenset({
    "ADJUDICATED_HUMAN",
    "NOT_REQUIRED_ZERO_DISAGREEMENTS",
})
REQUIRED_ASSISTANCE_DECLARATION = "NONE_INDEPENDENT_HUMAN"
REQUIRED_PRIOR_EXPOSURE = "NONE"
REJECTED_PROVENANCE_CLASSES = frozenset({
    "AI_ASSISTED_OR_GENERATED",
    "HUMAN_POST_AI_EXPOSURE",
    "SYNTHETIC",
    "UNVERIFIED",
    "UNKNOWN",
})
PLACEHOLDER_ID_MARKERS = frozenset({
    "<INVESTIGATOR_ID>",
    "<HUMAN_VERIFIER_ID>",
    "<REVIEWER_ID>",
    "TODO",
    "TBD",
    "AUTO",
    "AI",
    "NONE",
    "N/A",
})

# Negative controls
PROVISIONAL_NEG_CONTROL_IDS = ("Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11")

NEG_CONTROL_CONFIRMED_UNANSWERABLE = frozenset({
    "NO_ANSWER_IN_FROZEN_CORPUS",
    "confirmed_unanswerable",
})
NEG_CONTROL_RECLASSIFIED_ANSWERABLE = frozenset({
    "ANSWERABLE_IN_FROZEN_CORPUS",
    "answerable_in_corpus",
    "RECLASSIFIED_AS_ANSWERABLE",
})
NEG_CONTROL_EXCLUDED_CLASSES = frozenset({
    "NO_ANSWER_IN_SELECTED_PASSAGES",
    "AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION",
    "QUESTION_REQUIRING_REVISION",
    "ambiguous",
    "unsupported_premise",
    "requires_revision",
})
ALL_VALID_NEG_CONTROL_CLASSES = (
    NEG_CONTROL_CONFIRMED_UNANSWERABLE
    | NEG_CONTROL_RECLASSIFIED_ANSWERABLE
    | NEG_CONTROL_EXCLUDED_CLASSES
)

# System names for 1-hop vs 2-hop descriptive comparison
SYSTEM_REPAIRED_1HOP = "repaired_graph_1hop_ablation"
SYSTEM_REPAIRED_2HOP = "repaired_graph_2hop_full"
SYSTEM_BASELINE_1HOP = "baseline_graph_1hop"

# Synthetic watermarking
SYNTHETIC_PREFIX = "SYNTHETIC_"
SYNTHETIC_BANNER = "SYNTHETIC TEST DATA — NOT REAL S5-D1 HUMAN EVALUATION RESULTS"
SYNTHETIC_TITLE_TAG = "[SYNTHETIC]"

# SVG layout constants
SVG_WIDTH = 920
SVG_HEIGHT = 480
SVG_MARGIN_LEFT = 80
SVG_MARGIN_RIGHT = 40
SVG_MARGIN_TOP = 75
SVG_MARGIN_BOTTOM = 110
SVG_WATERMARK_FONT_SIZE = 72
SVG_TITLE_FONT_SIZE = 18
SVG_SUBTITLE_FONT_SIZE = 12
SVG_AXIS_FONT_SIZE = 11
SVG_LEGEND_FONT_SIZE = 11
SVG_GRID_STEPS = 5
SVG_BAR_GROUP_PADDING = 0.22

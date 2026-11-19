"""Named constants and canonical paths for S5-C3 A/C Comparison & Adjudication."""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]

DEFAULT_FROZEN_POOL = (
    ROOT_DIR
    / "research"
    / "s5-b2-benchmark-correction"
    / "proposed_package_v2_1"
    / "retrieval_query_pool_blinded.json"
)
DEFAULT_AC_V2_SCHEMA = (
    ROOT_DIR
    / "research"
    / "s5-c3-human-adjudication-prep"
    / "schemas"
    / "s5_gold_label_ac_v2.schema.json"
)
DEFAULT_PRIVATE_S5C3_DIR = ROOT_DIR / "data" / "annotation_local" / "s5c3"

EXPECTED_PAIR_COUNT = 254
SHA256_HEX_LENGTH = 64
MIN_SIGNER_LENGTH = 2
MIN_RATIONALE_LENGTH = 10
MIN_APPROVAL_LENGTH = 10
MIN_TIMESTAMP_LENGTH = 10
FLOAT_ROUND_DIGITS = 4

VALID_GRADES = frozenset({0, 1, 2})
GRADE_IRRELEVANT = 0
GRADE_PARTIAL = 1
GRADE_HIGH = 2
MAX_GRADE_SPAN_SQUARED = 4

VALID_ROLES = frozenset({"REV_A", "REV_C"})
ROLE_REV_A = "REV_A"
ROLE_REV_C = "REV_C"
ROLE_REV_B = "REV_B"

SCHEMA_VERSION_AC_V2 = "s5d1_adjudicated_gold_ac_v2"
GOLD_STATUS_AC_V2_FINAL = "ADJUDICATED_HUMAN_GOLD_AC_V2_FINAL"
WORKSHEET_SCHEMA_VERSION = "s5c3_ac_adjudication_worksheet_v1"
WORKSHEET_STATUS_BLANK = "AWAITING_HUMAN_ADJUDICATION"
WORKSHEET_STATUS_IN_PROGRESS = "IN_PROGRESS_HUMAN_ADJUDICATION"
WORKSHEET_STATUS_COMPLETED = "COMPLETED_HUMAN_ADJUDICATION"

PROVENANCE_INDEPENDENT_HUMAN = "INDEPENDENT_HUMAN"
PROVENANCE_ADJUDICATED_HUMAN = "ADJUDICATED_HUMAN"
PROVENANCE_NOT_REQUIRED_ZERO = "NOT_REQUIRED_ZERO_DISAGREEMENTS"
PROVENANCE_AI_ASSISTED = "AI_ASSISTED_OR_GENERATED"
PROVENANCE_UNATTESTED = "UNATTESTED"

ASSISTANCE_NONE = "NONE_INDEPENDENT_HUMAN"
PRIOR_EXPOSURE_NONE = "NONE"

ADJUDICATION_SOURCE_AGREEMENT = "DUAL_HUMAN_AC_AGREEMENT"
ADJUDICATION_SOURCE_ADJUDICATED = "ADJUDICATED_HUMAN_AC"

LEGACY_REV_B_PRESERVED_SHA256 = (
    "ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4"
)

PROVISIONAL_NEG_CONTROL_IDS = ("Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11")
VALID_NEG_CONTROL_CLASSES = frozenset(
    {
        "NO_ANSWER_IN_SELECTED_PASSAGES",
        "NO_ANSWER_IN_FROZEN_CORPUS",
        "AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION",
        "QUESTION_REQUIRING_REVISION",
    }
)

FORBIDDEN_SIGNER_TOKENS = frozenset(
    {
        "tbd",
        "todo",
        "auto",
        "automated",
        "ai",
        "llm",
        "bot",
        "gpt",
        "claude",
        "gemini",
        "qwen",
        "assistant",
        "placeholder",
        "unsigned",
        "none",
        "n/a",
    }
)

AI_PROVENANCE_KEYWORDS = (
    "ai",
    "llm",
    "model",
    "generated",
    "assisted",
    "synthetic",
    "automated",
    "gpt",
    "claude",
    "gemini",
    "qwen",
)

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 5063
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

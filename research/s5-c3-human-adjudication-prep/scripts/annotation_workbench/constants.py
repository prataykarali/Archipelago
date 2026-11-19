"""Named constants and protocol invariants for the S5-C3 human annotation workbench."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_POOL_JSON = (
    REPO_ROOT
    / "research"
    / "s5-b2-benchmark-correction"
    / "proposed_package_v2_1"
    / "retrieval_query_pool_blinded.json"
)

PRIVATE_ANNOTATION_ROOT = REPO_ROOT / "data" / "annotation_local"
DEFAULT_PRIVATE_S5C3_DIR = PRIVATE_ANNOTATION_ROOT / "s5c3"
DEFAULT_WORKBENCH_DIR = DEFAULT_PRIVATE_S5C3_DIR / "workbench"
DEFAULT_SESSION_FILE = DEFAULT_WORKBENCH_DIR / "active_session.json"
DEFAULT_BACKUP_DIR = DEFAULT_WORKBENCH_DIR / "backups"
DEFAULT_SUBMISSIONS_DIR = DEFAULT_PRIVATE_S5C3_DIR / "submissions"

DEFAULT_BLANK_WORKBOOK_BACKUP = (
    DEFAULT_PRIVATE_S5C3_DIR
    / "immutable_blank_backups"
    / "independent_reviewer_c_s5c3_workbook_BLANK_BACKUP.md"
)
DEFAULT_BLANK_WORKBOOK = (
    DEFAULT_PRIVATE_S5C3_DIR / "independent_reviewer_c_s5c3_workbook.md"
)
DEFAULT_KUZU_DB_PATH = REPO_ROOT / "okf_graph.db"

EXPECTED_POOL_SHA256 = (
    "2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037"
)
EXPECTED_PAIR_COUNT = 254
EXPECTED_QUERY_COUNT = 10

SESSION_SCHEMA_VERSION = "s5c3_annotation_session_v1"
SUBMISSION_SCHEMA_VERSION = "s5c3_human_submission_v1"
MANIFEST_SCHEMA_VERSION = "s5c3_submission_sha256_manifest_v1"
DEFAULT_EVIDENCE_SOURCE_LABEL = "okf_graph.db (s5a_eval_corpus_v1, 713 passages)"

ALLOWED_HOST = "127.0.0.1"
DEFAULT_PORT = 5058
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE_ENTITY = 422

VALID_GRADES: frozenset[int] = frozenset({0, 1, 2})
GRADE_IRRELEVANT = 0
GRADE_PARTIAL = 1
GRADE_HIGHLY_RELEVANT = 2

VALID_CONFIDENCE_LEVELS: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")

VALID_PROVENANCE_CLASSES: tuple[str, ...] = (
    "INDEPENDENT_HUMAN",
    "HUMAN_POST_AI_EXPOSURE",
    "AI_ASSISTED_OR_GENERATED",
    "ADJUDICATED_HUMAN",
)

VALID_ASSISTANCE_DECLARATIONS: tuple[str, ...] = (
    "NONE_INDEPENDENT_HUMAN",
    "EXPOSED_TO_AI_SUGGESTIONS",
    "AI_ASSISTED",
)

PROVENANCE_INDEPENDENT_HUMAN = "INDEPENDENT_HUMAN"
PROVENANCE_POST_AI_EXPOSURE = "HUMAN_POST_AI_EXPOSURE"
PROVENANCE_AI_ASSISTED = "AI_ASSISTED_OR_GENERATED"
PROVENANCE_ADJUDICATED_HUMAN = "ADJUDICATED_HUMAN"

ASSISTANCE_NONE = "NONE_INDEPENDENT_HUMAN"
ASSISTANCE_EXPOSED = "EXPOSED_TO_AI_SUGGESTIONS"
ASSISTANCE_AI_ASSISTED = "AI_ASSISTED"

STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED_TEMPLATE = "COMPLETED_{completed}_OF_{total}"

HUMAN_ATTESTATION_STATEMENT = (
    "I affirm that every grade, verbatim quotation, confidence rating, and note "
    "in this submission reflects my own truthful human judgment, and that the "
    "provenance class and AI-assistance/exposure disclosure above are accurate."
)

# Forbidden tokens that must never appear in blinded UI chrome or non-passage metadata.
FORBIDDEN_BLINDING_TOKENS: tuple[str, ...] = (
    "bm25",
    "dense_snowflake_arctic",
    "hybrid_rrf",
    "baseline_graph",
    "repaired_graph",
    "rev_a",
    "rev_b",
    "disagreement",
    "unanswerable",
    "negative_control",
    "single_hop",
    "two_hop",
    "cross_document",
)

SUBMISSION_CSV_COLUMNS: tuple[str, ...] = (
    "pair_id",
    "query_id",
    "domain",
    "query_text",
    "candidate_passage_id",
    "candidate_doc_id",
    "candidate_chunk_id",
    "candidate_page_number",
    "passage_sha256",
    "relevance_grade",
    "supporting_quotation",
    "confidence",
    "reviewer_notes",
    "reviewer_id",
    "provenance_class",
    "review_date_utc",
)

EXCLUDED_CORPUS_PASSAGE_ID = (
    "doc_data_and_computer_communications::"
    "doc_data_and_computer_communications_p612_4"
)

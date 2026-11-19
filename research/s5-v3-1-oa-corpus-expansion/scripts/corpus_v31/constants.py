"""Named constants and verified open-license registry for S5-v3.1 Corpus v3.1."""

from __future__ import annotations

from pathlib import Path

CORPUS_V31_SCHEMA_VERSION = "s5v31_corpus_v3.1"
CORPUS_V31_MANIFEST_SCHEMA_VERSION = "s5v31_corpus_manifest_v3.1"
SOURCE_LICENSE_MANIFEST_SCHEMA_VERSION = "s5v31_source_license_manifest_v3.1"

# Prior S5-v3 frozen corpus inputs (read-only; never modified)
PRIOR_V3_CORPUS_JSONL = Path("data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl")
PRIOR_V3_CORPUS_EXPECTED_SHA256 = "dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4"
PRIOR_V3_EXPECTED_ELIGIBLE_COUNT = 818

# Default S5-v3.1 outputs
DEFAULT_V31_OUTPUT_JSONL = Path(
    "data/annotation_local/s5v3_1/corpus_v31/s5v31_corpus_passages.jsonl"
)
DEFAULT_V31_CORPUS_MANIFEST = Path(
    "research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_corpus_manifest.json"
)
DEFAULT_V31_LICENSE_MANIFEST = Path(
    "research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_source_license_manifest.json"
)

# Provenance classes
PROVENANCE_PDF_EXTRACTED = "pdf_extracted"
PROVENANCE_MARKDOWN_OA_EXTRACTED = "markdown_oa_extracted"
PROVENANCE_EPUB_OA_EXTRACTED = "epub_oa_extracted"
PROVENANCE_HTML_OA_EXTRACTED = "html_oa_extracted"
PROVENANCE_LATEX_OA_EXTRACTED = "latex_oa_extracted"

# Chunking parameters (aligned with v3)
TARGET_CHUNK_CHARS = 1200
MAX_CHUNK_CHARS = 1600
MIN_CHUNK_CHARS = 240
PARAGRAPH_JOIN_SEP = "\n\n"

# Quality & boilerplate filtering thresholds
MIN_USABLE_CHARS = 160
MIN_USABLE_TOKENS = 25
MAX_CONTROL_CHAR_RATIO = 0.01
CONTROL_ORD_UPPER = 32
ALLOWED_WHITESPACE_ORDS: frozenset[int] = frozenset({9, 10, 13})
MAX_SINGLE_CHAR_TOKEN_RATIO = 0.28
MIN_TOKENS_FOR_MATH_CHECK = 25
MIN_PROSE_WORDS_PER_SENTENCE = 6
BIB_CITATION_LINE_MIN_RATIO = 0.45
BIB_MIN_LINES = 5
NAV_BOILERPLATE_PHRASES: tuple[str, ...] = (
    "skip to main content",
    "table of contents",
    "previous chapter",
    "next chapter",
    "creative commons attribution",
    "toggle navigation",
    "back to top",
)

# Deduplication thresholds
SHINGLE_SIZE = 5
NEAR_DUP_JACCARD_THRESHOLD = 0.80
MIN_TOKENS_FOR_NEAR_DUP = 15
MAX_SHINGLE_POSTING_FREQ = 60

# Strictly forbidden sources (never ingest)
FORBIDDEN_SOURCE_PATTERNS: tuple[str, ...] = (
    "mixu/distsysbook",
    "distsysbook",
    "predictive_analytics_and_data_mining",
    "z-library",
    "z-lib",
    "elsevier",
    "okf_graph.db",
)

# Split assignment (shared retrieval corpus; query benchmark owns dev/test)
SPLIT_CORPUS_SHARED = "corpus_shared"

# Canonical new OA source paths under gitignored data/annotation_local/s5v3_1/raw_sources/
RAW_OS_EPUB_REL = Path(
    "data/annotation_local/s5v3_1/raw_sources/operating_system_fundamentals.epub"
)
RAW_DB_HTML_DIR_REL = Path("data/annotation_local/s5v3_1/raw_sources/dbdesign2e_libretexts")
RAW_NET_PDF_REL = Path("data/annotation_local/s5v3_1/raw_sources/cnp3/book/CNP3.pdf")
RAW_DS_TEX_REL = Path("data/annotation_local/s5v3_1/raw_sources/dist-sys/dist-sys.tex")

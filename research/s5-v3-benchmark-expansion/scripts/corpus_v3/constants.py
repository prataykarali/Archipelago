"""Named constants and verified source registry for S5-v3 Corpus v3 builder."""

from __future__ import annotations

from pathlib import Path

CORPUS_SCHEMA_VERSION = "s5v3_corpus_v3.0"
MANIFEST_SCHEMA_VERSION = "s5v3_corpus_manifest_v3.0"

# Provenance classes (strictly separated; never conflated)
PROVENANCE_PDF_EXTRACTED = "pdf_extracted"
PROVENANCE_MARKDOWN_OA_EXTRACTED = "markdown_oa_extracted"
PROVENANCE_HAND_AUTHORED = "hand_authored"
PROVENANCE_DERIVED = "derived"
VALID_PROVENANCE_CLASSES: frozenset[str] = frozenset(
    {
        PROVENANCE_PDF_EXTRACTED,
        PROVENANCE_MARKDOWN_OA_EXTRACTED,
        PROVENANCE_HAND_AUTHORED,
        PROVENANCE_DERIVED,
    }
)

# Redistribution permissions
REDIST_SHARE_ALIKE = "share_alike_with_attribution"
REDIST_LOCAL_RESEARCH_ONLY = "local_research_only_no_republishing"
REDIST_FORBIDDEN = "forbidden_excluded"

# Split labels
SPLIT_CORPUS_SHARED = "corpus_shared"
SPLIT_TRAIN = "train"
SPLIT_DEV = "dev"
SPLIT_TEST = "test"
VALID_SPLITS: frozenset[str] = frozenset({SPLIT_CORPUS_SHARED, SPLIT_TRAIN, SPLIT_DEV, SPLIT_TEST})

# Chunking parameters (named constants; no magic numbers)
TARGET_CHUNK_CHARS = 1200
MAX_CHUNK_CHARS = 1600
MIN_CHUNK_CHARS = 220
CHUNK_OVERLAP_CHARS = 150
PARAGRAPH_JOIN_SEPARATOR = "\n\n"

# Quality inspection thresholds
MIN_USABLE_CHARS = 120
MIN_USABLE_TOKENS = 20
HEADER_FOOTER_MAX_CHARS = 320
MAX_SHORT_LINE_RATIO = 0.72
SHORT_LINE_MAX_CHARS = 28
MIN_LINES_FOR_HEADER_CHECK = 4
MIN_PROSE_WORDS_PER_SENTENCE = 6
TOC_DOT_LEADER_MIN_COUNT = 3
TOC_NUMERIC_LINE_MIN_RATIO = 0.28
TOC_MIN_LINES = 8
MAX_SINGLE_CHAR_TOKEN_RATIO = 0.28
MIN_TOKENS_FOR_MATH_NOISE_CHECK = 25
MAX_CONTROL_CHAR_RATIO = 0.01
QUALITY_PENALTY_SEVERE = 0.45
QUALITY_PENALTY_MODERATE = 0.20
QUALITY_PENALTY_MINOR = 0.08
QUALITY_MIN_USABLE_SCORE = 0.50

# Quality flag names
FLAG_EMPTY_OR_TOO_SHORT = "EMPTY_OR_TOO_SHORT"
FLAG_HEADER_FOOTER_ONLY = "HEADER_FOOTER_ONLY"
FLAG_TOC_OR_INDEX_LIKE = "TOC_OR_INDEX_LIKE"
FLAG_BROKEN_ENCODING = "BROKEN_LIGATURES_OR_ENCODING"
FLAG_MATH_EXTRACTION_NOISE = "MATH_EXTRACTION_NOISE"
FLAG_TRUNCATED_START = "MID_SENTENCE_TRUNCATION_START"
FLAG_TRUNCATED_END = "MID_SENTENCE_TRUNCATION_END"

SEVERE_QUALITY_FLAGS: frozenset[str] = frozenset(
    {
        FLAG_EMPTY_OR_TOO_SHORT,
        FLAG_HEADER_FOOTER_ONLY,
        FLAG_BROKEN_ENCODING,
    }
)

# Deduplication parameters
SHINGLE_SIZE = 5
NEAR_DUP_JACCARD_THRESHOLD = 0.80
MIN_TOKENS_FOR_NEAR_DUP = 12
MAX_SHINGLE_POSTING_FREQ = 50

# Exclusion guard patterns (copyrighted, personal, synthetic stubs)
EXCLUDED_PATH_SUBSTRINGS: tuple[str, ...] = (
    "predictive_analytics_and_data_mining",
    "z-library",
    "z-lib",
    "elsevier",
    "data/private",
    "data/uploads",
    "test_upload",
    "data/annotation_local/s5c3",
)
MIN_REAL_SOURCE_BYTES = 1024

# Default repository-relative and local output paths
DEFAULT_OUTPUT_JSONL = Path("data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl")
DEFAULT_OUTPUT_MANIFEST = Path(
    "research/s5-v3-benchmark-expansion/manifests/s5v3_corpus_manifest.json"
)

# Explicit multi-domain coverage gap (honest accounting)
MISSING_OA_DOMAINS: tuple[dict[str, str], ...] = (
    {
        "domain": "Operating Systems",
        "status": "MISSING_LOCAL_OA_SOURCE",
        "candidate_oa_source": "OSTEP (Remzi & Andrea Arpaci-Dusseau, free online textbook)",
    },
    {
        "domain": "Database Systems",
        "status": "MISSING_LOCAL_OA_SOURCE",
        "candidate_oa_source": "CMU 15-445 / Open-access database architecture surveys",
    },
    {
        "domain": "Computer Networks",
        "status": "MISSING_LOCAL_OA_SOURCE",
        "candidate_oa_source": "Computer Networks: A Systems Approach (Peterson & Davie, CC-BY)",
    },
    {
        "domain": "Distributed Systems",
        "status": "MISSING_LOCAL_OA_SOURCE",
        "candidate_oa_source": "arXiv cs.DC open-access papers / Maarten van Steen DS free PDF",
    },
)

# Verified local open-access source registry (from Module A inventory)
VERIFIED_LOCAL_OA_SOURCES: tuple[dict[str, object], ...] = (
    {
        "doc_id": "local_oa_001",
        "path": (
            "data/academic_candidates/"
            "39990e2958ef5c3494918de03fd3d9ed594efa4572218cb644efc57194bb8fe5.md"
        ),
        "title": "Dive into Deep Learning (D2L) — Chapter 3: Linear Regression",
        "source_format": "markdown",
        "domain": "Machine Learning",
        "provenance_class": PROVENANCE_MARKDOWN_OA_EXTRACTED,
        "license_id": "CC-BY-SA-4.0",
        "redistribution_permission": REDIST_SHARE_ALIKE,
        "expected_sha256": ("39990e2958ef5c3494918de03fd3d9ed594efa4572218cb644efc57194bb8fe5"),
        "source_url": ("https://d2l.ai/chapter_linear-regression/linear-regression.html"),
        "eligible": True,
    },
    {
        "doc_id": "local_oa_002",
        "path": (
            "data/academic_candidates/"
            "8888aa2043588e41d0f222b59ca6896e5211816eeca8896db215234ba209aa4f.pdf"
        ),
        "title": (
            "Efficient Guided Generation for Large Language Models "
            "(Willard & Louf, 2023; arXiv:2307.09702v2)"
        ),
        "source_format": "pdf",
        "domain": "Natural Language Processing / LLMs",
        "provenance_class": PROVENANCE_PDF_EXTRACTED,
        "license_id": "arXiv-perpetual-nonexclusive",
        "redistribution_permission": REDIST_LOCAL_RESEARCH_ONLY,
        "expected_sha256": ("8888aa2043588e41d0f222b59ca6896e5211816eeca8896db215234ba209aa4f"),
        "source_url": "https://arxiv.org/abs/2307.09702",
        "eligible": True,
    },
    {
        "doc_id": "local_oa_003",
        "path": "/home/pratay-karali/Downloads/mml-book.pdf",
        "title": "Mathematics for Machine Learning (Deisenroth, Faisal, Ong)",
        "source_format": "pdf",
        "domain": "Mathematics for Machine Learning",
        "provenance_class": PROVENANCE_PDF_EXTRACTED,
        "license_id": ("Free online PDF edition (mml-book.github.io; Cambridge University Press)"),
        "redistribution_permission": REDIST_LOCAL_RESEARCH_ONLY,
        "expected_sha256": ("3f87b70c64a35d30ec4e565b4d5cfd18fe913002d3b3bed44691c7d0838911bc"),
        "source_url": "https://mml-book.github.io/",
        "eligible": True,
    },
    {
        "doc_id": "local_oa_004",
        "path": "/home/pratay-karali/Downloads/metatron-paper.pdf",
        "title": (
            "METATRON: A Promptable Whole-Body Execution Layer for Humanoids (Tessler et al.)"
        ),
        "source_format": "pdf",
        "domain": "Robotics / Control",
        "provenance_class": PROVENANCE_PDF_EXTRACTED,
        "license_id": (
            "Preprint (local extraction only; verify arXiv license before redistribution)"
        ),
        "redistribution_permission": REDIST_LOCAL_RESEARCH_ONLY,
        "expected_sha256": ("de2411a21822326b6afadd2724cbafa1b8b8850c8630197c2e706a41c2b6ecaa"),
        "source_url": "local_preprint_verified_module_a",
        "eligible": True,
    },
)

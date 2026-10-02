"""Mention-a-book resolver: turn a librarian's free-text mention into a filled record.

A librarian types (or pastes) a title, an ISBN, a filename, or any fragment of a
book's name. This module searches every authoritative source the library owns and
returns ranked candidates **with their exact verified source URL**.

Design rules (docs/01 §5, §6):
  * Never fabricate a book, author, identifier, or URL.
  * Never return a generic portal/repo homepage when an exact page exists.
  * An unmatched mention returns an empty result with a reason — never a guess.
  * Matching is deterministic and offline-first so it is always available."""
from __future__ import annotations

import logging  # noqa: F401
import re  # noqa: F401
from dataclasses import asdict, dataclass, field  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401

from .part01_logger import (  # noqa: F401
    logger,
    MAX_CANDIDATES,
    MIN_FUZZY_SCORE,
    MIN_TOKEN_LENGTH,
    ISBN_MIN_DIGITS,
    HF_REPO_ID,
    HF_BLOB_BASE,
    PDF_SUBDIRS,
    _OPAC_URL,
    _STOPWORDS,
    MATCH_KIND_EXACT_ISBN,
    MATCH_KIND_CATALOG,
    MATCH_KIND_REGISTRY,
    MATCH_KIND_PEARSON,
    MATCH_KIND_HF,
    MATCH_KIND_LOCAL,
    METADATA_TRUST_MIN_CONFIDENCE,
    SOURCE_NAMES,
    MentionMatch,
    MentionResult,
    normalize_title,
    title_tokens,
    extract_isbn,
    score_against,
    _best,
    _repo_root,
    _search_resource_catalog,
    _search_registry,
    _search_pearson,
    _search_huggingface,
    _search_local_pdfs,
)
from .part02_search_by_isbn import (  # noqa: F401
    _search_by_isbn,
    mention_book,
    is_trusted_match,
    prefill_from_match,
)

__all__ = ["logger", "MAX_CANDIDATES", "MIN_FUZZY_SCORE", "MIN_TOKEN_LENGTH", "ISBN_MIN_DIGITS", "HF_REPO_ID", "HF_BLOB_BASE", "PDF_SUBDIRS", "_OPAC_URL", "_STOPWORDS", "MATCH_KIND_EXACT_ISBN", "MATCH_KIND_CATALOG", "MATCH_KIND_REGISTRY", "MATCH_KIND_PEARSON", "MATCH_KIND_HF", "MATCH_KIND_LOCAL", "METADATA_TRUST_MIN_CONFIDENCE", "SOURCE_NAMES", "MentionMatch", "MentionResult", "normalize_title", "title_tokens", "extract_isbn", "score_against", "_best", "_repo_root", "_search_resource_catalog", "_search_registry", "_search_pearson", "_search_huggingface", "_search_local_pdfs", "_search_by_isbn", "mention_book", "is_trusted_match", "prefill_from_match"]

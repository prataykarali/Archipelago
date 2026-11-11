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

from dataclasses import asdict, dataclass, field  # noqa: F401
import logging  # noqa: F401
from pathlib import Path  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401

from .part01_logger import (
    _OPAC_URL,
    _STOPWORDS,
    HF_BLOB_BASE,
    HF_REPO_ID,
    ISBN_MIN_DIGITS,
    MATCH_KIND_CATALOG,
    MATCH_KIND_EXACT_ISBN,
    MATCH_KIND_HF,
    MATCH_KIND_LOCAL,
    MATCH_KIND_PEARSON,
    MATCH_KIND_REGISTRY,
    MAX_CANDIDATES,
    METADATA_TRUST_MIN_CONFIDENCE,
    MIN_FUZZY_SCORE,
    MIN_TOKEN_LENGTH,
    PDF_SUBDIRS,
    SOURCE_NAMES,
    MentionMatch,
    MentionResult,
    _best,
    _repo_root,
    _search_huggingface,
    _search_local_pdfs,
    _search_pearson,
    _search_registry,
    _search_resource_catalog,
    extract_isbn,
    logger,
    normalize_title,
    score_against,
    title_tokens,
)
from .part02_search_by_isbn import (
    _search_by_isbn,
    is_trusted_match,
    mention_book,
    prefill_from_match,
)

__all__ = [
    "HF_BLOB_BASE",
    "HF_REPO_ID",
    "ISBN_MIN_DIGITS",
    "MATCH_KIND_CATALOG",
    "MATCH_KIND_EXACT_ISBN",
    "MATCH_KIND_HF",
    "MATCH_KIND_LOCAL",
    "MATCH_KIND_PEARSON",
    "MATCH_KIND_REGISTRY",
    "MAX_CANDIDATES",
    "METADATA_TRUST_MIN_CONFIDENCE",
    "MIN_FUZZY_SCORE",
    "MIN_TOKEN_LENGTH",
    "PDF_SUBDIRS",
    "SOURCE_NAMES",
    "_OPAC_URL",
    "_STOPWORDS",
    "MentionMatch",
    "MentionResult",
    "_best",
    "_repo_root",
    "_search_by_isbn",
    "_search_huggingface",
    "_search_local_pdfs",
    "_search_pearson",
    "_search_registry",
    "_search_resource_catalog",
    "extract_isbn",
    "is_trusted_match",
    "logger",
    "mention_book",
    "normalize_title",
    "prefill_from_match",
    "score_against",
    "title_tokens",
]

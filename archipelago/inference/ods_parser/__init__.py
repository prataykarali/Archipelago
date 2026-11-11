"""ODS File Parser — Schema Validation & Cell Cleaning for Institutional Reports.

Implements:
  - ODS-1: Exact Field Schema Integrity (column header matching)
  - ODS-2: Empty Cells & Keyword Deduplication (whitespace strip, fallback, dedup)

Supports both the control-case ideal headers and the real report files under docs/:

  Subject (ideal):   Subject / Department, Title Count, Volume/Issue Count
  Subject (real):    Subject, Total Titles
  Subject (detail):  Subject, Title, Author, Copyright Year

  Journal (ideal):   Journal Title, ISSN, Issue Count, Publisher
  Journal (real):    Journal Title, Issue Number/Volume, Published Date, Issue Status

  Keyword (ideal):   Title, Author, Subject Keyword, Call Number
  Keyword (real):    biblionumber, Title, Author, Publisher, Accn Nos., ..."""

from __future__ import annotations

import csv  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401
from xml.etree import ElementTree as ET  # noqa: F401
import zipfile  # noqa: F401

from .part01_ods_schema_subject import (
    FIELD_FALLBACKS,
    ODS_SCHEMA_JOURNAL,
    ODS_SCHEMA_JOURNAL_ISSUES,
    ODS_SCHEMA_KEYWORD,
    ODS_SCHEMA_KEYWORD_TITLES,
    ODS_SCHEMA_REGISTRY,
    ODS_SCHEMA_SUBJECT,
    ODS_SCHEMA_SUBJECT_COUNTS,
    ODS_SCHEMA_VARIANTS,
    ODSParseError,
    _header_matches,
    _normalize_header,
    _score_schema,
    clean_ods_cell,
    clean_ods_row,
    read_ods_sheet,
    resolve_schema,
    sniff_schema,
    validate_ods_columns,
)
from .part02_deduplicate_keywords import (
    build_column_map,
    build_column_map_for_rows,
    deduplicate_keywords,
    strip_conversational_filler,
)

__all__ = [
    "FIELD_FALLBACKS",
    "ODS_SCHEMA_JOURNAL",
    "ODS_SCHEMA_JOURNAL_ISSUES",
    "ODS_SCHEMA_KEYWORD",
    "ODS_SCHEMA_KEYWORD_TITLES",
    "ODS_SCHEMA_REGISTRY",
    "ODS_SCHEMA_SUBJECT",
    "ODS_SCHEMA_SUBJECT_COUNTS",
    "ODS_SCHEMA_VARIANTS",
    "ODSParseError",
    "_header_matches",
    "_normalize_header",
    "_score_schema",
    "build_column_map",
    "build_column_map_for_rows",
    "clean_ods_cell",
    "clean_ods_row",
    "deduplicate_keywords",
    "read_ods_sheet",
    "resolve_schema",
    "sniff_schema",
    "strip_conversational_filler",
    "validate_ods_columns",
]

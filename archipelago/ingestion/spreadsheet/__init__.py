"""Idempotent library spreadsheet merge (ODS / CSV / XLSX → graph).

Implements the docs/01 §10 update loop with explicit per-record outcomes::

    CREATE   record is new to the catalogue
    UPDATE   record exists and a field genuinely changed
    UNCHANGED record already matches — no write performed
    RETIRE   record disappeared from the authoritative export

Re-running the same file must produce UNCHANGED for every row and must never
duplicate a node, a relationship, or a library record."""

from __future__ import annotations

from dataclasses import dataclass, field  # noqa: F401
import logging  # noqa: F401
from pathlib import Path  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401

from archipelago.ingestion.mention import normalize_title as _normalize_title  # noqa: F401

from .part01_logger import (
    _ID_STRIP_RE,
    _INT_FIELDS,
    _INT_RE,
    _STR_FIELDS,
    _TRUTHY,
    _YEAR_RE,
    FIELD_ALIASES,
    MAX_ROWS,
    MAX_SCAN_ROWS,
    OUTCOME_CREATE,
    OUTCOME_RETIRE,
    OUTCOME_UNCHANGED,
    OUTCOME_UPDATE,
    OUTCOMES,
    REQUIRED_FIELDS,
    MergePlan,
    RecordChange,
    _alias_map,
    _clean_str,
    _diff_fields,
    _fetch_existing,
    _slug,
    _to_bool,
    _to_int,
    find_header_row,
    load_records,
    logger,
    map_columns,
    normalize_header,
    plan_merge,
    read_rows,
    record_id_for,
    row_to_record,
)
from .part02_apply_merge import (
    _resource_params,
    _subject_params,
    _update_statements,
    _write_plan,
    apply_merge,
)

__all__ = [
    "FIELD_ALIASES",
    "MAX_ROWS",
    "MAX_SCAN_ROWS",
    "OUTCOMES",
    "OUTCOME_CREATE",
    "OUTCOME_RETIRE",
    "OUTCOME_UNCHANGED",
    "OUTCOME_UPDATE",
    "REQUIRED_FIELDS",
    "_ID_STRIP_RE",
    "_INT_FIELDS",
    "_INT_RE",
    "_STR_FIELDS",
    "_TRUTHY",
    "_YEAR_RE",
    "MergePlan",
    "RecordChange",
    "_alias_map",
    "_clean_str",
    "_diff_fields",
    "_fetch_existing",
    "_resource_params",
    "_slug",
    "_subject_params",
    "_to_bool",
    "_to_int",
    "_update_statements",
    "_write_plan",
    "apply_merge",
    "find_header_row",
    "load_records",
    "logger",
    "map_columns",
    "normalize_header",
    "plan_merge",
    "read_rows",
    "record_id_for",
    "row_to_record",
]

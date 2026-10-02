"""Idempotent library spreadsheet merge (ODS / CSV / XLSX → graph).

Implements the docs/01 §10 update loop with explicit per-record outcomes::

    CREATE   record is new to the catalogue
    UPDATE   record exists and a field genuinely changed
    UNCHANGED record already matches — no write performed
    RETIRE   record disappeared from the authoritative export

Re-running the same file must produce UNCHANGED for every row and must never
duplicate a node, a relationship, or a library record."""
from __future__ import annotations

import logging  # noqa: F401
import re  # noqa: F401
from dataclasses import dataclass, field  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401
from archipelago.ingestion.mention import normalize_title as _normalize_title  # noqa: F401

from .part01_logger import (  # noqa: F401
    logger,
    OUTCOME_CREATE,
    OUTCOME_UPDATE,
    OUTCOME_UNCHANGED,
    OUTCOME_RETIRE,
    OUTCOMES,
    MAX_ROWS,
    MAX_SCAN_ROWS,
    _ID_STRIP_RE,
    _YEAR_RE,
    _INT_RE,
    _TRUTHY,
    FIELD_ALIASES,
    REQUIRED_FIELDS,
    _STR_FIELDS,
    _INT_FIELDS,
    RecordChange,
    MergePlan,
    _slug,
    _clean_str,
    _to_int,
    _to_bool,
    normalize_header,
    _alias_map,
    map_columns,
    row_to_record,
    record_id_for,
    read_rows,
    find_header_row,
    load_records,
    _fetch_existing,
    _diff_fields,
    plan_merge,
)
from .part02_apply_merge import (  # noqa: F401
    apply_merge,
    _subject_params,
    _resource_params,
    _update_statements,
    _write_plan,
)

__all__ = ["logger", "OUTCOME_CREATE", "OUTCOME_UPDATE", "OUTCOME_UNCHANGED", "OUTCOME_RETIRE", "OUTCOMES", "MAX_ROWS", "MAX_SCAN_ROWS", "_ID_STRIP_RE", "_YEAR_RE", "_INT_RE", "_TRUTHY", "FIELD_ALIASES", "REQUIRED_FIELDS", "_STR_FIELDS", "_INT_FIELDS", "RecordChange", "MergePlan", "_slug", "_clean_str", "_to_int", "_to_bool", "normalize_header", "_alias_map", "map_columns", "row_to_record", "record_id_for", "read_rows", "find_header_row", "load_records", "_fetch_existing", "_diff_fields", "plan_merge", "apply_merge", "_subject_params", "_resource_params", "_update_statements", "_write_plan"]

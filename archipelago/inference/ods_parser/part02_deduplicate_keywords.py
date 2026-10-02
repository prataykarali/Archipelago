"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import re
from . import _deps as _rt  # noqa: F401


def deduplicate_keywords(keywords: list[str]) -> list[str]:
    """Canonical lowercase deduplication of keyword strings."""
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        cleaned = _rt.clean_ods_cell(kw).lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def strip_conversational_filler(query: str) -> str:
    """Strip filler from a user query for library-hours/credentials matching."""
    q = re.sub(
        r"\b(?:hi|hello|hey|please|thanks|thank you|could you|can you|i need|"
        r"tell me|what is|what's|whats|how to|how do i|where can i find|"
        r"give me|show me|looking for|i want|i need to find)\b",
        " ",
        query,
        flags=re.I,
    )
    q = re.sub(r"\s+", " ", q).strip(" ?!.,;:")
    return q


def build_column_map(header_row: list[str], schema: dict) -> dict[str, int]:
    """Build canonical field_name -> column_index map.

    Applies schema canonical_map so real-file headers become ideal field names.
    Optional columns that are absent are simply omitted from the map.
    """
    _rt.validate_ods_columns([header_row], schema)
    header_norm = [_rt._normalize_header(h) for h in header_row]
    optional = {_rt._normalize_header(h) for h in schema.get("optional_headers", ())}
    raw_map: dict[str, int] = {}

    for expected in schema["expected_headers"]:
        exp_norm = _rt._normalize_header(expected)
        for j, actual in enumerate(header_norm):
            if j in raw_map.values():
                continue
            if _rt._header_matches(exp_norm, actual, schema):
                raw_map[expected] = j
                break
        if expected not in raw_map and exp_norm not in optional:
            raise _rt.ODSParseError(
                f"[{schema['name']}] Could not map columns: {[expected]}. "
                f"Header row: {header_row}"
            )

    canonical_map = schema.get("canonical_map") or {}
    col_map: dict[str, int] = {}
    for field, idx in raw_map.items():
        canon = canonical_map.get(field, field)
        col_map[canon] = idx
    return col_map


def build_column_map_for_rows(rows: list[list[str]], preferred: str | None = None) -> tuple[dict, dict[str, int]]:
    """Resolve schema + column map for a full sheet."""
    schema = _rt.resolve_schema(rows, preferred=preferred)
    return schema, build_column_map(rows[0], schema)

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
  Keyword (real):    biblionumber, Title, Author, Publisher, Accn Nos., ...
"""
from __future__ import annotations

import csv
import os
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET


# ── ODS-1: Schema Definitions ─────────────────────────────────────────────

ODS_SCHEMA_SUBJECT = {
    "name": "subject_report",
    "expected_headers": [
        "subject / department", "title count", "volume/issue count",
    ],
    "optional_headers": (),
    "header_aliases": {
        "subject / department": (
            "subject", "department", "subject/department", "subject department",
            "subject / department",
        ),
        "title count": (
            "titles", "title count", "count of titles", "titles count",
            "total titles", "total title",
        ),
        "volume/issue count": (
            "volume/issue", "vol/issue", "volume count", "issue count",
            "volume/issue count",
        ),
    },
}

# Real KOHA export: Subject, Total Titles only (no volume column).
ODS_SCHEMA_SUBJECT_COUNTS = {
    "name": "subject_report",
    "expected_headers": ["subject", "total titles"],
    "optional_headers": (),
    "header_aliases": {
        "subject": ("subject", "department", "subject / department"),
        "total titles": ("total titles", "title count", "titles", "count of titles"),
    },
    "canonical_map": {
        "subject": "subject / department",
        "total titles": "title count",
    },
}

ODS_SCHEMA_JOURNAL = {
    "name": "journal_report",
    "expected_headers": [
        "journal title", "issn", "issue count", "publisher",
    ],
    "optional_headers": (),
    "header_aliases": {
        "journal title": ("journal", "title", "journal name", "publication title", "journal title"),
        "issn": ("issn", "issn number", "issn no"),
        "issue count": ("issues", "issue count", "number of issues", "count"),
        "publisher": ("publisher", "publisher name", "published by"),
    },
}

# Real KOHA journal issues export.
ODS_SCHEMA_JOURNAL_ISSUES = {
    "name": "journal_report",
    "expected_headers": [
        "journal title", "issue number/volume", "published date", "issue status",
    ],
    "optional_headers": ("published date", "issue status"),
    "header_aliases": {
        "journal title": ("journal title", "journal", "title"),
        "issue number/volume": (
            "issue number/volume", "issue number", "volume", "vol/issue",
            "issue number/volume",
        ),
        "published date": ("published date", "date", "pub date"),
        "issue status": ("issue status", "status"),
    },
    "canonical_map": {
        "journal title": "journal title",
        "issue number/volume": "issue count",
        "published date": "published date",
        "issue status": "issue status",
    },
}

ODS_SCHEMA_KEYWORD = {
    "name": "keyword_report",
    "expected_headers": [
        "title", "author", "subject keyword", "call number",
    ],
    "optional_headers": (),
    "header_aliases": {
        "title": ("title", "book title", "publication title", "item title"),
        "author": ("author", "authors", "author(s)", "creator"),
        "subject keyword": (
            "subject keyword", "subject", "keyword", "keywords",
            "subject heading", "tags",
        ),
        "call number": (
            "call number", "call no", "call #", "classification no",
            "shelf mark", "accn nos.", "accn nos", "accession",
        ),
    },
}

# Real KOHA "titles with keyword" export.
ODS_SCHEMA_KEYWORD_TITLES = {
    "name": "keyword_report",
    "expected_headers": ["title", "author"],
    "optional_headers": (
        "author", "publisher", "biblionumber", "accn nos.", "no. of copies",
    ),
    "header_aliases": {
        "title": ("title", "book title", "publication title"),
        "author": ("author", "authors", "author(s)"),
        "publisher": ("publisher",),
        "biblionumber": ("biblionumber", "biblio number"),
        "accn nos.": ("accn nos.", "accn nos", "accession"),
        "no. of copies": ("no. of copies", "copies"),
    },
    "canonical_map": {
        "title": "title",
        "author": "author",
        "publisher": "publisher",
        "accn nos.": "call number",
        "biblionumber": "biblionumber",
    },
}

# All accepted schema variants (sniff order: most specific first).
ODS_SCHEMA_VARIANTS: list[dict] = [
    ODS_SCHEMA_SUBJECT,
    ODS_SCHEMA_SUBJECT_COUNTS,
    ODS_SCHEMA_JOURNAL,
    ODS_SCHEMA_JOURNAL_ISSUES,
    ODS_SCHEMA_KEYWORD,
    ODS_SCHEMA_KEYWORD_TITLES,
]

ODS_SCHEMA_REGISTRY: dict[str, dict] = {
    "subject_report": ODS_SCHEMA_SUBJECT,
    "journal_report": ODS_SCHEMA_JOURNAL,
    "keyword_report": ODS_SCHEMA_KEYWORD,
}

FIELD_FALLBACKS: dict[str, str] = {
    "author": "Unknown / Institutional",
    "subject keyword": "uncategorized",
    "subject keyword ": "uncategorized",
    "publisher": "Unknown Publisher",
    "call number": "Unassigned",
    "issn": "0000-0000",
    "volume/issue count": "0",
    "title count": "0",
    "issue count": "0",
}


class ODSParseError(Exception):
    """Raised on ODS schema or parsing violations."""
    pass


def _normalize_header(h: str) -> str:
    """Lowercase, strip spaces, collapse multiple spaces."""
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _header_matches(expected: str, actual_normalized: str, schema: dict) -> bool:
    """Check if actual_normalized matches expected or any of its aliases."""
    exp = _normalize_header(expected)
    if actual_normalized == exp:
        return True
    aliases = schema.get("header_aliases", {}).get(expected, ())
    # Also try lookup under normalized expected key
    if not aliases:
        aliases = schema.get("header_aliases", {}).get(exp, ())
    for alias in aliases:
        if actual_normalized == _normalize_header(alias):
            return True
    return False


def read_ods_sheet(filepath: str) -> list[list[str]]:
    """Read all rows from the first sheet of an ODS/CSV/XLSX file."""
    if not os.path.exists(filepath):
        raise ODSParseError(f"ODS file not found: {filepath}")

    if filepath.lower().endswith(".csv"):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                return [row for row in csv.reader(f)]
        except Exception as e:
            raise ODSParseError(f"Failed to read CSV: {e}")

    if filepath.lower().endswith(".tsv"):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                return [row for row in csv.reader(f, delimiter="\t")]
        except Exception as e:
            raise ODSParseError(f"Failed to read TSV: {e}")

    if filepath.lower().endswith(".xlsx"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            ws = wb.active
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append([str(c) if c is not None else "" for c in row])
            wb.close()
            return rows
        except ImportError:
            raise ODSParseError("openpyxl not installed; cannot read .xlsx files.")
        except Exception as e:
            raise ODSParseError(f"Failed to read XLSX: {e}")

    try:
        with zipfile.ZipFile(filepath, "r") as z:
            if "content.xml" not in z.namelist():
                raise ODSParseError(f"No content.xml found in ODS: {filepath}")
            with z.open("content.xml") as f:
                tree = ET.parse(f)
    except zipfile.BadZipFile:
        raise ODSParseError(f"File is not a valid ODS/ZIP archive: {filepath}")
    except ODSParseError:
        raise
    except Exception as e:
        raise ODSParseError(f"Failed to parse ODS XML: {e}")

    root = tree.getroot()
    rows_data: list[list[str]] = []
    for table in root.iter("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table"):
        for row in table.iter("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row"):
            cells: list[str] = []
            for cell in row.iter("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell"):
                repeat_attr = cell.get(
                    "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}number-columns-repeated"
                )
                repeat = int(repeat_attr) if repeat_attr else 1
                # Cap pathological repeats used as sheet padding
                if repeat > 64:
                    repeat = 1 if not any(
                        "".join(p.itertext()).strip()
                        for p in cell.iter("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p")
                    ) else min(repeat, 8)
                text_parts = []
                for p in cell.iter("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"):
                    text_parts.append("".join(p.itertext()))
                cell_text = " ".join(text_parts).strip()
                for _ in range(repeat):
                    cells.append(cell_text)
            if any(c.strip() for c in cells):
                # Trim trailing empty padding cells
                while cells and not cells[-1].strip():
                    cells.pop()
                rows_data.append(cells)
        break

    if not rows_data:
        raise ODSParseError(f"No data rows found in ODS: {filepath}")
    return rows_data


def _score_schema(header_row: list[str], schema: dict) -> int:
    """Return number of required (non-optional) headers matched."""
    header_norm = [_normalize_header(c) for c in header_row]
    optional = {_normalize_header(h) for h in schema.get("optional_headers", ())}
    required = [
        _normalize_header(h)
        for h in schema["expected_headers"]
        if _normalize_header(h) not in optional
    ]
    matches = 0
    used: set[int] = set()
    for exp in required:
        for j, actual in enumerate(header_norm):
            if j in used:
                continue
            if _header_matches(exp, actual, schema):
                matches += 1
                used.add(j)
                break
    return matches if matches >= len(required) else -1


def resolve_schema(rows: list[list[str]], preferred: str | None = None) -> dict:
    """Pick the best matching schema variant for the header row."""
    if not rows or not rows[0]:
        raise ODSParseError("Empty row set — no header to validate.")

    header = rows[0]
    candidates = list(ODS_SCHEMA_VARIANTS)
    if preferred:
        preferred_variants = [s for s in candidates if s["name"] == preferred]
        other = [s for s in candidates if s["name"] != preferred]
        candidates = preferred_variants + other

    best: dict | None = None
    best_score = -1
    for schema in candidates:
        score = _score_schema(header, schema)
        if score > best_score:
            best_score = score
            best = schema
    if best is None or best_score < 0:
        raise ODSParseError(
            f"No matching ODS schema for headers: {[ _normalize_header(h) for h in header ]}. "
            "Record dropped from concept-linking."
        )
    return best


def sniff_schema(rows: list[list[str]]) -> str | None:
    """Auto-detect report type name from header row."""
    if not rows or not rows[0]:
        return None
    try:
        return resolve_schema(rows)["name"]
    except ODSParseError:
        return None


def validate_ods_columns(rows: list[list[str]], schema: dict) -> list[str]:
    """Validate header row against schema.

    Required columns must match; optional columns may be absent.
    Returns list of matched header labels (original casing) for required+found optional.
    """
    if not rows or not rows[0]:
        raise ODSParseError("Empty row set — no header to validate.")

    header_row = rows[0]
    header_norm = [_normalize_header(c) for c in header_row]
    optional = {_normalize_header(h) for h in schema.get("optional_headers", ())}
    schema_name = schema["name"]
    col_indices: list[int] = []
    matched_labels: list[str] = []

    for i, expected in enumerate(schema["expected_headers"]):
        exp_norm = _normalize_header(expected)
        found_idx = None
        for j, actual in enumerate(header_norm):
            if j in col_indices:
                continue
            if _header_matches(exp_norm, actual, schema):
                found_idx = j
                break
        if found_idx is None:
            if exp_norm in optional:
                continue
            raise ODSParseError(
                f"[{schema_name}] Missing column: '{expected}'. "
                f"Found headers: {header_norm}. Record dropped from concept-linking."
            )
        col_indices.append(found_idx)
        matched_labels.append(header_row[found_idx])

    return matched_labels


def clean_ods_cell(value: str, field_name: str = "") -> str:
    """Strip whitespace, apply fallback for empty strings."""
    cleaned = (value or "").strip()
    if not cleaned:
        fn = field_name.lower().strip()
        if fn in FIELD_FALLBACKS:
            return FIELD_FALLBACKS[fn]
        return ""
    return cleaned


def clean_ods_row(row: list[str], column_map: dict[str, int]) -> dict[str, str]:
    """Convert a raw row to cleaned canonical fields."""
    cleaned: dict[str, str] = {}
    for field_name, col_idx in column_map.items():
        raw = row[col_idx] if col_idx < len(row) else ""
        cleaned[field_name] = clean_ods_cell(raw, field_name)
    return cleaned


def deduplicate_keywords(keywords: list[str]) -> list[str]:
    """Canonical lowercase deduplication of keyword strings."""
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        cleaned = clean_ods_cell(kw).lower()
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
    validate_ods_columns([header_row], schema)
    header_norm = [_normalize_header(h) for h in header_row]
    optional = {_normalize_header(h) for h in schema.get("optional_headers", ())}
    raw_map: dict[str, int] = {}

    for expected in schema["expected_headers"]:
        exp_norm = _normalize_header(expected)
        for j, actual in enumerate(header_norm):
            if j in raw_map.values():
                continue
            if _header_matches(exp_norm, actual, schema):
                raw_map[expected] = j
                break
        if expected not in raw_map and exp_norm not in optional:
            raise ODSParseError(
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
    schema = resolve_schema(rows, preferred=preferred)
    return schema, build_column_map(rows[0], schema)

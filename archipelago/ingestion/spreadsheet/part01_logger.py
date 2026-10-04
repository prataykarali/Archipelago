"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
from typing import Any

from archipelago.ingestion.mention import normalize_title as _normalize_title

from . import _deps as _rt  # noqa: F401

logger = logging.getLogger("archipelago.ingestion.spreadsheet")


OUTCOME_CREATE = "CREATE"


OUTCOME_UPDATE = "UPDATE"


OUTCOME_UNCHANGED = "UNCHANGED"


OUTCOME_RETIRE = "RETIRE"


OUTCOMES = (OUTCOME_CREATE, OUTCOME_UPDATE, OUTCOME_UNCHANGED, OUTCOME_RETIRE)


MAX_ROWS = 20000


MAX_SCAN_ROWS = 200000


_ID_STRIP_RE = re.compile(r"[^a-z0-9]+")


_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")


_INT_RE = re.compile(r"-?\d+")


_TRUTHY = frozenset({"true", "yes", "y", "1", "t"})


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "booktitle", "name", "book", "worktitle"),
    "author": ("author", "authors", "creator", "by", "authorname"),
    "publisher": ("publisher", "imprint", "press", "pub"),
    "year": ("year", "copyrightyear", "pubyear", "publicationyear", "date", "copyright"),
    "isbn": ("isbn", "isbn13", "isbn10", "identifier", "biblionumber", "accno", "accession"),
    "subject": ("subject", "category", "topic", "dept", "department"),
    "total_copies": ("totalcopies", "nocopies", "noofcopies", "numberofcopies", "copies",
                     "holdings", "total"),
    "available_copies": ("availablecopies", "available", "availcopies", "availcopiescount",
                         "copiesavailable"),
    "overdue_items": ("overdueitems", "overdue", "onloanitems"),
     "call_number": ("callnumber", "classification"),
    "barcode": ("barcode", "itembarcode"),
    "rack": ("rack", "racknumber"),
    "shelf": ("shelf", "shelfnumber"),
    "location": ("location", "shelflocation", "librarylocation"),
    "is_periodical": ("isperiodical", "periodical", "journal", "serial"),
}


REQUIRED_FIELDS = ("title",)


_STR_FIELDS = ("title", "author", "publisher", "isbn", "subject", "call_number", "barcode", "rack", "shelf", "location")


_INT_FIELDS = ("total_copies", "available_copies", "overdue_items")


@dataclass
class RecordChange:
    """One row's merge outcome."""

    outcome: str
    record_id: str
    title: str
    fields: dict[str, Any] = field(default_factory=dict)
    changed_fields: list[str] = field(default_factory=list)
    source_row: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "record_id": self.record_id,
            "title": self.title,
            "fields": self.fields,
            "changed_fields": self.changed_fields,
            "source_row": self.source_row,
        }


@dataclass
class MergePlan:
    """The full dry-run diff for one spreadsheet."""

    source_file: str
    record_type: str
    detected_fields: list[str] = field(default_factory=list)
    changes: list[RecordChange] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """Outcome tallies for reporting."""
        return {outcome: 0 for outcome in OUTCOMES} | {
            c.outcome: sum(1 for x in self.changes if x.outcome == c.outcome)
            for c in self.changes
        }

    def summary(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "record_type": self.record_type,
            "detected_fields": self.detected_fields,
            "row_count": len(self.changes),
            "counts": {
                outcome: sum(1 for c in self.changes if c.outcome == outcome)
                for outcome in OUTCOMES
            },
            "errors": self.errors,
            "changes": [c.to_dict() for c in self.changes],
        }


def _slug(value: str) -> str:
    return _ID_STRIP_RE.sub("_", str(value or "").strip().lower()).strip("_")


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _to_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    match = _INT_RE.search(_clean_str(value))
    return int(match.group(0)) if match else default


def _to_bool(value: Any) -> bool:
    return _clean_str(value).lower() in _TRUTHY


def normalize_header(name: Any) -> str:
    """Lowercase, punctuation-free header key for alias matching."""
    return _ID_STRIP_RE.sub("", _clean_str(name).lower())


def _alias_map() -> dict[str, str]:
    """Normalized header → canonical field name."""
    out: dict[str, str] = {}
    for field_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            out[alias] = field_name
    return out


def map_columns(headers: list[Any]) -> tuple[dict[int, str], list[str]]:
    """Map column positions to canonical field names."""
    aliases = _alias_map()
    mapping: dict[int, str] = {}
    detected: list[str] = []
    for index, header in enumerate(headers):
        key = normalize_header(header)
        if not key:
            continue
        canonical = aliases.get(key)
        if canonical and canonical not in mapping.values():
            mapping[index] = canonical
            detected.append(canonical)
    return mapping, detected


def row_to_record(row: list[Any], mapping: dict[int, str]) -> dict[str, Any]:
    """Normalize one spreadsheet row into a canonical record."""
    record: dict[str, Any] = {}
    for index, canonical in mapping.items():
        value = row[index] if index < len(row) else None
        if canonical in _STR_FIELDS:
            record[canonical] = _clean_str(value)
        elif canonical in _INT_FIELDS:
            record[canonical] = _to_int(value)
        elif canonical == "is_periodical":
            record[canonical] = _to_bool(value)
        elif canonical == "year":
            text = _clean_str(value)
            match = _YEAR_RE.search(text)
            record[canonical] = match.group(1) if match else text
    return record


def record_id_for(record: dict[str, Any]) -> str:
    """Stable identity for a catalogue record.

    Uses the same ``res_<title-slug>`` scheme as ``catalog_ingest`` so a
    re-import updates the existing node instead of creating a duplicate.
    """
    title = _clean_str(record.get("title"))
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return f"res_{slug}" if slug else "res_unknown"


def read_rows(path: str | Path) -> list[list[Any]]:
    """Read an ODS/CSV/TSV/XLSX export into rows, reusing the shared parser."""
    from archipelago.ingestion.table_reader import read_table

    return read_table(path)


def find_header_row(rows: list[list[Any]], scan_rows: int = 12) -> int:
    """Locate the header row, tolerating report title lines above it."""
    best_index, best_hits = 0, 0
    for index, row in enumerate(rows[:scan_rows]):
        _, detected = map_columns(row)
        if len(detected) > best_hits:
            best_index, best_hits = index, len(detected)
    return best_index


def load_records(path: str | Path, max_rows: int = MAX_ROWS) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Load a spreadsheet into normalized records plus detected fields and errors."""
    errors: list[str] = []
    try:
        rows = read_rows(path)
    except (ValueError, OSError, UnicodeError) as exc:
        return [], [], [str(exc)]
    if not rows:
        return [], [], [f"No readable rows in {Path(path).name}."]

    header_index = find_header_row(rows)
    mapping, detected = map_columns(rows[header_index])
    if not mapping:
        return [], [], [
            f"{Path(path).name}: no recognisable columns "
            f"(expected one of: {', '.join(FIELD_ALIASES)})."
        ]
    missing = [f for f in REQUIRED_FIELDS if f not in detected]
    if missing:
        errors.append(f"{Path(path).name}: missing required column(s): {', '.join(missing)}")

    if errors:
        return [], detected, errors
    records: list[dict[str, Any]] = []
    for offset, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        if len(records) >= max_rows:
            errors.append(f"{Path(path).name}: truncated at {max_rows} rows.")
            break
        if not any(_clean_str(cell) for cell in row):
            continue
        record = row_to_record(row, mapping)
        if not record.get("title"):
            continue
        total, available = record.get("total_copies"), record.get("available_copies")
        if (total is not None and total < 0) or (available is not None and available < 0):
            errors.append(f"Row {offset}: copy counts cannot be negative.")
            continue
        if total is not None and available is not None and available > total:
            errors.append(f"Row {offset}: available copies exceed total copies.")
            continue
        record["_row"] = offset
        records.append(record)
    return records, detected, errors


def _fetch_existing(record_type: str) -> dict[str, dict[str, Any]]:
    """Read current catalogue state keyed by record id."""
    existing: dict[str, dict[str, Any]] = {}
    if record_type == "subject":
        query = "MATCH (s:Subject) RETURN s.id, s.subject_name, s.total_titles"
        name_field = "subject_name"
    else:
        query = (
            "MATCH (r:Resource) RETURN r.id, r.title, r.author, r.publisher, "
            "r.copyright_year, r.biblionumber, r.total_copies, r.available_copies, "
            "r.overdue_items, r.is_periodical"
        )
        name_field = "title"
    try:
        import kuzu

        from archipelago.inference import state as st
        if getattr(st, "db", None) is None:
            return existing
        conn = kuzu.Connection(st.db)
        res = conn.execute(query)
        while res.has_next():
            row = res.get_next()
            existing[str(row[0])] = {
                name_field: _clean_str(row[1]),
                "author": _clean_str(row[2]) if len(row) > 2 else "",
                "publisher": _clean_str(row[3]) if len(row) > 3 else "",
                "year": str(row[4]) if len(row) > 4 and row[4] is not None else "",
                "isbn": _clean_str(row[5]) if len(row) > 5 else "",
                "total_copies": row[6] if len(row) > 6 and row[6] is not None else 0,
                "available_copies": row[7] if len(row) > 7 and row[7] is not None else 0,
                "overdue_items": row[8] if len(row) > 8 and row[8] is not None else 0,
                "is_periodical": bool(row[9]) if len(row) > 9 else False,
            }
        if record_type == "resource":
            from archipelago.ingestion.catalog_locations import read_fields

            for record_id, details in read_fields(conn).items():
                if record_id in existing:
                    existing[record_id].update(details)
    except Exception as exc:
        logger.debug("Existing catalogue read unavailable: %s", exc)
    return existing


def _diff_fields(incoming: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Field names whose values genuinely changed."""
    changed: list[str] = []
    for key, value in incoming.items():
        if key.startswith("_"):
            continue
        before = current.get(key)
        if isinstance(value, int) or isinstance(before, int):
            if _to_int(value, -1) != _to_int(before, -2):
                changed.append(key)
        elif isinstance(value, bool):
            if bool(value) != bool(before):
                changed.append(key)
        else:
            if _clean_str(value) != _clean_str(before):
                changed.append(key)
    return changed


def plan_merge(
    path: str | Path,
    record_type: str = "resource",
    retire_missing: bool = False,
) -> MergePlan:
    """Compute the CREATE/UPDATE/UNCHANGED/RETIRE plan without writing anything.

    ``retire_missing`` is opt-in and defaults to False: a partial export (for
    example a 109-row holdings list) is not the authoritative full catalogue, so
    records absent from it must never be retired by default.
    """
    plan = MergePlan(source_file=Path(path).name, record_type=record_type)
    records, detected, errors = load_records(path)
    plan.detected_fields = detected
    plan.errors.extend(errors)
    if not records:
        return plan

    existing = _fetch_existing(record_type)
    # Title index lets a record match an existing node whose id predates a
    # change in id scheme, so re-imports do not duplicate.
    existing_by_title = {
        _normalize_title(v.get("title", "")): rid for rid, v in existing.items() if v.get("title")
    }

    seen_ids: set[str] = set()
    for record in records:
        rid = record_id_for(record)
        title_key = _normalize_title(record.get("title", ""))
        if rid not in existing and title_key in existing_by_title:
            rid = existing_by_title[title_key]
        fields = {k: v for k, v in record.items() if not k.startswith("_")}
        if rid in seen_ids:
            # Duplicate row inside the same file: report once, never write twice.
            plan.changes.append(RecordChange(
                outcome=OUTCOME_UNCHANGED,
                record_id=rid,
                title=fields.get("title", ""),
                fields=fields,
                source_row=record.get("_row", 0),
            ))
            continue
        seen_ids.add(rid)
        current = existing.get(rid)
        if current is None:
            outcome = OUTCOME_CREATE
            changed = sorted(fields)
        else:
            changed = _diff_fields(fields, current)
            outcome = OUTCOME_UPDATE if changed else OUTCOME_UNCHANGED
        plan.changes.append(RecordChange(
            outcome=outcome,
            record_id=rid,
            title=fields.get("title", ""),
            fields=fields,
            changed_fields=changed,
            source_row=record.get("_row", 0),
        ))

    if retire_missing and record_type == "resource":
        for rid, current in existing.items():
            if rid in seen_ids or not current.get("title"):
                continue
            plan.changes.append(RecordChange(
                outcome=OUTCOME_RETIRE,
                record_id=rid,
                title=current.get("title", ""),
                fields={k: v for k, v in current.items() if v not in ("", 0, False, None)},
            ))
    return plan

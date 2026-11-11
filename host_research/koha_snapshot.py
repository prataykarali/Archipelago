"""Validate Koha ODS exports and publish a dated metadata snapshot."""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import zipfile

from defusedxml import ElementTree as ET
import requests

BUCKET = "archipelago-cache"
OBJECT = "koha_catalog_snapshot.json"
SNAPSHOT_SCHEMA_VERSION = 2
STALE_AFTER_DAYS = 2
REQUEST_TIMEOUT_SECONDS = 30
MAX_REPEATED_CELLS = 32
TABLE_NS = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
TEXT_NS = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
FILES = {
    "holdings": "Titles List with specified keyword-reportresults.ods",
    "journal_issues": "JOURNALS TITLES AND ISSUE COUNTS-reportresults.ods",
    "subject_counts": "SUBJECT-WISE TITLE COUNT-reportresults.ods",
    "subject_titles": "SUBJECT-WISE TITLE COUNT-reportresults (1).ods",
}
IDENTIFIERS_FILE = "catalog_identifiers.csv"
IDENTIFIER_FIELDS = ("biblionumber", "isbn", "call_number", "rack_number")
OPAC_DETAIL_URL = "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber="
OPTIONAL_HOLDINGS_FIELDS = ("Available Barcodes", "Overdue Items")
HEADERS = {
    "holdings": (
        "biblionumber",
        "Title",
        "Author",
        "Publisher",
        "Accn Nos.",
        "No. of copies",
        "Available Copies",
    ),
    "journal_issues": ("Journal Title", "Issue Number/Volume", "Published Date", "Issue Status"),
    "subject_counts": ("Subject", "Total Titles"),
    "subject_titles": ("Subject", "Title", "Author", "Copyright Year"),
}


def read_ods(path: Path) -> list[list[str]]:
    """Read the first ODS table with bounded repeats and hardened XML parsing."""
    with zipfile.ZipFile(path) as archive:
        content = archive.read("content.xml")
    root = ET.fromstring(content)
    table = root.find(f".//{TABLE_NS}table")
    if table is None:
        raise ValueError(f"No table in {path.name}")
    rows = []
    for ods_row in table.findall(f".//{TABLE_NS}table-row"):
        cells: list[str] = []
        for cell in ods_row.findall(f"{TABLE_NS}table-cell"):
            repeat = min(
                int(cell.get(f"{TABLE_NS}number-columns-repeated", "1")), MAX_REPEATED_CELLS
            )
            value = " ".join("".join(p.itertext()) for p in cell.findall(f".//{TEXT_NS}p")).strip()
            cells.extend([value] * repeat)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(cells)
    if not rows:
        raise ValueError(f"No rows in {path.name}")
    return rows


def _valid_isbn(value: str) -> bool:
    """Accept only ISBN-10 or ISBN-13 values with a valid check digit."""
    cleaned = value.replace("-", "").replace(" ", "").upper()
    if len(cleaned) == 10:
        if not cleaned[:9].isdigit() or not (cleaned[-1].isdigit() or cleaned[-1] == "X"):
            return False
        check = sum((10 - index) * int(digit) for index, digit in enumerate(cleaned[:9]))
        check += 10 if cleaned[-1] == "X" else int(cleaned[-1])
        return check % 11 == 0
    if len(cleaned) == 13 and cleaned.isdigit():
        check = sum(
            int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(cleaned)
        )
        return check % 10 == 0
    return False


def _catalog_identifiers(path: Path) -> dict[str, dict[str, str]]:
    """Read librarian-supplied identifiers without inferring missing ISBNs or racks."""
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not set(IDENTIFIER_FIELDS).issubset(reader.fieldnames):
            raise ValueError(f"Unexpected columns in {path.name}")
        records: dict[str, dict[str, str]] = {}
        for row in reader:
            identifier = (row.get("biblionumber") or "").strip()
            if not identifier.isdigit() or identifier in records:
                raise ValueError(f"Invalid or duplicate biblionumber in {path.name}")
            isbn = (row.get("isbn") or "").strip()
            if isbn and not _valid_isbn(isbn):
                raise ValueError(f"Invalid ISBN for biblionumber {identifier}")
            records[identifier] = {
                "isbn": isbn,
                "call_number": (row.get("call_number") or "").strip(),
                "rack_number": (row.get("rack_number") or "").strip(),
            }
    return records


def build_snapshot(directory: Path) -> dict[str, object]:
    """Build a public metadata snapshot with source dates and checksums."""
    snapshot: dict[str, object] = {
        "source": "authorized_koha_ods_export",
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "exports": {},
    }
    latest: datetime | None = None
    oldest: datetime | None = None
    identifiers_path = directory / IDENTIFIERS_FILE
    identifiers = _catalog_identifiers(identifiers_path)
    for kind, filename in FILES.items():
        path = directory / filename
        rows = read_ods(path)
        header = rows[0]
        expected = HEADERS[kind]
        if not all(name in header for name in expected):
            raise ValueError(f"Unexpected {kind} columns in {filename}")
        indexes = [header.index(name) for name in expected]
        records: list[dict[str, str]] = []
        for row in rows[1:]:
            if not any(row[index].strip() for index in indexes if index < len(row)):
                continue
            record = dict(
                zip(
                    expected,
                    (row[index] if index < len(row) else "" for index in indexes),
                    strict=True,
                )
            )
            if kind == "holdings":
                for field in OPTIONAL_HOLDINGS_FIELDS:
                    if field in header:
                        index = header.index(field)
                        record[field] = row[index] if index < len(row) else ""
                identifier = record["biblionumber"]
                if not identifier.isdigit():
                    raise ValueError(f"Invalid biblionumber in {filename}")
                record.update(identifiers.get(identifier, dict.fromkeys(IDENTIFIER_FIELDS[1:], "")))
                record["opac_url"] = f"{OPAC_DETAIL_URL}{identifier}"
            records.append(record)
        if not records:
            raise ValueError(f"No records in {filename}")
        if kind == "holdings":
            unknown = set(identifiers) - {record["biblionumber"] for record in records}
            if unknown:
                raise ValueError(f"Identifier rows absent from {filename}: {len(unknown)}")
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        latest = max(latest, modified) if latest else modified
        oldest = min(oldest, modified) if oldest else modified
        snapshot[kind] = records
        snapshot["exports"][kind] = {
            "filename": filename,
            "modified_at": modified.isoformat(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "count": len(records),
        }
    if identifiers_path.is_file():
        snapshot["exports"]["catalog_identifiers"] = {
            "filename": IDENTIFIERS_FILE,
            "modified_at": datetime.fromtimestamp(
                identifiers_path.stat().st_mtime, UTC
            ).isoformat(),
            "sha256": hashlib.sha256(identifiers_path.read_bytes()).hexdigest(),
            "count": len(identifiers),
        }
    snapshot["catalog_identity_status"] = {
        "covered_holdings": sum(
            1 for row in snapshot["holdings"] if row["biblionumber"] in identifiers
        ),
        "total_holdings": len(snapshot["holdings"]),
        "complete_inventory": False,
        "note": "Keyword-filtered holdings export; ISBN and rack require librarian-supplied identifiers.",
    }
    assert latest is not None and oldest is not None
    snapshot["source_updated_at"] = latest.isoformat()
    snapshot["oldest_export_at"] = oldest.isoformat()
    snapshot["snapshot_created_at"] = datetime.now(UTC).isoformat()
    snapshot["stale"] = datetime.now(UTC) - oldest > timedelta(days=STALE_AFTER_DAYS)
    return snapshot


def _storage_config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("Supabase private storage is not configured")
    return url, key


def load_snapshot() -> dict[str, object] | None:
    """Read the latest published Koha metadata from private Supabase Storage."""
    url, key = _storage_config()
    response = requests.get(
        f"{url}/storage/v1/object/{BUCKET}/{OBJECT}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code in {400, 404} and response.json().get("code") == "NoSuchKey":
        return None
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("source") != "authorized_koha_ods_export":
        raise ValueError("Invalid Koha snapshot")
    oldest = data.get("oldest_export_at")
    if isinstance(oldest, str):
        data["stale"] = datetime.now(UTC) - datetime.fromisoformat(oldest) > timedelta(
            days=STALE_AFTER_DAYS
        )
    return data


def save_snapshot(snapshot: dict[str, object]) -> bool:
    """Upsert changed metadata only; never upload a source document or PDF."""
    existing = load_snapshot()
    if (
        existing
        and existing.get("exports") == snapshot.get("exports")
        and existing.get("schema_version") == snapshot.get("schema_version")
    ):
        return False
    url, key = _storage_config()
    response = requests.put(
        f"{url}/storage/v1/object/{BUCKET}/{OBJECT}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "x-upsert": "true",
        },
        data=json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return True

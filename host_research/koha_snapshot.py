"""Validate Koha ODS exports and publish a dated metadata snapshot."""

from __future__ import annotations

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
            repeat = min(int(cell.get(f"{TABLE_NS}number-columns-repeated", "1")), MAX_REPEATED_CELLS)
            value = " ".join("".join(p.itertext()) for p in cell.findall(f".//{TEXT_NS}p")).strip()
            cells.extend([value] * repeat)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(cells)
    if not rows:
        raise ValueError(f"No rows in {path.name}")
    return rows


def build_snapshot(directory: Path) -> dict[str, object]:
    """Build a public metadata snapshot with source dates and checksums."""
    snapshot: dict[str, object] = {"source": "authorized_koha_ods_export", "exports": {}}
    latest: datetime | None = None
    oldest: datetime | None = None
    for kind, filename in FILES.items():
        path = directory / filename
        rows = read_ods(path)
        header = rows[0]
        expected = HEADERS[kind]
        if not all(name in header for name in expected):
            raise ValueError(f"Unexpected {kind} columns in {filename}")
        indexes = [header.index(name) for name in expected]
        records = [
            dict(
                zip(
                    expected,
                    (row[index] if index < len(row) else "" for index in indexes),
                    strict=True,
                )
            )
            for row in rows[1:]
            if any(row[index].strip() for index in indexes if index < len(row))
        ]
        if not records:
            raise ValueError(f"No records in {filename}")
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
    if existing and existing.get("exports") == snapshot.get("exports"):
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

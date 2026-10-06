"""Validated, persistent library holdings imports for the hosted app."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import requests
from runtime_paths import runtime_cache_dir
from supabase_service_headers import service_headers

ROOT = Path(__file__).resolve().parent
CACHE = runtime_cache_dir()
BUCKET = "archipelago-cache"
OBJECT = "library_inventory.json"
MAX_ROWS = 20_000
REQUIRED = {"book_id", "title", "total_copies", "available_copies"}
TEXT_FIELDS = (
    "book_id",
    "title",
    "authors",
    "publisher",
    "subject",
    "publication_year",
    "category",
    "availability",
    "take_home",
    "location",
    "accession",
    "call_number",
    "rack",
    "shelf",
    "doc_id",
)


def parse_inventory_csv(payload: bytes) -> list[dict]:
    """Validate a holdings CSV and normalize it to public library records."""
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 CSV file.") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = {str(header or "").strip().lower() for header in (reader.fieldnames or [])}
    missing = REQUIRED - headers
    if missing:
        raise ValueError("CSV is missing required columns: " + ", ".join(sorted(missing)))

    rows = []
    seen = set()
    for row_number, raw in enumerate(reader, start=2):
        if row_number > MAX_ROWS + 1:
            raise ValueError(f"CSV exceeds the {MAX_ROWS:,} row limit.")
        row = {str(k or "").strip().lower(): str(v or "").strip() for k, v in raw.items()}
        book_id = row.get("book_id", "")[:160]
        title = row.get("title", "")[:500]
        if not book_id or not title:
            raise ValueError(f"Row {row_number} needs a book_id and title.")
        if book_id in seen:
            raise ValueError(f"Duplicate book_id on row {row_number}.")
        seen.add(book_id)
        try:
            total = int(row.get("total_copies", ""))
            available = int(row.get("available_copies", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Row {row_number} has invalid copy counts.") from exc
        if total < 0 or available < 0 or available > total:
            raise ValueError(f"Row {row_number} must have 0 ≤ available_copies ≤ total_copies.")
        item = {key: row.get(key, "")[:500] for key in TEXT_FIELDS}
        item.update(
            {
                "book_id": book_id,
                "title": title,
                "total_copies": total,
                "available_copies": available,
                "accession": (row.get("accession") or book_id)[:160],
                "available_ratio": f"{available} / {total}",
                "no_of_copies": total,
            }
        )
        rows.append(item)
    if not rows:
        raise ValueError("CSV contains no holdings rows.")
    return rows


def inventory_stats(rows: list[dict]) -> dict[str, int]:
    """Summarize a normalized holdings list."""
    return {
        "total_records": len(rows),
        "total_copies": sum(int(row["total_copies"]) for row in rows),
        "available_copies": sum(int(row["available_copies"]) for row in rows),
    }


def load_inventory() -> list[dict] | None:
    """Load the latest import from Supabase Storage or the runtime cache."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / OBJECT
    if not path.is_file():
        url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
        key = (
            os.environ.get("SUPABASE_SECRET_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or ""
        ).strip()
        if url and key:
            try:
                response = requests.get(
                    f"{url}/storage/v1/object/{BUCKET}/{OBJECT}",
                    headers=service_headers(key),
                    timeout=15,
                )
                if response.status_code == 200:
                    path.write_bytes(response.content)
            except requests.RequestException:
                pass
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_inventory(rows: list[dict]) -> None:
    """Persist holdings to the private Supabase cache bucket and local cache."""
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    ).strip()
    if not url or not key:
        raise RuntimeError("Supabase private storage is not configured.")
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {**service_headers(key, json_body=True), "x-upsert": "true"}
    response = requests.put(
        f"{url}/storage/v1/object/{BUCKET}/{OBJECT}", headers=headers, data=payload, timeout=30
    )
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"Supabase inventory save failed ({response.status_code}).")
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / OBJECT).write_bytes(payload)

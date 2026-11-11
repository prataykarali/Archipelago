"""Server-only persistence for staff research intake records."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

STORE_PATH = "/rest/v1/research_intake_records"
STORE_TIMEOUT_SECONDS = 10
MAX_RECORDS = 200
GRAPH_PAGE_SIZE = 400
GRAPH_MAX_RECORDS = 2000
COUNT_KINDS = ("paper", "institutional_page")
SEARCH_TERMS_LIMIT = 6
SEARCH_RECORD_LIMIT = 150
TOPIC_PAGE_SIZE = 500
MAX_TOPIC_ROWS = 10000
RECENT_PAPER_SCAN = 40
SEARCH_WORD = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)
SEARCH_STOPWORDS = frozenset(
    {
        "about",
        "and",
        "are",
        "between",
        "can",
        "does",
        "explain",
        "for",
        "from",
        "give",
        "how",
        "into",
        "please",
        "tell",
        "the",
        "this",
        "using",
        "what",
        "when",
        "where",
        "which",
        "why",
        "with",
    }
)
RECORD_COLUMNS = (
    "id,record_key,kind,title,source_url,source_name,topic,content,published_at,metadata,updated_at"
)


def _endpoint() -> tuple[str, dict[str, str]]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        raise RuntimeError("Research intake storage is not configured")
    return f"{url}{STORE_PATH}", {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def save_records(records: list[dict[str, object]]) -> int:
    """Upsert deduplicated source records; fail if persistence fails."""
    if not records:
        return 0
    endpoint, headers = _endpoint()
    response = requests.post(
        endpoint,
        params={"on_conflict": "record_key"},
        data=json.dumps(records),
        headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return len(records)


def list_records(kind: str | None = None, topic: str | None = None) -> list[dict[str, Any]]:
    """Read recently ingested records for the research workspace."""
    endpoint, headers = _endpoint()
    params: dict[str, str | int] = {
        "select": RECORD_COLUMNS,
        "order": "updated_at.desc",
        "limit": MAX_RECORDS,
    }
    if kind:
        params["kind"] = f"eq.{kind}"
    if topic:
        params["topic"] = f"eq.{topic}"
    response = requests.get(endpoint, params=params, headers=headers, timeout=STORE_TIMEOUT_SECONDS)
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected research storage response")
    return [row for row in rows if _active(row)]


def get_record(record_key: str) -> dict[str, Any] | None:
    """Read one saved source by its stable key."""
    endpoint, headers = _endpoint()
    response = requests.get(
        endpoint,
        params={"select": RECORD_COLUMNS, "record_key": f"eq.{record_key}", "limit": 1},
        headers=headers,
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected research storage response")
    return rows[0] if rows and _active(rows[0]) else None


def _active(row: dict[str, Any]) -> bool:
    """Hide a source only after a confirmed retirement."""
    metadata = row.get("metadata") or {}
    return not isinstance(metadata, dict) or metadata.get("active") is not False


def list_managed_college_records() -> list[dict[str, Any]]:
    """Read pages previously managed by the scheduled public campus sync."""
    rows, _truncated = list_graph_records(include_inactive=True)
    return [
        row
        for row in rows
        if row.get("kind") == "institutional_page"
        and isinstance(row.get("metadata"), dict)
        and row["metadata"].get("sync_scope") == "campus_public"
    ]


def retire_record(row: dict[str, Any], checked_at: str) -> None:
    """Remove a confirmed missing campus page from active graph and retrieval."""
    endpoint, headers = _endpoint()
    metadata = {**row.get("metadata", {}), "active": False, "retired_at": checked_at}
    response = requests.patch(
        endpoint,
        params={"record_key": f"eq.{row['record_key']}"},
        data=json.dumps({"metadata": metadata}),
        headers=headers,
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def list_graph_records(*, include_inactive: bool = False) -> tuple[list[dict[str, Any]], bool]:
    """Page through saved sources for the durable research graph projection."""
    endpoint, headers = _endpoint()
    rows: list[dict[str, Any]] = []
    while len(rows) < GRAPH_MAX_RECORDS:
        response = requests.get(
            endpoint,
            params={
                "select": RECORD_COLUMNS,
                "order": "updated_at.desc",
                "limit": GRAPH_PAGE_SIZE,
                "offset": len(rows),
            },
            headers=headers,
            timeout=STORE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError("Unexpected research graph storage response")
        rows.extend(page)
        if len(page) < GRAPH_PAGE_SIZE:
            return (rows if include_inactive else [row for row in rows if _active(row)]), False
    return (rows if include_inactive else [row for row in rows if _active(row)]), True


def search_records(query: str, kind: str | None = "paper") -> list[dict[str, Any]]:
    """Find matching sources in the entire store, including older intakes."""
    terms = list(
        dict.fromkeys(
            term for term in SEARCH_WORD.findall(query.casefold()) if term not in SEARCH_STOPWORDS
        )
    )[:SEARCH_TERMS_LIMIT]
    if not terms:
        return []
    filters = ",".join(
        f"{column}.ilike.*{term}*" for term in terms for column in ("title", "topic", "content")
    )
    endpoint, headers = _endpoint()
    params: dict[str, str | int] = {
        "select": RECORD_COLUMNS,
        "or": f"({filters})",
        "order": "updated_at.desc",
        "limit": SEARCH_RECORD_LIMIT,
    }
    if kind:
        params["kind"] = f"eq.{kind}"
    response = requests.get(
        endpoint,
        params=params,
        headers=headers,
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected research search response")
    return [row for row in rows if _active(row)]


def count_records() -> dict[str, int]:
    """Return aggregate counts without sending research records to public pages."""
    endpoint, headers = _endpoint()
    counts: dict[str, int] = {}
    for kind in COUNT_KINDS:
        response = requests.get(
            endpoint,
            params={"select": "id", "kind": f"eq.{kind}", "limit": 1},
            headers={**headers, "Prefer": "count=exact"},
            timeout=STORE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content_range = response.headers.get("Content-Range", "")
        if "/" not in content_range:
            raise ValueError("Research storage omitted the record count")
        counts[kind] = int(content_range.rsplit("/", 1)[-1])
    return counts


def list_topic_inventory(max_rows: int = MAX_TOPIC_ROWS) -> list[dict[str, Any]]:
    """Read the live topic view across all active ingested papers."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    _, headers = _endpoint()
    if not url:
        raise RuntimeError("Research topic storage is not configured")
    rows: list[dict[str, Any]] = []
    while len(rows) < max_rows:
        page_size = min(TOPIC_PAGE_SIZE, max_rows - len(rows))
        response = requests.get(
            f"{url}/rest/v1/research_topic_inventory",
            params={
                "select": "topic,paper_count,last_ingested_at",
                "order": "last_ingested_at.desc",
                "limit": page_size,
                "offset": len(rows),
            },
            headers=headers,
            timeout=STORE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError("Unexpected research topic response")
        rows.extend(page)
        if len(page) < page_size:
            break
    return rows


def recent_papers(limit: int = 8) -> list[dict[str, Any]]:
    """Return source links and titles for the public library activity panel."""
    endpoint, headers = _endpoint()
    response = requests.get(
        endpoint,
        params={
            "select": "title,topic,source_url,source_name,updated_at,metadata",
            "kind": "eq.paper",
            "order": "updated_at.desc",
            "limit": RECENT_PAPER_SCAN,
        },
        headers=headers,
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected recent paper response")
    papers = []
    for row in rows:
        if not _active(row) or not str(row.get("source_url") or "").startswith("https://"):
            continue
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        paper = {key: row.get(key) for key in ("title", "topic", "source_url", "source_name")}
        paper["okf_status"] = (
            "processed" if metadata.get("ingestion_pipeline") == "local_indra_v3" else "metadata"
        )
        paper["verified_fields"] = len(metadata.get("verified_extractions") or [])
        paper["access_state"] = metadata.get("access_state") or "METADATA_ONLY"
        papers.append(paper)
        if len(papers) == limit:
            break
    return papers

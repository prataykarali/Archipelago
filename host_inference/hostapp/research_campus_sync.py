"""Refresh approved public campus pages and retire only confirmed 404/410 URLs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from .research_campus_sources import ALLOWED_HOSTS
from .research_intake import (
    HTTP_TIMEOUT_SECONDS,
    MAX_ROBOTS_BYTES,
    SOURCE_USER_AGENT,
    fetch_college_page,
)
from .research_intake_store import list_managed_college_records, retire_record, save_records

MAX_CAMPUS_PAGES = 80
CAMPUS_WORKERS = 8
RETIRED_HTTP_CODES = frozenset({404, 410})


def _confirmed_gone(url: str) -> bool:
    """Require a successful robots check and an explicit gone response."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        return False
    robots_response = requests.get(
        f"https://{parsed.hostname}/robots.txt",
        headers={"User-Agent": SOURCE_USER_AGENT},
        allow_redirects=False,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    if robots_response.status_code != 200 or len(robots_response.content) > MAX_ROBOTS_BYTES:
        return False
    robots = RobotFileParser()
    robots.parse(robots_response.text.splitlines())
    if not robots.can_fetch(SOURCE_USER_AGENT, url):
        return False
    response = requests.get(
        url,
        headers={"User-Agent": SOURCE_USER_AGENT},
        allow_redirects=False,
        timeout=HTTP_TIMEOUT_SECONDS,
        stream=True,
    )
    try:
        return response.status_code in RETIRED_HTTP_CODES
    finally:
        response.close()


def sync_public_campus_pages(candidates: list[str], *, complete_sitemap: bool) -> dict[str, object]:
    """Ingest a daily snapshot; retire missing pages only after direct confirmation."""
    selected = sorted(set(candidates))[:MAX_CAMPUS_PAGES]
    checked_at = datetime.now(UTC).isoformat()
    records: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    gone: set[str] = set()

    def fetch(url: str) -> tuple[str, dict[str, object] | None, str | None]:
        try:
            return url, fetch_college_page(url, None), None
        except (requests.RequestException, ValueError) as exc:
            try:
                if _confirmed_gone(url):
                    return url, None, "gone"
            except requests.RequestException:
                pass
            return url, None, type(exc).__name__

    with ThreadPoolExecutor(max_workers=CAMPUS_WORKERS) as pool:
        for future in as_completed(pool.submit(fetch, url) for url in selected):
            url, record, error = future.result()
            if record:
                metadata = dict(record.get("metadata") or {})
                metadata.update({"sync_scope": "campus_public", "active": True})
                record["metadata"] = metadata
                records.append(record)
            elif error == "gone":
                gone.add(url)
            elif error:
                errors.append({"source": url, "error": error})
    saved = save_records(records)
    retired = 0
    if complete_sitemap:
        candidate_set = set(candidates)
        for row in list_managed_college_records():
            url = str(row.get("source_url") or "")
            if url in candidate_set and url not in gone:
                continue
            if (row.get("metadata") or {}).get("active") is False:
                continue
            try:
                if url in gone or _confirmed_gone(url):
                    retire_record(row, checked_at)
                    retired += 1
            except requests.RequestException:
                errors.append({"source": url, "error": "retirement_check_unavailable"})
    return {
        "attempted": len(selected),
        "saved": saved,
        "retired": retired,
        "errors": errors,
        "complete_sitemap": complete_sitemap,
        "truncated": len(candidates) > MAX_CAMPUS_PAGES,
    }

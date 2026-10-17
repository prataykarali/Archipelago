"""Bounded public-page Actor probes for institutional catalog sources."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import json
import re
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

from archipelago.ingestion.apify_source import (
    actor_failure_state,
    actor_run_status,
    fetch_dataset_items,
    run_actor,
)

ACTOR_ID = "apify/website-content-crawler"
MAX_PAGES = 1
MAX_ITEMS = 1
REQUEST_TIMEOUT_SECONDS = 20
MAX_CHARGE_USD = Decimal("1.00")
OPAC_HOST = "uemk-opac.l2c2.co.in"
IEM_HOST = "iemcrp.com"
IEM_PORTAL = "https://www.iemcrp.com/iemEn/aerp_libreay_chy20200726.jsp"
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BIB_PATTERN = re.compile(r"(?:\?|&)biblionumber=(\d+)(?:&|$)")
CHALLENGE_MARKERS = ("cf-turnstile", "checking your browser", "access denied")
TERMINAL_STATES = frozenset(("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"))


def _source_url(source: str, query: str) -> tuple[str, set[str]]:
    if source == "opac":
        return (
            f"http://{OPAC_HOST}/cgi-bin/koha/opac-search.pl?q={quote(query)}",
            {OPAC_HOST},
        )
    if source == "iemcrp":
        return IEM_PORTAL, {IEM_HOST}
    raise ValueError(f"unknown institutional source: {source}")


def _official_url(url: str, hosts: set[str]) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and any(
        host == permitted or host.endswith(f".{permitted}") for permitted in hosts
    )


def extract_public_records(source: str, items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return source-linked records; never infer a holding from a navigation link."""
    _, hosts = _source_url(source, "")
    found: dict[str, dict[str, str]] = {}
    for item in items:
        page_url = str(item.get("url") or item.get("loadedUrl") or "")
        if not _official_url(page_url, hosts):
            continue
        content = str(item.get("markdown") or item.get("text") or "")
        if any(marker in content.lower() for marker in CHALLENGE_MARKERS):
            continue
        for title, href in LINK_PATTERN.findall(content):
            target = urljoin(page_url, href)
            if not _official_url(target, hosts):
                continue
            clean_title = " ".join(title.split()).strip()
            if not clean_title:
                continue
            if source == "opac":
                bib = BIB_PATTERN.search(target)
                if bib is None:
                    continue
                source_id = bib.group(1)
                kind = "catalog_book"
            else:
                source_id = hashlib.sha256(target.encode()).hexdigest()
                kind = "resource_link"
            found[source_id] = {
                "source_record_id": source_id,
                "title": clean_title,
                "source_url": target,
                "kind": kind,
                "availability": "unknown",
            }
    return list(found.values())


def probe_public_source(
    source: str,
    *,
    query: str = "computer science",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Start or resume one capped Actor run and classify its actual dataset."""
    url, hosts = _source_url(source, query)
    if run_id is None:
        run = run_actor(
            ACTOR_ID,
            {
                "startUrls": [{"url": url}],
                "crawlerType": "cheerio",
                "maxCrawlDepth": 0,
                "maxCrawlPages": MAX_PAGES,
                "respectRobotsTxtFile": True,
                "requestTimeoutSecs": REQUEST_TIMEOUT_SECONDS,
                "maxRequestRetries": 0,
                "maxSessionRotations": 0,
                "maxConcurrency": 1,
                "dynamicContentWaitSecs": 0,
                "proxyConfiguration": {"useApifyProxy": True},
            },
            approved=True,
            max_total_charge_usd=MAX_CHARGE_USD,
            max_items=MAX_ITEMS,
            allowed_hosts=hosts,
        )
        if not run.get("run_id"):
            return {
                "source": source,
                "target_url": url,
                "actor_id": ACTOR_ID,
                "actor_run": run,
                "checked_at": datetime.now(UTC).isoformat(),
                "records": [],
                "dataset_items": 0,
                "raw_snapshot_sha256": None,
                "source_status": "actor_start_failed",
            }
        run_id = str(run["run_id"])
    run = actor_run_status(run_id)
    report: dict[str, Any] = {
        "source": source,
        "target_url": url,
        "actor_id": ACTOR_ID,
        "actor_run": run,
        "checked_at": datetime.now(UTC).isoformat(),
        "records": [],
        "dataset_items": 0,
        "raw_snapshot_sha256": None,
        "source_status": "pending" if run["status"] not in TERMINAL_STATES else "unavailable",
    }
    if run["status"] != "SUCCEEDED" or not run.get("dataset_id"):
        if run["status"] in TERMINAL_STATES:
            report["failure_state"] = actor_failure_state(run_id)
        return report
    items = fetch_dataset_items(str(run["dataset_id"]), limit=MAX_ITEMS)
    report["dataset_items"] = len(items)
    report["raw_snapshot_sha256"] = hashlib.sha256(
        json.dumps(items, sort_keys=True, default=str).encode()
    ).hexdigest()
    records = extract_public_records(source, items)
    report["records"] = records
    failure = actor_failure_state(run_id) if not records else None
    report["failure_state"] = failure
    report["source_status"] = (
        "live_records" if records else "source_request_failed" if failure else "no_usable_records"
    )
    return report

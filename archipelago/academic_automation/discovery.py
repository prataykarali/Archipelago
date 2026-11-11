"""Live OPAC discovery, identifier matching, and permitted candidate queuing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

from .candidate_from_source import queue_verified_source
from .evidence import record_source_evidence
from .external_sources import (
    crossref_article,
    europe_pmc_open_article,
    open_library_edition,
    open_textbook_edition,
)
from .open_books import find_open_book, queue_open_book
from .reconcile import reconcile
from .store import AcademicStore

MAX_RECORDS_PER_RUN = 20


def _kind(record: dict[str, Any]) -> str:
    holdings = record.get("holdings") or []
    if any("journal" in str(item.get("item_type") or "").casefold() for item in holdings):
        return "journal"
    if record.get("isbn"):
        return "book"
    return "paper_or_other"


def hunt_record(store: AcademicStore, root: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Resolve one live catalog item through exact edition or article evidence."""
    record_key = f"opac_live:{record['biblionumber']}"
    title = str(record["title"])
    kind = _kind(record)
    found: list[dict[str, str]] = []
    errors: list[str] = []
    jobs: list[str] = []
    if kind == "book":
        try:
            book = open_library_edition(str(record["isbn"]), title)
            if book:
                evidence = record_source_evidence(store, record_key, record, book)
                status = evidence["content_status"]
                found.append(
                    {"provider": "open_library", "status": status, "url": book["source_url"]}
                )
        except (OSError, ValueError, KeyError, requests.RequestException) as exc:
            errors.append(f"open_library:{type(exc).__name__}")
        try:
            textbook = open_textbook_edition(str(record["isbn"]), title)
            if textbook:
                evidence = record_source_evidence(store, record_key, record, textbook)
                found.append(
                    {
                        "provider": textbook["provider"],
                        "status": evidence["content_status"],
                        "url": textbook["source_url"],
                    }
                )
                if evidence["eligible_extraction"]:
                    job_id = queue_verified_source(store, root, record_key, textbook)
                    if job_id:
                        jobs.append(job_id)
        except (OSError, ValueError, KeyError, requests.RequestException) as exc:
            errors.append(f"open_textbook:{type(exc).__name__}")
        try:
            for hit in find_open_book(
                store, record_key, title, str(record["isbn"]), str(record.get("author") or "")
            ):
                found.append(
                    {
                        "provider": hit["provider"],
                        "status": hit["content_status"],
                        "url": hit["source_url"],
                    }
                )
                if (
                    hit["eligible_extraction"]
                    and os.getenv("ARCHIPELAGO_ACADEMIC_AUTO_DOWNLOAD") == "1"
                ):
                    jobs.append(queue_open_book(store, root, hit))
        except (OSError, ValueError, KeyError, requests.RequestException) as exc:
            errors.append(f"open_books:{type(exc).__name__}")
    elif kind != "journal":
        try:
            article = crossref_article(title)
            if article:
                record_source_evidence(store, record_key, record, article)
                found.append(
                    {
                        "provider": "crossref",
                        "status": "metadata_only",
                        "url": article["source_url"],
                    }
                )
                try:
                    full_text = europe_pmc_open_article(article["doi"], title)
                    if full_text:
                        record_source_evidence(store, record_key, record, full_text)
                        job_id = queue_verified_source(store, root, record_key, full_text)
                        if job_id:
                            found.append(
                                {
                                    "provider": "europe_pmc",
                                    "status": "open_text_queued",
                                    "url": full_text["source_url"],
                                }
                            )
                            jobs.append(job_id)
                except (OSError, ValueError, KeyError, requests.RequestException) as exc:
                    errors.append(f"europe_pmc:{type(exc).__name__}")
        except (OSError, ValueError, KeyError, requests.RequestException) as exc:
            errors.append(f"crossref:{type(exc).__name__}")
    if not found:
        store.audit("source_hunt", "no_verified_external_match", record_key, {"kind": kind})
    return {
        "record_key": record_key,
        "title": title,
        "kind": kind,
        "matches": found,
        "job_ids": jobs,
        "errors": errors,
    }


def discover_opac_query(
    store: AcademicStore,
    root: Path,
    query: str,
    *,
    offset: int = 0,
    max_records: int = MAX_RECORDS_PER_RUN,
) -> dict[str, Any]:
    """Search one live OPAC page, fetch details, then hunt external sources."""
    from opac_live import lookup_book, search_books_page

    if max_records < 1 or max_records > MAX_RECORDS_PER_RUN:
        raise ValueError("max_records outside bounded page limit")
    page = search_books_page(query, offset=offset)
    details: list[dict[str, Any]] = []
    lookup_errors: list[dict[str, str]] = []
    for summary in page["results"][:max_records]:
        identifier = str(summary["biblionumber"])
        try:
            details.append(lookup_book(identifier))
        except (OSError, ValueError, requests.RequestException) as exc:
            lookup_errors.append({"biblionumber": identifier, "error": type(exc).__name__})
    if details:
        reconciliation = reconcile(store, "opac_live", details)
        outcomes = []
        from .open_books import ensure_schema

        ensure_schema(store)
        for record in details:
            key = f"opac_live:{record['biblionumber']}"
            with store._connect() as db:
                state = db.execute(
                    "SELECT status FROM records WHERE record_key=?", (key,)
                ).fetchone()
                prior = db.execute(
                    "SELECT 1 FROM source_evidence WHERE record_key=? LIMIT 1", (key,)
                ).fetchone()
            if state and state["status"] == "unchanged" and prior:
                outcomes.append({"record_key": key, "status": "unchanged_evidence_retained"})
            else:
                outcomes.append(hunt_record(store, root, record))
    else:
        store.provider_result("opac_live", error="no_detail_records")
        reconciliation = {"provider": "opac_live", "status": "unavailable", "counts": {}}
        outcomes = []
    return {
        "query": query,
        "offset": offset,
        "next_offset": page.get("next_offset"),
        "fetched_at": page.get("fetched_at"),
        "reconciliation": reconciliation,
        "records": outcomes,
        "lookup_errors": lookup_errors,
    }

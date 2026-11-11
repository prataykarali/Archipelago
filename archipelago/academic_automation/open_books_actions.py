"""Resumable open-book harvesting, matching, and verified PDF queuing."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import md5, sha256
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urlparse

from defusedxml import ElementTree as ET
import requests  # type: ignore[import-untyped]

from .candidate import ALLOWED_LICENSES
from .external_sources import title_matches
from .open_books import (
    MAX_PDF_BYTES,
    OAI_NS,
    OAI_PAUSE_SECONDS,
    PROVIDERS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    _now,
    _oai_get,
    _store_row,
    ensure_schema,
    normalize_isbn,
    opac_url,
    parse_record,
)
from .store import AcademicStore


def harvest(
    store: AcademicStore,
    provider: str,
    *,
    max_pages: int,
    fetch: Callable[[str, dict[str, str]], bytes] = _oai_get,
    pause: float = OAI_PAUSE_SECONDS,
) -> dict[str, Any]:
    """Advance a resumable harvest by at most ``max_pages``; failures keep the saved token."""
    if provider not in PROVIDERS or not 1 <= max_pages <= 2000:
        raise ValueError("Unknown provider or page budget outside 1-2000")
    ensure_schema(store)
    with store._connect() as db:
        cursor = db.execute(
            "SELECT token,from_date,started_at,pages,complete FROM open_book_cursor WHERE provider=?",
            (provider,),
        ).fetchone()
    token, from_date, started, pages_done, complete = cursor if cursor else ("", "", "", 0, 0)
    if complete or not cursor:  # a finished harvest continues incrementally from its start date
        from_date = started[:10] if complete else ""
        token, pages_done, started = "", 0, _now()
    indexed = deleted = pages = 0
    status = "ok"
    try:
        while pages < max_pages:
            params = (
                {"verb": "ListRecords", "resumptionToken": token}
                if token
                else {
                    "verb": "ListRecords",
                    "metadataPrefix": "xoai",
                    **({"set": PROVIDERS[provider]["set"]} if PROVIDERS[provider]["set"] else {}),
                    **({"from": from_date} if from_date else {}),
                }
            )
            root = ET.fromstring(fetch(provider, params))
            error = root.find(f"{OAI_NS}error")
            if error is not None and error.get("code") == "noRecordsMatch":
                token, complete = "", 1
                break
            if error is not None:
                raise ValueError(f"OAI error {error.get('code')}")
            with store._connect() as db:
                for record in root.iter(f"{OAI_NS}record"):
                    oai_id, row = parse_record(provider, record)
                    if row is None:
                        db.execute(
                            "DELETE FROM open_book_index WHERE provider=? AND oai_id=?",
                            (provider, oai_id),
                        )
                        db.execute(
                            "DELETE FROM open_book_isbn WHERE provider=? AND oai_id=?",
                            (provider, oai_id),
                        )
                        deleted += 1
                    else:
                        _store_row(db, provider, oai_id, row)
                        indexed += 1
            pages += 1
            pages_done += 1
            node = root.find(f"{OAI_NS}ListRecords/{OAI_NS}resumptionToken")
            token = (node.text or "").strip() if node is not None else ""
            complete = 0 if token else 1
            with store._connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO open_book_cursor VALUES(?,?,?,?,?,?,?)",
                    (provider, token, from_date, started, pages_done, complete, _now()),
                )
            if complete:
                break
            time.sleep(pause)
    except (OSError, ValueError, requests.RequestException, ET.ParseError) as exc:
        status = f"error:{type(exc).__name__}"  # saved token lets the next run resume
    with store._connect() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM open_book_index WHERE provider=?", (provider,)
        ).fetchone()[0]
        complete_now = db.execute(
            "SELECT complete FROM open_book_cursor WHERE provider=?", (provider,)
        ).fetchone()
    result = {
        "provider": provider,
        "status": status,
        "pages": pages,
        "records_indexed": indexed,
        "records_deleted": deleted,
        "books_in_index": total,
        "complete": bool(complete_now and complete_now[0]),
    }
    store.audit("open_books", "harvest", provider, result)
    return result


def content_policy(row: dict[str, Any]) -> tuple[str, bool, str]:
    """Return (content_status, eligible_for_extraction, reason) from index facts only."""
    if not row["pdf_url"]:
        if row["host_url"]:
            return (
                "publisher_hosted_unverified",
                False,
                "Full text is hosted elsewhere; no approved retrieval method or per-file license",
            )
        return "metadata_only", False, "No hosted full text in this provider record"
    if row["license_id"] not in ALLOWED_LICENSES:
        return (
            "restricted_license",
            False,
            f"License '{row['rights_text'] or 'unstated'}' does not permit derivative extraction",
        )
    if not row["pdf_bytes"] or row["pdf_bytes"] > MAX_PDF_BYTES:
        return "too_large", False, "Hosted PDF size is unknown or above the processing limit"
    if not row["pdf_md5"]:
        return "unverifiable", False, "Provider supplied no checksum to verify the download"
    return "open_full_text", True, f"Per-file {row['license_id']} declaration on provider PDF"


def _surname_overlap(wanted: str, found: str) -> bool:
    def names(value: str) -> set[str]:
        return set(re.findall(r"[a-z]{3,}", value.casefold()))

    return bool(names(wanted) & names(found)) if wanted and found else True


def find_open_book(
    store: AcademicStore,
    record_key: str,
    title: str,
    isbn: str,
    author: str = "",
    edition: str = "",
) -> list[dict[str, Any]]:
    """Resolve an OPAC record to indexed open books; ISBN and title must both agree."""
    ensure_schema(store)
    isbn = normalize_isbn(isbn)
    if not isbn:
        return []  # title-only joins are not strong enough to expose provider content
    cols = "provider,oai_id,handle_url,title,authors,doi,license_id,license_uri,rights_text,pdf_url,pdf_bytes,pdf_md5,chapter_titles,publisher,host_url"
    with store._connect() as db:
        rows = db.execute(
            f"SELECT {cols} FROM open_book_index i WHERE EXISTS "
            "(SELECT 1 FROM open_book_isbn n WHERE n.isbn=? AND n.provider=i.provider AND n.oai_id=i.oai_id)",
            (isbn,),
        ).fetchall()
    matches = []
    for values in rows:
        row = dict(zip(cols.split(","), values, strict=True))
        if not title_matches(title, row["title"]) and set(
            re.findall(r"[a-z0-9]+", title.casefold())
        ) != set(re.findall(r"[a-z0-9]+", row["title"].casefold())):
            store.audit(
                "open_books",
                "isbn_title_conflict",
                record_key,
                {"provider": row["provider"], "isbn": isbn},
            )
            continue
        status, eligible, reason = content_policy(row)
        chapters = json.loads(row["chapter_titles"])
        verification = "isbn_exact_title_verified" + (
            "" if _surname_overlap(author, row["authors"]) else "_author_unconfirmed"
        )
        evidence = {
            "record_key": record_key,
            "provider": row["provider"],
            "source_id": row["oai_id"],
            "opac_source_url": opac_url(record_key),
            "source_url": row["handle_url"],
            "matched_title": row["title"],
            "matched_authors": row["authors"],
            "isbn": isbn,
            "edition": edition,
            "match_verification": verification,
            "license_id": row["license_id"],
            "license_uri": row["license_uri"],
            "content_status": status,
            "has_toc": int(bool(chapters)),
            "has_preview": 0,
            "chapter_count": len(chapters),
            "has_full_text": int(bool(row["pdf_url"])),
            "eligible_extraction": int(eligible and "author_unconfirmed" not in verification),
            "reason": reason,
            "retrieved_at": _now(),
        }
        with store._connect() as db:
            db.execute(
                f"INSERT OR REPLACE INTO source_evidence({','.join(evidence)}) VALUES({','.join('?' * len(evidence))})",
                list(evidence.values()),
            )
        store.save_match(record_key, row["provider"], row["oai_id"], row["handle_url"], status)
        matches.append(
            {
                **evidence,
                "pdf_url": row["pdf_url"],
                "pdf_md5": row["pdf_md5"],
                "pdf_bytes": row["pdf_bytes"],
            }
        )
    return matches


def queue_open_book(
    store: AcademicStore,
    root: Path,
    match: dict[str, Any],
    *,
    download: Callable[[str], bytes] | None = None,
) -> str:
    """Download one verified, permissively licensed PDF and queue it; an explicit action."""
    if not match.get("eligible_extraction") or match["license_id"] not in ALLOWED_LICENSES:
        raise ValueError("Source is not eligible for extraction")
    parsed = urlparse(match["pdf_url"])
    host = PROVIDERS["oapen"]["host"]
    if (
        match["provider"] != "oapen"
        or parsed.scheme != "https"
        or parsed.hostname != host
        or not parsed.path.startswith("/bitstream/")
    ):
        raise ValueError("Only OAPEN-hosted bitstreams have an approved retrieval method")
    data = download(match["pdf_url"]) if download else _download_pdf(match["pdf_url"])
    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF"):
        raise ValueError("Downloaded file is not an acceptable PDF")
    if md5(data).hexdigest() != match["pdf_md5"]:
        raise ValueError("Downloaded PDF failed provider checksum verification")
    digest = sha256(data).hexdigest()
    folder = root / "data" / "academic_candidates"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest}.pdf"
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)
    path.with_suffix(".source.json").write_text(
        json.dumps(
            {
                "record_key": match["record_key"],
                "provider": "oapen",
                "source_id": match["source_id"],
                "source_url": match["source_url"],
                "source_kind": "open_book_pdf",
                "license": match["license_id"],
                "license_url": match["license_uri"],
                "retrieved_at": _now(),
                "content_sha256": digest,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    job_id = store.enqueue(
        record_key=match["record_key"],
        rights="open_permitted",
        content_path=str(path),
        content_sha256=digest,
    )
    store.audit(
        "open_books",
        "open_book_queued",
        job_id,
        {"source": match["source_url"], "license": match["license_id"]},
    )
    return job_id


def _download_pdf(url: str) -> bytes:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS * 3,
        allow_redirects=False,
        stream=True,
    )
    response.raise_for_status()
    chunks, size = [], 0
    for chunk in response.iter_content(65536):
        size += len(chunk)
        if size > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds size limit")
        chunks.append(chunk)
    return b"".join(chunks)

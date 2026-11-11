"""DOAB and OAPEN open-book resolution through their supported OAI-PMH feeds.

Metadata is harvested into a local index inside the existing academic ledger. Full text is
eligible only when the hosted PDF carries its own permissive Creative Commons declaration.
A table of contents or chapter list is recorded as coverage metadata, never as evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from typing import Any

import requests  # type: ignore[import-untyped]

from .store import AcademicStore

OAI_NS = "{http://www.openarchives.org/OAI/2.0/}"
PROVIDERS = {
    "oapen": {
        "endpoint": "https://library.oapen.org/oai/request",
        "set": "",  # server-side set filtering times out; books are filtered by dc.type
        "host": "library.oapen.org",
    },
    "doab": {
        "endpoint": "https://directory.doabooks.org/oai/request",
        "set": "",
        "host": "directory.doabooks.org",
    },
}
USER_AGENT = "ArchipelagoAcademic/1.0"  # longer agent strings are reset by the OAPEN edge
REQUEST_TIMEOUT_SECONDS = 60
MAX_OAI_BYTES = 8_000_000
OAI_PAUSE_SECONDS = 1.0
MAX_PDF_BYTES = 100 * 1024 * 1024
ISBN_PATTERN = re.compile(r"\b(?:97[89][\d-]{10,14}|\d{9}[\dXx])\b")
LICENSE_URI = re.compile(
    r"creativecommons\.org/(?:licenses/(by(?:-nc)?(?:-nd|-sa)?)/(\d\.\d)|publicdomain/zero/1\.0)",
    re.I,
)
# Permissive attribution-only terms; NC/ND variants block derivative or non-commercial reuse.
_LICENSE_IDS = {
    ("by", "4.0"): "CC-BY-4.0",
    ("by-sa", "4.0"): "CC-BY-SA-4.0",
    ("by", "3.0"): "CC-BY-3.0",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS open_book_index (
    provider TEXT NOT NULL, oai_id TEXT NOT NULL, handle_url TEXT NOT NULL, title TEXT NOT NULL,
    authors TEXT NOT NULL, doi TEXT NOT NULL, license_id TEXT NOT NULL, license_uri TEXT NOT NULL,
    rights_text TEXT NOT NULL, pdf_url TEXT NOT NULL, pdf_bytes INTEGER NOT NULL,
    pdf_md5 TEXT NOT NULL, chapter_titles TEXT NOT NULL, subjects TEXT NOT NULL,
    publisher TEXT NOT NULL, issued TEXT NOT NULL, host_url TEXT NOT NULL, datestamp TEXT NOT NULL,
    PRIMARY KEY(provider, oai_id)
);
CREATE TABLE IF NOT EXISTS open_book_isbn (
    isbn TEXT NOT NULL, provider TEXT NOT NULL, oai_id TEXT NOT NULL,
    PRIMARY KEY(isbn, provider, oai_id)
);
CREATE TABLE IF NOT EXISTS open_book_cursor (
    provider TEXT PRIMARY KEY, token TEXT NOT NULL, from_date TEXT NOT NULL,
    started_at TEXT NOT NULL, pages INTEGER NOT NULL, complete INTEGER NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_evidence (
    record_key TEXT NOT NULL, provider TEXT NOT NULL, source_id TEXT NOT NULL,
    opac_source_url TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL, matched_title TEXT NOT NULL, matched_authors TEXT NOT NULL,
    isbn TEXT NOT NULL, edition TEXT NOT NULL, match_verification TEXT NOT NULL,
    license_id TEXT NOT NULL, license_uri TEXT NOT NULL, content_status TEXT NOT NULL,
    has_toc INTEGER NOT NULL, has_preview INTEGER NOT NULL, chapter_count INTEGER NOT NULL,
    has_full_text INTEGER NOT NULL, eligible_extraction INTEGER NOT NULL, reason TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY(record_key, provider, source_id)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def opac_url(record_key: str) -> str:
    """Return the institution's detail URL for a live bibliographic record."""
    if not record_key.startswith("opac_live:") or not record_key.partition(":")[2].isdigit():
        return ""
    return (
        "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber="
        + record_key.partition(":")[2]
    )


def ensure_schema(store: AcademicStore) -> None:
    """Add the open-book index to the existing ledger instead of a second database."""
    with store._connect() as db:
        db.executescript(SCHEMA)
        columns = {row[1] for row in db.execute("PRAGMA table_info(source_evidence)")}
        if "opac_source_url" not in columns:
            db.execute(
                "ALTER TABLE source_evidence ADD COLUMN opac_source_url TEXT NOT NULL DEFAULT ''"
            )


def normalize_isbn(value: str) -> str:
    """Return a digits-only ISBN-10/13 candidate, or an empty string."""
    cleaned = re.sub(r"[^0-9Xx]", "", value).upper()
    return cleaned if len(cleaned) in {10, 13} else ""


def license_from_uri(uri: str) -> str:
    """Map a CC URI to an identifier; unknown or restricted terms return an empty string."""
    match = LICENSE_URI.search(uri or "")
    if not match:
        return ""
    if match.group(1) is None:
        return "CC0-1.0"
    return _LICENSE_IDS.get((match.group(1).lower(), match.group(2)), "")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _values(element: Any, prefix: str, out: dict[str, list[str]]) -> None:
    for child in element:
        name = child.get("name") or ""
        if _local(child.tag) == "field" and name == "value":
            text = " ".join((child.text or "").split())
            if text:
                out.setdefault(prefix, []).append(text)
        elif _local(child.tag) == "element":
            _values(child, prefix if name in {"none", "*"} else f"{prefix}.{name}".lstrip("."), out)


def _bitstreams(metadata: Any) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for bundle in metadata.iter():
        if _local(bundle.tag) != "element" or bundle.get("name") != "bundle":
            continue
        bundle_name = next(
            (
                (f.text or "")
                for f in bundle
                if _local(f.tag) == "field" and f.get("name") == "name"
            ),
            "",
        )
        for stream in bundle.iter():
            if _local(stream.tag) == "element" and stream.get("name") == "bitstream":
                row = {
                    f.get("name") or "": " ".join((f.text or "").split())
                    for f in stream
                    if _local(f.tag) == "field"
                }
                row["bundle"] = bundle_name
                found.append(row)
    return found


def parse_record(provider: str, record: Any) -> tuple[str, dict[str, Any] | None]:
    """Return (oai_id, row); row is None for deleted records or non-book items."""
    header = record.find(f"{OAI_NS}header")
    if header is None:
        raise ValueError("OAI record without header")
    oai_id = str(header.findtext(f"{OAI_NS}identifier") or "")
    if header.get("status") == "deleted":
        return oai_id, None
    metadata = next((e for e in record.iter() if _local(e.tag) == "metadata"), None)
    if metadata is None:
        return oai_id, None
    fields: dict[str, list[str]] = {}
    for section in metadata.iter():
        if _local(section.tag) == "element" and section.get("name") in {
            "dc",
            "oapen",
            "linkedItemsMetadata",
        }:
            _values(section, section.get("name") or "", fields)
    if "book" not in {v.casefold() for v in fields.get("dc.type", [])}:
        return oai_id, None
    streams = _bitstreams(metadata)
    pdf = next(
        (
            b
            for b in streams
            if b.get("bundle") == "ORIGINAL" and b.get("format") == "application/pdf"
        ),
        {},
    )
    rights_stream = pdf or next(
        (
            b
            for b in streams
            if b.get("rightsuri")
            or b.get("oapenidentifierdownloadUrl")
            or b.get("dcidentifierurlwebshop")
        ),
        {},
    )
    pdf_uri = rights_stream.get("rightsuri", "")
    item_uri = next(
        (
            v
            for v in fields.get("dc.rights.uri", []) + fields.get("dc.rights", [])
            if "creativecommons" in v
        ),
        "",
    )
    license_id = license_from_uri(pdf_uri or item_uri)
    if pdf_uri and item_uri and license_from_uri(pdf_uri) != license_from_uri(item_uri):
        license_id = ""  # conflicting declarations are treated as unverified
    handle = next(iter(fields.get("dc.identifier.uri", []) + fields.get("dc.identifier", [])), "")
    isbns = sorted(
        {
            normalize_isbn(value)
            for value in fields.get("oapen.relation.isbn", [])
            + fields.get("dc.identifier.isbn", [])
            if normalize_isbn(value)
        }
    )
    web_links = [
        v
        for v in (
            [
                rights_stream.get("oapenidentifierdownloadUrl", ""),
                rights_stream.get("dcidentifierurlwebshop", ""),
                *fields.get("dc.identifier", []),
            ]
        )
        if v.startswith(("https://", "http://")) and "handle" not in v
    ]
    publisher = (
        fields.get("oapen.imprint")
        or fields.get("linkedItemsMetadata.oapen.relation.isPublishedBy.publisher.name")
        or fields.get("dc.publisher")
        or [""]
    )[0]
    return oai_id, {
        "handle_url": handle,
        "title": (fields.get("dc.title") or [""])[0],
        "authors": "; ".join(
            fields.get("dc.contributor.author", []) + fields.get("dc.contributor.editor", [])
        ),
        "doi": (fields.get("oapen.identifier.doi") or [""])[0],
        "license_id": license_id,
        "license_uri": pdf_uri or item_uri,
        "rights_text": rights_stream.get("rights") or (fields.get("dc.rights") or [""])[0],
        "pdf_url": pdf.get("url", ""),
        "pdf_bytes": int(pdf["size"]) if pdf.get("size", "").isdigit() else 0,
        "pdf_md5": pdf.get("checksum", "") if pdf.get("checksumAlgorithm") == "MD5" else "",
        "chapter_titles": json.dumps(fields.get("oapen.relation.hasChapter", [])[:200]),
        "subjects": "; ".join(
            fields.get("dc.subject.classification", []) + fields.get("dc.subject", [])
        )[:600],
        "publisher": publisher,
        "issued": (fields.get("dc.date.issued") or [""])[0],
        "host_url": web_links[0] if web_links else "",
        "datestamp": str(header.findtext(f"{OAI_NS}datestamp") or ""),
        "isbns": isbns,
    }


def _oai_get(provider: str, params: dict[str, str]) -> bytes:
    response = requests.get(
        PROVIDERS[provider]["endpoint"],
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    response.raise_for_status()
    if response.is_redirect or len(response.content) > MAX_OAI_BYTES:
        raise ValueError("OAI response redirected or too large")
    return bytes(response.content)


def _store_row(db: Any, provider: str, oai_id: str, row: dict[str, Any]) -> None:
    columns = [k for k in row if k != "isbns"]
    db.execute(
        f"INSERT OR REPLACE INTO open_book_index(provider,oai_id,{','.join(columns)}) "
        f"VALUES(?,?,{','.join('?' * len(columns))})",
        [provider, oai_id, *[row[c] for c in columns]],
    )
    db.execute("DELETE FROM open_book_isbn WHERE provider=? AND oai_id=?", (provider, oai_id))
    db.executemany(
        "INSERT OR IGNORE INTO open_book_isbn(isbn,provider,oai_id) VALUES(?,?,?)",
        [(isbn, provider, oai_id) for isbn in row["isbns"]],
    )


from .open_books_actions import (  # noqa: E402,F401
    content_policy,
    find_open_book,
    harvest,
    queue_open_book,
)

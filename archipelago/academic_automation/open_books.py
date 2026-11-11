"""DOAB and OAPEN open-book resolution through their supported OAI-PMH feeds.

Metadata is harvested into a local index inside the existing academic ledger. Full text is
eligible only when the hosted PDF carries its own permissive Creative Commons declaration.
A table of contents or chapter list is recorded as coverage metadata, never as evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import md5, sha256
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable
from urllib.parse import urlparse

from defusedxml import ElementTree as ET
import requests  # type: ignore[import-untyped]

from .candidate import ALLOWED_LICENSES
from .external_sources import title_matches
from .store import AcademicStore

OAI_NS = "{http://www.openarchives.org/OAI/2.0/}"
PROVIDERS = {
    "oapen": {
        "endpoint": "https://library.oapen.org/oai/request",
        "set": "com_20.500.12657_5",
        "host": "library.oapen.org",
    },
    "doab": {
        "endpoint": "https://directory.doabooks.org/oai/request",
        "set": "com_20.500.12854_5",
        "host": "directory.doabooks.org",
    },
}
USER_AGENT = "ArchipelagoAcademic/1.0 (OAI-PMH metadata harvest; contact: library operator)"
REQUEST_TIMEOUT_SECONDS = 60
MAX_OAI_BYTES = 8_000_000
OAI_PAUSE_SECONDS = 1.0
MAX_PDF_BYTES = 100 * 1024 * 1024
ISBN_PATTERN = re.compile(r"\b(?:97[89][\d-]{10,14}|\d{9}[\dXx])\b")
LICENSE_URI = re.compile(
    r"creativecommons\.org/(?:licenses/(by(?:-nc)?(?:-nd|-sa)?)/(\d\.\d)|publicdomain/zero/1\.0)", re.I
)
# Permissive attribution-only terms; NC/ND variants block derivative or non-commercial reuse.
_LICENSE_IDS = {("by", "4.0"): "CC-BY-4.0", ("by-sa", "4.0"): "CC-BY-SA-4.0", ("by", "3.0"): "CC-BY-3.0"}
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


def ensure_schema(store: AcademicStore) -> None:
    """Add the open-book index to the existing ledger instead of a second database."""
    with store._connect() as db:
        db.executescript(SCHEMA)


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
            _values(child, prefix if name == "none" else f"{prefix}.{name}".lstrip("."), out)


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
                row = {f.get("name") or "": " ".join((f.text or "").split()) for f in stream if _local(f.tag) == "field"}
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
        if _local(section.tag) == "element" and section.get("name") in {"dc", "oapen"}:
            _values(section, section.get("name") or "", fields)
    if "book" not in {v.casefold() for v in fields.get("dc.type", [])}:
        return oai_id, None
    pdf = next(
        (b for b in _bitstreams(metadata) if b.get("bundle") == "ORIGINAL" and b.get("format") == "application/pdf"),
        {},
    )
    pdf_uri = pdf.get("rightsuri", "")
    item_uri = next((v for v in fields.get("dc.rights.uri", []) if "creativecommons" in v), "")
    license_id = license_from_uri(pdf_uri or item_uri)
    if pdf_uri and item_uri and license_from_uri(pdf_uri) != license_from_uri(item_uri):
        license_id = ""  # conflicting declarations are treated as unverified
    handle = next(iter(fields.get("dc.identifier.uri", []) + fields.get("dc.identifier", [])), "")
    isbns = sorted(
        {
            normalize_isbn(value)
            for value in fields.get("oapen.relation.isbn", []) + fields.get("dc.identifier.isbn", [])
            if normalize_isbn(value)
        }
    )
    web_links = [
        v for v in fields.get("dc.identifier", []) if v.startswith("https://") and "handle" not in v
    ]
    return oai_id, {
        "handle_url": handle,
        "title": (fields.get("dc.title") or [""])[0],
        "authors": "; ".join(fields.get("dc.contributor.author", []) + fields.get("dc.contributor.editor", [])),
        "doi": (fields.get("oapen.identifier.doi") or [""])[0],
        "license_id": license_id,
        "license_uri": pdf_uri or item_uri,
        "rights_text": pdf.get("rights") or (fields.get("dc.rights") or [""])[0],
        "pdf_url": pdf.get("url", ""),
        "pdf_bytes": int(pdf["size"]) if pdf.get("size", "").isdigit() else 0,
        "pdf_md5": pdf.get("checksum", "") if pdf.get("checksumAlgorithm") == "MD5" else "",
        "chapter_titles": json.dumps(fields.get("oapen.relation.hasChapter", [])[:200]),
        "subjects": "; ".join(fields.get("dc.subject.classification", []))[:600],
        "publisher": (fields.get("oapen.imprint") or [""])[0],
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
        cursor = db.execute("SELECT token,from_date,started_at,pages,complete FROM open_book_cursor WHERE provider=?", (provider,)).fetchone()
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
                    "set": PROVIDERS[provider]["set"],
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
                        db.execute("DELETE FROM open_book_index WHERE provider=? AND oai_id=?", (provider, oai_id))
                        db.execute("DELETE FROM open_book_isbn WHERE provider=? AND oai_id=?", (provider, oai_id))
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
        total = db.execute("SELECT COUNT(*) FROM open_book_index WHERE provider=?", (provider,)).fetchone()[0]
        complete_now = db.execute("SELECT complete FROM open_book_cursor WHERE provider=?", (provider,)).fetchone()
    result = {
        "provider": provider, "status": status, "pages": pages, "records_indexed": indexed,
        "records_deleted": deleted, "books_in_index": total, "complete": bool(complete_now and complete_now[0]),
    }
    store.audit("open_books", "harvest", provider, result)
    return result


def content_policy(row: dict[str, Any]) -> tuple[str, bool, str]:
    """Return (content_status, eligible_for_extraction, reason) from index facts only."""
    if not row["pdf_url"]:
        if row["host_url"]:
            return "publisher_hosted_unverified", False, "Full text is hosted elsewhere; no approved retrieval method or per-file license"
        return "metadata_only", False, "No hosted full text in this provider record"
    if row["license_id"] not in ALLOWED_LICENSES:
        return "restricted_license", False, f"License '{row['rights_text'] or 'unstated'}' does not permit derivative extraction"
    if not row["pdf_bytes"] or row["pdf_bytes"] > MAX_PDF_BYTES:
        return "too_large", False, "Hosted PDF size is unknown or above the processing limit"
    if not row["pdf_md5"]:
        return "unverifiable", False, "Provider supplied no checksum to verify the download"
    return "open_full_text", True, f"Per-file {row['license_id']} declaration on provider PDF"


def _surname_overlap(wanted: str, found: str) -> bool:
    def names(value: str) -> set[str]:
        return {t for t in re.findall(r"[a-z]{3,}", value.casefold())}

    return bool(names(wanted) & names(found)) if wanted and found else True


def find_open_book(
    store: AcademicStore, record_key: str, title: str, isbn: str, author: str = "", edition: str = ""
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
        if not title_matches(title, row["title"]) and set(re.findall(r"[a-z0-9]+", title.casefold())) != set(
            re.findall(r"[a-z0-9]+", row["title"].casefold())
        ):
            store.audit("open_books", "isbn_title_conflict", record_key, {"provider": row["provider"], "isbn": isbn})
            continue
        status, eligible, reason = content_policy(row)
        chapters = json.loads(row["chapter_titles"])
        verification = "isbn_exact_title_verified" + ("" if _surname_overlap(author, row["authors"]) else "_author_unconfirmed")
        evidence = {
            "record_key": record_key, "provider": row["provider"], "source_id": row["oai_id"],
            "source_url": row["handle_url"], "matched_title": row["title"], "matched_authors": row["authors"],
            "isbn": isbn, "edition": edition, "match_verification": verification,
            "license_id": row["license_id"], "license_uri": row["license_uri"], "content_status": status,
            "has_toc": int(bool(chapters)), "has_preview": 0, "chapter_count": len(chapters),
            "has_full_text": int(bool(row["pdf_url"])), "eligible_extraction": int(eligible and "author_unconfirmed" not in verification),
            "reason": reason, "retrieved_at": _now(),
        }
        with store._connect() as db:
            db.execute(
                f"INSERT OR REPLACE INTO source_evidence({','.join(evidence)}) VALUES({','.join('?' * len(evidence))})",
                list(evidence.values()),
            )
        store.save_match(record_key, row["provider"], row["oai_id"], row["handle_url"], status)
        matches.append({**evidence, "pdf_url": row["pdf_url"], "pdf_md5": row["pdf_md5"], "pdf_bytes": row["pdf_bytes"]})
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
    if match["provider"] != "oapen" or parsed.scheme != "https" or parsed.hostname != host or not parsed.path.startswith("/bitstream/"):
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
                "record_key": match["record_key"], "provider": "oapen", "source_id": match["source_id"],
                "source_url": match["source_url"], "source_kind": "open_book_pdf",
                "license": match["license_id"], "license_url": match["license_uri"],
                "retrieved_at": _now(), "content_sha256": digest,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    job_id = store.enqueue(
        record_key=match["record_key"], rights="open_permitted", content_path=str(path), content_sha256=digest
    )
    store.audit("open_books", "open_book_queued", job_id, {"source": match["source_url"], "license": match["license_id"]})
    return job_id


def _download_pdf(url: str) -> bytes:
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS * 3,
        allow_redirects=False, stream=True,
    )
    response.raise_for_status()
    chunks, size = [], 0
    for chunk in response.iter_content(65536):
        size += len(chunk)
        if size > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds size limit")
        chunks.append(chunk)
    return b"".join(chunks)

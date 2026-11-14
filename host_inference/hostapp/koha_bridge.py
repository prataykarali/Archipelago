"""Read the shared public Koha metadata snapshot for the Library page."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from html.parser import HTMLParser
import os
import re
import time
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import requests

BUCKET = "archipelago-cache"
OBJECT = "koha_catalog_snapshot.json"
REQUEST_TIMEOUT_SECONDS = 12
CACHE_SECONDS = 300

OPAC_ORIGIN = "https://uemk-opac.l2c2.co.in"
OPAC_HOST = "uemk-opac.l2c2.co.in"
OPAC_SEARCH_PATH = "/cgi-bin/koha/opac-search.pl"
OPAC_DETAIL_PATH = "/cgi-bin/koha/opac-detail.pl"
LIVE_OPAC_TIMEOUT_SECONDS = 5
MAX_OPAC_PAGE_BYTES = 2_000_000
MAX_OPAC_REDIRECTS = 3
MAX_CHAT_OPAC_RECORDS = 3
MAX_OPAC_HOLDINGS = 300
OPAC_USER_AGENT = "ArchipelagoAcademic/1.0 (user-triggered catalogue lookup)"
BIB_PATTERN = re.compile(r"^\d{1,9}$")


def load_koha_snapshot() -> dict[str, object] | None:
    """Return a validated shared snapshot without exposing storage credentials."""
    return _load_for_bucket(int(time.time() // CACHE_SECONDS))


@lru_cache(maxsize=2)
def _load_for_bucket(_bucket: int) -> dict[str, object] | None:
    """Bound repeated reads in a warm serverless instance."""
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        return None
    try:
        response = requests.get(
            f"{base}/storage/v1/object/{BUCKET}/{OBJECT}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or data.get("source") != "authorized_koha_ods_export":
        return None
    return data


def _count(value: object) -> int:
    """Coerce a nonnegative copy count from the Koha export."""
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def public_holdings(snapshot: dict[str, object]) -> list[dict[str, object]]:
    """Map dated Koha rows to the existing Library table contract."""
    source = snapshot.get("holdings")
    if not isinstance(source, list):
        return []
    rows = []
    for item in source:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("biblionumber") or "").strip()
        title = str(item.get("Title") or "").strip()
        if not identifier.isdigit() or not title:
            continue
        total = _count(item.get("No. of copies"))
        available = min(_count(item.get("Available Copies")), total)
        rows.append(
            {
                "book_id": identifier,
                "biblionumber": identifier,
                "title": title,
                "authors": str(item.get("Author") or "").strip(),
                "publisher": str(item.get("Publisher") or "").strip(),
                "accession": str(item.get("Accn Nos.") or "").strip(),
                "total_copies": total,
                "available_copies": available,
                "no_of_copies": total,
                "available_ratio": f"{available} / {total}",
                "isbn": str(item.get("isbn") or "").strip(),
                "call_number": str(item.get("call_number") or "").strip(),
                "rack_number": str(item.get("rack_number") or "").strip(),
                "opac_url": f"https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber={identifier}",
            }
        )
    return rows


def _valid_opac_url(url: str) -> bool:
    """Ensure URL stays on HTTPS uemk-opac.l2c2.co.in public Koha OPAC paths."""
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == OPAC_HOST
        and parsed.path.startswith("/cgi-bin/koha/opac-")
    )


def _opac_book_id(url: str) -> str:
    """Extract a validated numeric Koha biblionumber from a detail URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != OPAC_HOST or parsed.path != OPAC_DETAIL_PATH:
        return ""
    value = parse_qs(parsed.query).get("biblionumber", [""])[0]
    return value if BIB_PATTERN.fullmatch(value) else ""


def _opac_fetch(path: str, params: dict[str, str]) -> tuple[str, str]:
    """Fetch one public Koha OPAC page, rejecting off-host redirects and oversized responses."""
    url = f"{OPAC_ORIGIN}{path}"
    for _ in range(MAX_OPAC_REDIRECTS + 1):
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": OPAC_USER_AGENT, "Accept": "text/html"},
            timeout=LIVE_OPAC_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if not response.is_redirect:
            break
        url = urljoin(response.url, response.headers.get("Location", ""))
        if not _valid_opac_url(url):
            raise ValueError("Unexpected OPAC redirect")
        params = {}
    else:
        raise ValueError("Too many OPAC redirects")
    response.raise_for_status()
    if not _valid_opac_url(response.url):
        raise ValueError("Unexpected OPAC URL")
    if len(response.content) > MAX_OPAC_PAGE_BYTES:
        raise ValueError("OPAC page exceeds size limit")
    return response.text, response.url


class _SearchPageParser(HTMLParser):
    """Extract ordered, deduplicated biblionumbers from Koha search results."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_results = False
        self._results_depth = 0
        self.biblionumbers: list[str] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())
        if "searchresults" in classes and not self._in_results:
            self._in_results = True
            self._results_depth = 1
            return
        if self._in_results:
            self._results_depth += 1
            if tag == "a" and "title" in classes:
                href = urljoin(OPAC_ORIGIN, attr_map.get("href") or "")
                bib = _opac_book_id(href)
                if bib and bib not in self._seen:
                    self._seen.add(bib)
                    self.biblionumbers.append(bib)

    def handle_endtag(self, tag: str) -> None:
        if self._in_results:
            self._results_depth -= 1
            if self._results_depth <= 0:
                self._in_results = False


class _DetailPageParser(HTMLParser):
    """Extract bibliographic metadata and #holdingst copy rows from a Koha detail page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.author = ""
        self.isbn = ""
        self.publisher = ""
        self.year = ""
        self.holdings: list[dict[str, str]] = []

        self._stack: list[tuple[str, set[str], str]] = []
        self._capture_target: str | None = None
        self._capture_depth = 0
        self._capture_buf: list[str] = []

        self._in_holdingst = False
        self._in_tbody = False
        self._in_tr = False
        self._current_row: dict[str, str] = {}
        self._current_td: str | None = None
        self._td_buf: list[str] = []

    def _start_capture(self, target: str) -> None:
        self._capture_target = target
        self._capture_depth = 1
        self._capture_buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())
        elem_id = attr_map.get("id") or ""
        prop = attr_map.get("property") or ""
        self._stack.append((tag, classes, elem_id))

        if self._capture_target is not None:
            self._capture_depth += 1

        if tag == "h1" and "title" in classes and not self.title:
            self._start_capture("title")
        elif "resource_list" in classes and any("author" in c for _, c, _ in self._stack) and not self.author:
            self._start_capture("author")
        elif prop == "isbn" and any("isbn" in c for _, c, _ in self._stack) and not self.isbn:
            self._start_capture("isbn")
        elif "publisher_name" in classes and not self.publisher:
            self._start_capture("publisher")
        elif "publisher_date" in classes and not self.year:
            self._start_capture("year")

        if elem_id == "holdingst":
            self._in_holdingst = True
        elif self._in_holdingst and tag == "tbody":
            self._in_tbody = True
        elif self._in_tbody and tag == "tr" and len(self.holdings) < MAX_OPAC_HOLDINGS:
            self._in_tr = True
            self._current_row = {}
        elif self._in_tr and tag == "td":
            for col in ("itype", "location", "call_no", "status", "date_due", "barcode"):
                if col in classes:
                    self._current_td = col
                    self._td_buf = []
                    break

    def handle_data(self, data: str) -> None:
        if self._capture_target is not None and (
            self._capture_target != "title" or self._capture_depth == 1
        ):
            self._capture_buf.append(data)
        if self._current_td is not None:
            self._td_buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            _, _, elem_id = self._stack.pop()
            if elem_id == "holdingst":
                self._in_holdingst = False
                self._in_tbody = False
                self._in_tr = False

        if self._capture_target is not None:
            self._capture_depth -= 1
            if self._capture_depth <= 0:
                text = " ".join("".join(self._capture_buf).split())
                if self._capture_target == "title":
                    self.title = text
                elif self._capture_target == "author":
                    self.author = text
                elif self._capture_target == "isbn":
                    self.isbn = text
                elif self._capture_target == "publisher":
                    self.publisher = text
                elif self._capture_target == "year":
                    self.year = text
                self._capture_target = None
                self._capture_buf = []

        if self._current_td is not None and tag == "td":
            self._current_row[self._current_td] = " ".join("".join(self._td_buf).split())
            self._current_td = None
            self._td_buf = []
        elif self._in_tr and tag == "tr":
            self._in_tr = False
            raw_call = self._current_row.get("call_no") or ""
            call_no = re.split(r"\(\s*Browse shelf", raw_call, maxsplit=1)[0].strip()
            self.holdings.append(
                {
                    "item_type": self._current_row.get("itype", ""),
                    "library": self._current_row.get("location", ""),
                    "call_number": call_no,
                    "status": self._current_row.get("status", ""),
                    "due_date": self._current_row.get("date_due", ""),
                    "barcode": self._current_row.get("barcode", ""),
                }
            )
            self._current_row = {}
        elif self._in_tbody and tag == "tbody":
            self._in_tbody = False


def _parse_opac_detail(html: str, source_url: str) -> dict[str, object]:
    """Parse a Koha detail page into a structured live-OPAC holding record."""
    parser = _DetailPageParser()
    parser.feed(html)
    parser.close()
    bib = _opac_book_id(source_url)
    if not bib or not parser.title:
        raise ValueError("OPAC record missing biblionumber or title")

    holdings = parser.holdings
    libraries = list(dict.fromkeys(h["library"] for h in holdings if h.get("library")))
    call_numbers = list(dict.fromkeys(h["call_number"] for h in holdings if h.get("call_number")))
    if holdings:
        available_copies: int | None = sum(
            1 for h in holdings if (h.get("status") or "").strip().lower() == "available"
        )
        total_copies: int | None = len(holdings)
        statuses = list(dict.fromkeys(h["status"] for h in holdings if h.get("status")))
        availability_status = (
            f"{available_copies} of {total_copies} copies available"
            + (f" ({', '.join(statuses)})" if statuses else "")
        )
    else:
        available_copies = None
        total_copies = None
        availability_status = "Catalogued in OPAC (no physical copy status rows listed on detail page)"

    return {
        "biblionumber": bib,
        "title": parser.title,
        "author": parser.author,
        "isbn": parser.isbn,
        "publisher": parser.publisher,
        "year": parser.year,
        "call_number": call_numbers[0] if call_numbers else "",
        "library_name": ", ".join(libraries),
        "availability_status": availability_status,
        "available_copies": available_copies,
        "total_copies": total_copies,
        "holdings": holdings,
        "opac_url": f"{OPAC_ORIGIN}{OPAC_DETAIL_PATH}?biblionumber={bib}",
    }


def _snapshot_fallback(query: str) -> dict[str, object] | None:
    """Fall back cleanly to the dated Koha snapshot when live OPAC is unavailable."""
    snapshot = load_koha_snapshot()
    if not snapshot:
        return None
    tokens = [tok for tok in re.findall(r"[a-z0-9]+", query.lower()) if len(tok) >= 2]
    scored: list[tuple[int, dict[str, object]]] = []
    for row in public_holdings(snapshot):
        haystack = " ".join(
            str(row.get(k) or "")
            for k in ("title", "authors", "isbn", "call_number", "biblionumber")
        ).lower()
        score = sum(1 for tok in tokens if tok in haystack)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    records = []
    for _, row in scored[:MAX_CHAT_OPAC_RECORDS]:
        avail = row.get("available_copies")
        total = row.get("total_copies")
        records.append(
            {
                "biblionumber": row["biblionumber"],
                "title": row["title"],
                "author": row["authors"],
                "isbn": row["isbn"],
                "publisher": row["publisher"],
                "call_number": row["call_number"],
                "library_name": "",
                "availability_status": f"{avail} of {total} copies available in dated Koha export",
                "available_copies": avail,
                "total_copies": total,
                "opac_url": row["opac_url"],
            }
        )
    primary = records[0] if records else {}
    return {
        "query": query,
        "source_mode": "KOHA_EXPORT_SNAPSHOT",
        "snapshot_updated_at": snapshot.get("source_updated_at"),
        "stale": bool(snapshot.get("stale", True)),
        "checked_at": datetime.now(UTC).isoformat(),
        "records": records,
        "biblionumber": primary.get("biblionumber", ""),
        "title": primary.get("title", ""),
        "author": primary.get("author", ""),
        "call_number": primary.get("call_number", ""),
        "library_name": primary.get("library_name", ""),
        "availability_status": primary.get("availability_status", ""),
        "opac_url": primary.get("opac_url", ""),
    }


def lookup_chat_library_holding(query: str) -> dict[str, object] | None:
    """Query the live UEM Kolkata OPAC for chat, falling back to Koha snapshot on error."""
    cleaned = " ".join((query or "").split())[:100]
    if len(cleaned) < 2:
        return None
    checked_at = datetime.now(UTC).isoformat()
    search_url = f"{OPAC_ORIGIN}{OPAC_SEARCH_PATH}?q={quote_plus(cleaned)}"
    try:
        html, final_url = _opac_fetch(OPAC_SEARCH_PATH, {"q": cleaned, "count": str(MAX_CHAT_OPAC_RECORDS)})
        redirected_id = _opac_book_id(final_url)
        records: list[dict[str, object]] = []
        if redirected_id:
            records.append(_parse_opac_detail(html, final_url))
        else:
            parser = _SearchPageParser()
            parser.feed(html)
            parser.close()
            for bib in parser.biblionumbers[:MAX_CHAT_OPAC_RECORDS]:
                detail_html, detail_url = _opac_fetch(OPAC_DETAIL_PATH, {"biblionumber": bib})
                records.append(_parse_opac_detail(detail_html, detail_url))
        primary = records[0] if records else {}
        return {
            "query": cleaned,
            "source_mode": "LIVE_OPAC",
            "checked_at": checked_at,
            "opac_search_url": search_url,
            "records": records,
            "biblionumber": primary.get("biblionumber", ""),
            "title": primary.get("title", ""),
            "author": primary.get("author", ""),
            "call_number": primary.get("call_number", ""),
            "library_name": primary.get("library_name", ""),
            "availability_status": primary.get("availability_status", ""),
            "opac_url": primary.get("opac_url", search_url),
        }
    except (requests.RequestException, ValueError):
        return _snapshot_fallback(cleaned)

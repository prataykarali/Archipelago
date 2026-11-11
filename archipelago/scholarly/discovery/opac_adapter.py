"""Discover UEMK Koha holdings from an authorized local export snapshot."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)

logger = logging.getLogger("archipelago.scholarly.opac")

BASE_URL = "http://uemk-opac.l2c2.co.in"


class OPACAdapter:
    """Adapter for UEMK Koha Integrated Library System."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (
            base_url or os.environ.get("ARCHIPELAGO_OPAC_BASE_URL") or BASE_URL
        ).rstrip("/")
        self.headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Archipelago-OPAC-Bot/1.0"}

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search the authorized Koha export without crawling the public OPAC."""
        from pathlib import Path

        from archipelago.inference.ods_parser import read_ods_sheet

        export = (
            Path(__file__).resolve().parents[3]
            / "data/koha/Titles List with specified keyword-reportresults.ods"
        )
        if not export.is_file():
            return self._fallback_koha_records(query, limit)
        raw_sha256 = hashlib.sha256(export.read_bytes()).hexdigest()
        rows = read_ods_sheet(str(export))
        if not rows:
            return []
        columns = {name.strip(): index for index, name in enumerate(rows[0])}
        required = {"Title", "Author", "biblionumber"}
        if not required.issubset(columns):
            raise ValueError("Koha export is missing required columns")
        terms = [term.casefold() for term in query.split() if term.strip()]
        results: list[dict[str, Any]] = []

        def field(row: list[str], name: str) -> str:
            index = columns[name]
            return row[index].strip() if index < len(row) else ""

        for row in rows[1:]:
            title = field(row, "Title")
            author = field(row, "Author")
            if not title or not all(term in f"{title} {author}".casefold() for term in terms):
                continue
            bib = field(row, "biblionumber").removesuffix(".0")
            if not bib.isdigit():
                continue
            link = f"https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber={bib}"
            prov = ProvenancePointer(
                source_type="koha_ods_export",
                artifact_sha256=raw_sha256,
                source_record_id=bib,
                source_url=link,
            )
            paper = PaperRecord(
                title=title,
                abstract=f"UEMK Library catalog holding for '{title}'.",
                identifiers=PaperIdentifiers(),
                authors=[PaperAuthor(name=author or "Unknown author")],
                venue="UEMK Library",
                publication_type="book",
                is_open_access=False,
                oa_url=link,
            )
            results.append(
                {
                    "source": "uemk_opac",
                    "paper": paper,
                    "provenance": prov,
                    "raw_sha256": raw_sha256,
                    "citation_count": 0,
                    "biblionumber": bib,
                    "catalog_url": link,
                    "availability": "export_snapshot",
                    "retrieval_mode": "export_snapshot",
                }
            )
            if len(results) >= limit:
                break
        return results

    def _parse_rss_response(
        self, raw_bytes: bytes, raw_sha256: str, query: str, limit: int
    ) -> list[dict[str, Any]]:
        results = []
        try:
            root = ET.fromstring(raw_bytes)
            # Find all item nodes in RSS
            items = root.findall(".//item")
            for item in items[:limit]:
                title = item.findtext("title", "Untitled Book").strip()
                link = item.findtext("link", "").strip()
                desc = item.findtext("description", "").strip()
                author = item.findtext(
                    "{http://purl.org/dc/elements/1.1/}creator", "Unknown Author"
                ).strip()

                # Extract biblionumber from link (e.g. /cgi-bin/koha/opac-detail.pl?biblionumber=1234)
                bib_match = re.search(r"biblionumber=(\d+)", link)
                bib_id = bib_match.group(1) if bib_match else f"opac_{raw_sha256[:8]}"

                prov = ProvenancePointer(
                    source_type="opac",
                    artifact_sha256=raw_sha256,
                    source_record_id=bib_id,
                    source_url=link,
                )

                paper = PaperRecord(
                    title=title,
                    abstract=desc
                    if desc
                    else f"Physical library holdings for '{title}' in UEMK Library.",
                    identifiers=PaperIdentifiers(),
                    authors=[PaperAuthor(name=author)],
                    venue="UEMK Central Library",
                    publication_type="book",
                    is_open_access=False,
                    oa_url=link,
                )

                results.append(
                    {
                        "source": "uemk_opac",
                        "paper": paper,
                        "provenance": prov,
                        "raw_sha256": raw_sha256,
                        "citation_count": 0,
                        "biblionumber": bib_id,
                        "catalog_url": link,
                        "availability": "unknown",
                        "retrieval_mode": "live",
                    }
                )
        except Exception as e:
            logger.warning("Error parsing OPAC RSS XML: %s", e)

        return results

    def _search_html(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Fallback HTML scraper for Koha OPAC search."""
        search_url = f"{self.base_url}/cgi-bin/koha/opac-search.pl?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(search_url, headers=self.headers)
        results = []

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                html_bytes = resp.read()
                raw_sha256 = hashlib.sha256(html_bytes).hexdigest()
                html_text = html_bytes.decode("utf-8", errors="ignore")

                # Parse search results table rows / titles
                title_matches = re.findall(
                    r'<a\s+class="title"\s+href="([^"]*biblionumber=(\d+)[^"]*)">([^<]+)</a>',
                    html_text,
                    re.IGNORECASE,
                )

                for link_rel, bib_id, title_raw in title_matches[:limit]:
                    clean_title = re.sub(r"\s+", " ", title_raw).strip()
                    full_link = (
                        f"{self.base_url}{link_rel}" if link_rel.startswith("/") else link_rel
                    )

                    prov = ProvenancePointer(
                        source_type="opac",
                        artifact_sha256=raw_sha256,
                        source_record_id=bib_id,
                        source_url=full_link,
                    )

                    paper = PaperRecord(
                        title=clean_title,
                        abstract=f"UEMK Library Catalog holding. Accession record #{bib_id}.",
                        identifiers=PaperIdentifiers(),
                        authors=[PaperAuthor(name="UEM Library Cataloged Author")],
                        venue="UEMK Central Library",
                        publication_type="book",
                        oa_url=full_link,
                    )

                    results.append(
                        {
                            "source": "uemk_opac",
                            "paper": paper,
                            "provenance": prov,
                            "raw_sha256": raw_sha256,
                            "citation_count": 0,
                            "biblionumber": bib_id,
                            "catalog_url": full_link,
                            "availability": "unknown",
                            "retrieval_mode": "live",
                        }
                    )
        except Exception as e:
            logger.error("OPAC HTML search failed for '%s': %s", query, e)

        if not results:
            return self._fallback_koha_records(query, limit)

        return results

    def _fallback_koha_records(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Fallback verified holdings from institutional library catalog when live Koha server is unreachable."""
        import json
        from pathlib import Path

        results = []
        bookshelf_path = (
            Path(__file__).resolve().parents[3] / "data/catalogs/pearson_bookshelf.json"
        )

        books = []
        if bookshelf_path.is_file():
            try:
                with open(bookshelf_path, encoding="utf-8") as f:
                    data = json.load(f)
                    books = data.get("books", [])
            except Exception as e:
                logger.warning("Could not read bookshelf fallback: %s", e)

        query_tokens = [t.lower() for t in query.split() if len(t) > 2]
        matched_books = []
        for b in books:
            b_text = f"{b.get('title', '')} {b.get('author', '')} {b.get('domain', '')}".lower()
            if any(t in b_text for t in query_tokens):
                matched_books.append(b)

        raw_sha256 = hashlib.sha256(bookshelf_path.read_bytes()).hexdigest() if books else ""

        for b in matched_books[:limit]:
            book_id = b.get("isbn") or b.get("id") or "pearson_book"
            link = b.get("reader_base_url") or b.get("url")

            prov = ProvenancePointer(
                source_type="pearson_bookshelf",
                artifact_sha256=raw_sha256,
                source_record_id=str(book_id),
                source_url=link,
            )

            paper = PaperRecord(
                title=b.get("title", "UEMK Library Holding"),
                abstract=f"Pearson bookshelf catalog entry. Domain: {b.get('domain', 'Engineering & Science')}. ISBN: {b.get('isbn', 'N/A')}.",
                identifiers=PaperIdentifiers(isbn=b.get("isbn")),
                authors=[PaperAuthor(name=b.get("author", "UEM Faculty/Author"))],
                venue="Pearson bookshelf catalog",
                publication_type="book",
                oa_url=link,
            )

            results.append(
                {
                    "source": "pearson_bookshelf",
                    "paper": paper,
                    "provenance": prov,
                    "raw_sha256": raw_sha256,
                    "citation_count": 0,
                    "catalog_url": link,
                    "availability": "unknown",
                    "retrieval_mode": "catalog_fallback",
                }
            )

        return results

"""Native PDF, HTML, and plain-text/RFC extractors with physical/printed page mapping.

Extracts clean per-page or per-section units while preserving exact provenance:
physical PDF page index (0-based), 1-based page number, printed page label
(from PDF PageLabels or page-edge heuristic), and active section heading.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from bs4 import BeautifulSoup
import fitz

HASH_CHUNK_BYTES = 1024 * 1024
MIN_REPEATED_HEADER_PAGES = 4
HEADER_REPEAT_RATIO = 0.35
MAX_HEADER_FOOTER_LINE_LEN = 120
MAX_EDGE_LINES_TO_SCAN = 2
MAX_SECTION_HEADING_LEN = 120
MIN_SECTION_HEADING_LEN = 3
RFC_MIN_PAGE_LINES = 2
MAX_PRINTED_PAGE_NUMBER = 5000

_PRINTED_PAGE_NUM_RE = re.compile(r"^\s*(?:page\s+)?(\d{1,4})\s*$", re.IGNORECASE)
_ROMAN_PAGE_RE = re.compile(r"^\s*([ivxlcdm]{1,8})\s*$", re.IGNORECASE)
_RFC_PAGE_FOOTER_RE = re.compile(r"\[Page\s+(\d{1,4})\]", re.IGNORECASE)
_SECTION_HEADING_RE = re.compile(
    r"^(?:Chapter\s+\d+[:.\s]+.+|\d+(?:\.\d+){0,3}\s+[A-Z][^\n]{2,100}|"
    r"Appendix\s+[A-Z][:\s]+.+)$"
)
_HTML_NOISE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "noscript", "form")


@dataclass(frozen=True)
class ExtractedUnit:
    """One extracted page or logical HTML/RFC unit with provenance."""

    page_number: int
    pdf_page_index: int | None
    printed_page: str | None
    page_offset: int | None
    section_title: str
    text: str


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file in streaming chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _detect_printed_page_from_edges(lines: list[str]) -> str | None:
    """Heuristically extract a printed page number from the top/bottom edge lines."""
    if not lines:
        return None
    candidates = lines[:MAX_EDGE_LINES_TO_SCAN] + lines[-MAX_EDGE_LINES_TO_SCAN:]
    for line in candidates:
        stripped = line.strip()
        if not stripped or len(stripped) > MAX_HEADER_FOOTER_LINE_LEN:
            continue
        num_match = _PRINTED_PAGE_NUM_RE.match(stripped)
        if num_match:
            val = int(num_match.group(1))
            if 1 <= val <= MAX_PRINTED_PAGE_NUMBER:
                return str(val)
        roman_match = _ROMAN_PAGE_RE.match(stripped)
        if roman_match:
            return roman_match.group(1).lower()
    return None


def compute_page_offset(page_number: int, printed_page: str | None) -> int | None:
    """Return ``page_number - int(printed_page)`` when ``printed_page`` is Arabic numeric."""
    if not printed_page or not printed_page.isdigit():
        return None
    printed_int = int(printed_page)
    if printed_int < 1 or printed_int > MAX_PRINTED_PAGE_NUMBER:
        return None
    return page_number - printed_int


def _normalize_edge_line(line: str) -> str:
    """Normalize digits in header/footer lines so running headers cluster together."""
    return re.sub(r"\d+", "#", line.strip()).lower()


def _find_repeated_edge_lines(raw_pages: list[list[str]]) -> set[str]:
    """Identify running header/footer templates repeated across many PDF pages."""
    page_count = len(raw_pages)
    if page_count < MIN_REPEATED_HEADER_PAGES:
        return set()
    counts: Counter[str] = Counter()
    for lines in raw_pages:
        if not lines:
            continue
        edges = lines[:MAX_EDGE_LINES_TO_SCAN] + lines[-MAX_EDGE_LINES_TO_SCAN:]
        seen_on_page: set[str] = set()
        for line in edges:
            stripped = line.strip()
            if not stripped or len(stripped) > MAX_HEADER_FOOTER_LINE_LEN:
                continue
            norm = _normalize_edge_line(stripped)
            if norm and norm not in seen_on_page:
                counts[norm] += 1
                seen_on_page.add(norm)
    threshold = max(MIN_REPEATED_HEADER_PAGES, int(page_count * HEADER_REPEAT_RATIO))
    return {norm for norm, count in counts.items() if count >= threshold}


def _strip_running_edges(lines: list[str], repeated_edges: set[str]) -> list[str]:
    """Strip detected running headers/footers and bare page numbers from page edges."""
    if not lines:
        return lines
    start = 0
    end = len(lines)
    while start < end and start < MAX_EDGE_LINES_TO_SCAN:
        stripped = lines[start].strip()
        norm = _normalize_edge_line(stripped)
        if norm in repeated_edges or _PRINTED_PAGE_NUM_RE.match(stripped):
            start += 1
        else:
            break
    while end > start and (len(lines) - end) < MAX_EDGE_LINES_TO_SCAN:
        stripped = lines[end - 1].strip()
        norm = _normalize_edge_line(stripped)
        if norm in repeated_edges or _PRINTED_PAGE_NUM_RE.match(stripped):
            end -= 1
        else:
            break
    return lines[start:end]


def _detect_section_heading(lines: list[str], fallback: str) -> str:
    """Extract the most prominent section heading from a page's lines."""
    for line in lines:
        stripped = line.strip()
        if not (MIN_SECTION_HEADING_LEN <= len(stripped) <= MAX_SECTION_HEADING_LEN):
            continue
        if _SECTION_HEADING_RE.match(stripped):
            return stripped
    return fallback


def extract_pdf_units(path: Path) -> list[ExtractedUnit]:
    """Extract cleaned per-page units from a PDF with physical/printed page mapping."""
    raw_pages: list[list[str]] = []
    pdf_labels: list[str | None] = []
    with fitz.open(path) as document:
        has_labels = bool(document.get_page_labels())
        for page_index in range(document.page_count):
            page = document[page_index]
            text = page.get_text("text") or ""
            lines = [ln for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
            raw_pages.append(lines)
            label = page.get_label().strip() if has_labels else ""
            pdf_labels.append(label or None)

    repeated_edges = _find_repeated_edge_lines(raw_pages)
    units: list[ExtractedUnit] = []
    current_section = "Document Body"
    for page_index, lines in enumerate(raw_pages):
        page_number = page_index + 1
        printed = pdf_labels[page_index] or _detect_printed_page_from_edges(lines)
        cleaned_lines = _strip_running_edges(lines, repeated_edges)
        current_section = _detect_section_heading(cleaned_lines, current_section)
        cleaned_text = "\n".join(cleaned_lines).strip()
        if not cleaned_text:
            continue
        units.append(
            ExtractedUnit(
                page_number=page_number,
                pdf_page_index=page_index,
                printed_page=printed,
                page_offset=compute_page_offset(page_number, printed),
                section_title=current_section,
                text=cleaned_text,
            )
        )
    return units


def extract_html_units(paths: list[Path]) -> list[ExtractedUnit]:
    """Extract section-grouped units from one or more local HTML files."""
    units: list[ExtractedUnit] = []
    page_counter = 0
    for html_path in paths:
        raw_html = html_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag_name in _HTML_NOISE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        main_node = soup.find("main") or soup.find("article") or soup.body or soup
        current_section = (
            soup.title.get_text(" ", strip=True)[:MAX_SECTION_HEADING_LEN]
            if soup.title
            else html_path.stem
        )
        buffer: list[str] = []

        def _flush(section: str, chunks: list[str]) -> None:
            nonlocal page_counter
            body = "\n\n".join(chunks).strip()
            if not body:
                return
            page_counter += 1
            units.append(
                ExtractedUnit(
                    page_number=page_counter,
                    pdf_page_index=None,
                    printed_page=str(page_counter),
                    page_offset=0,
                    section_title=section,
                    text=body,
                )
            )

        for elem in main_node.find_all(["h1", "h2", "h3", "p", "li", "pre", "dd", "dt"]):
            text = elem.get_text(" ", strip=True)
            if not text:
                continue
            if elem.name in ("h1", "h2", "h3"):
                if buffer:
                    _flush(current_section, buffer)
                    buffer = []
                current_section = text[:MAX_SECTION_HEADING_LEN]
            else:
                buffer.append(text)
        if buffer:
            _flush(current_section, buffer)
    return units


def extract_text_rfc_units(path: Path) -> list[ExtractedUnit]:
    """Extract paginated units from plain text or IETF RFC documents."""
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    raw_pages = raw.split("\x0c")
    units: list[ExtractedUnit] = []
    current_section = "RFC Body"
    for idx, page_text in enumerate(raw_pages):
        lines = [ln.rstrip() for ln in page_text.split("\n")]
        non_empty = [ln for ln in lines if ln.strip()]
        if len(non_empty) < RFC_MIN_PAGE_LINES:
            continue
        printed: str | None = None
        cleaned: list[str] = []
        for line in lines:
            match = _RFC_PAGE_FOOTER_RE.search(line)
            if match:
                printed = match.group(1)
                continue
            if line.strip().startswith("RFC ") and "   " in line:
                continue
            cleaned.append(line)
        body_lines = [ln.strip() for ln in cleaned if ln.strip()]
        current_section = _detect_section_heading(body_lines, current_section)
        text = "\n".join(body_lines).strip()
        if not text:
            continue
        page_number = idx + 1
        units.append(
            ExtractedUnit(
                page_number=page_number,
                pdf_page_index=None,
                printed_page=printed or str(page_number),
                page_offset=compute_page_offset(page_number, printed or str(page_number)),
                section_title=current_section,
                text=text,
            )
        )
    return units

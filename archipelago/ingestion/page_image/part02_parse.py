"""Field extraction from an OCR'd book index (TOC) or content page.

Only fields that are actually present in the page text are emitted, so the
librarian's pre-filled form never contains an invented value.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from archipelago.ingestion.mention import extract_isbn, normalize_title

MAX_TITLE_WORDS = 18
MAX_AUTHOR_WORDS = 12
MAX_TOC_ENTRIES = 60
PAGE_NUM_MIN = 1
PAGE_NUM_MAX = 5000
HEADING_Y_MARGIN_RATIO = 0.35

_PUBLISHER_PATTERNS = (
    r"pearson education",
    r"pearson longman",
    r"pearson",
    r"mc[gm]raw[- ]hill",
    r"cambridge university press",
    r"oxford university press",
    r"mit press",
    r"springer",
    r"wiley",
    r"oreilly",
    r"addison[- ]wesley",
    r"elsevier",
    r"springer verlag",
    r"open court",
)
_COPYRIGHT_LINE_RE = re.compile(r"(?:©|\(c\)|copyright)\s*(\d{4})", re.I)
_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
_EDITION_RE = re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)\s+edition|\d+(?:st|nd|rd|th)\s+ed\.?)\b", re.I)
_EDITION_WORD_RE = re.compile(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth)\s+edition\b", re.I)
_TRAILING_PAGES_RE = re.compile(r"(?:\.{2,}|\s+|\t)(\d{1,4})\s*$")
_LEADING_NUM_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})*)[.\)]?\s+")
_CHAPTER_WORD_RE = re.compile(r"^\s*(chapter|ch\.?|unit|part|appendix|section)\s+([0-9]+|[ivxlc]+)\b", re.I)
_TOC_KEYWORDS = ("contents", "table of contents", "index")
_AUTHOR_LABEL_RE = re.compile(r"\b(?:by|written by|author)\s+([A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,5})")
_DOT_LEADER_RE = re.compile(r"[.·…]{3,}\s*\d{1,4}\s*$")
_ORG_SUFFIX_RE = re.compile(r"\b(university|institute|inc\.?|ltd\.?|llc|press|books|publishing|academy|college)\b", re.I)


@dataclass
class PageExtraction:
    """Fields recovered from one scanned page."""

    title: str = ""
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    year: str = ""
    edition: str = ""
    page_headings: list[str] = field(default_factory=list)
    toc_entries: list[dict[str, Any]] = field(default_factory=list)
    is_index_page: bool = False
    is_content_page: bool = False
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def extract_isbn_field(text: str) -> str:
    """Find an ISBN, preferring one introduced by an 'ISBN' label."""
    if not text:
        return ""
    labelled = re.search(
        r"(?:ISBN(?:\s*-?\s*1[03])?)\s*[:\-]?\s*((?:97[89][\s\-]?)?(?:\d[\s\-]?){9}[\dXx])",
        text,
        re.I,
    )
    if labelled:
        cleaned = re.sub(r"[\s\-]", "", labelled.group(1))
        if len(cleaned) in (10, 13):
            return cleaned.upper()
    return extract_isbn(text)


def extract_year(text: str) -> str:
    """Prefer the year on a copyright line, else the first plausible year."""
    if not text:
        return ""
    for line in text.splitlines():
        if re.search(r"(?:©|\(c\)|copyright)", line, re.I):
            match = _COPYRIGHT_LINE_RE.search(line)
            if match:
                return match.group(1)
    match = _YEAR_RE.search(text)
    return match.group(1) if match else ""


def extract_publisher(text: str) -> str:
    """First known publisher name appearing in the page text."""
    lowered = (text or "").lower()
    for pattern in _PUBLISHER_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            return _clean(match.group(0)).title()
    return ""


def extract_edition(text: str) -> str:
    """Edition statement, numeric or spelled-out."""
    if not text:
        return ""
    match = _EDITION_RE.search(text)
    if match:
        return _clean(match.group(1))
    match = _EDITION_WORD_RE.search(text)
    if match:
        return _clean(match.group(0))
    return ""


MIN_TOC_HEADING_CHARS = 4
MIN_TOC_HEADING_WORDS = 2


def _looks_like_toc_line(text: str) -> tuple[str, int] | None:
    """Return (heading, page) when a line looks like a contents entry.

    A trailing number alone is not enough — "Chapter 3" in body text would
    otherwise parse as a contents line. A real entry either uses dot leaders or
    carries a multi-word heading.
    """
    if not text or len(text) > 160:
        return None
    page_match = _TRAILING_PAGES_RE.search(text)
    if not page_match:
        return None
    try:
        page = int(page_match.group(1))
    except (TypeError, ValueError):
        return None
    if not (PAGE_NUM_MIN <= page <= PAGE_NUM_MAX):
        return None
    raw_heading = _clean(text[: page_match.start()])
    has_leaders = bool(_DOT_LEADER_RE.search(text))
    heading = _DOT_LEADER_RE.sub("", raw_heading).strip(" .·…")
    if len(heading) < MIN_TOC_HEADING_CHARS or not re.search(r"[A-Za-z]", heading):
        return None
    if not has_leaders and len(heading.split()) < MIN_TOC_HEADING_WORDS:
        return None
    if len(heading.split()) > MAX_TITLE_WORDS:
        return None
    return heading, page


def extract_toc(text: str) -> tuple[list[dict[str, Any]], bool]:
    """Extract contents entries and whether the page is an index/TOC page."""
    entries: list[dict[str, Any]] = []
    saw_keyword = any(k in (text or "").lower() for k in _TOC_KEYWORDS)
    for line in (text or "").splitlines():
        parsed = _looks_like_toc_line(line)
        if parsed is None:
            continue
        heading, page = parsed
        ordinal = ""
        ordinal_match = _LEADING_NUM_RE.match(line)
        if ordinal_match:
            ordinal = ordinal_match.group(1)
        else:
            chapter_match = _CHAPTER_WORD_RE.match(line)
            if chapter_match:
                ordinal = chapter_match.group(2)
        entries.append({"heading": heading, "page": page, "section": ordinal})
        if len(entries) >= MAX_TOC_ENTRIES:
            break
    return entries, bool(saw_keyword and entries)


def _candidate_titles(lines: list[str]) -> list[str]:
    """Lines that plausibly name the book, in reading order."""
    out: list[str] = []
    for line in lines:
        text = _clean(line)
        if not text or len(text) < 4 or len(text.split()) > MAX_TITLE_WORDS:
            continue
        if text.isdigit():
            continue
        lowered = text.lower()
        if any(k in lowered for k in _TOC_KEYWORDS):
            continue
        if _looks_like_toc_line(line) is not None:
            continue
        if re.match(r"^\s*(?:page\s+)?\d+\s*$", lowered):
            continue
        out.append(text)
    return out


_NAME_TOKEN_RE = re.compile(r"^[A-Z][\w.'’-]*$")
_NAME_SPLIT_RE = re.compile(r"\s*(?:,|;|\band\b|&)\s*", re.I)
_MIN_NAME_TOKENS = 2
_NAME_MIN_TOKEN_LEN = 2


def _looks_like_person_list(text: str) -> bool:
    """True for 'A. Name, B. Name and C. Name' style bylines."""
    if not text or _ORG_SUFFIX_RE.search(text):
        return False
    if re.search(r"\d", text):
        return False
    parts = [p.strip() for p in _NAME_SPLIT_RE.split(text) if p.strip()]
    if len(parts) < _MIN_NAME_TOKENS:
        return False
    tokens = text.replace(",", " ").replace(";", " ").split()
    if not tokens or len(tokens) > MAX_AUTHOR_WORDS:
        return False
    named = sum(1 for t in tokens if _NAME_TOKEN_RE.match(t) and len(t) >= _NAME_MIN_TOKEN_LEN)
    # Most tokens must look like name parts for this to be a byline.
    return named >= max(_MIN_NAME_TOKENS, int(len(tokens) * 0.6))


def extract_title_and_author(lines: list[str]) -> tuple[str, str]:
    """Pick the most likely title and author from the top of the page."""
    candidates = _candidate_titles(lines[:40])
    if not candidates:
        return "", ""

    title = ""
    for text in candidates:
        # A capitalised multi-word phrase reads like a book title.
        words = text.split()
        capitalised = sum(1 for w in words if w[:1].isupper())
        if capitalised >= max(2, len(words) // 2):
            title = text
            break
    if not title:
        title = candidates[0]

    author = ""
    for text in candidates:
        match = _AUTHOR_LABEL_RE.search(text)
        if match:
            author = _clean(match.group(1))
            break
    if not author:
        # A comma/"and" separated name list below the title is the byline.
        for text in candidates:
            if text == title or _looks_like_toc_line(text) is not None:
                continue
            if _looks_like_person_list(text):
                if normalize_title(text) not in normalize_title(title):
                    author = text
                    break
    return title, author


def extract_page_fields(text: str, lines: list[str] | None = None) -> PageExtraction:
    """Extract all supported fields from OCR text of one page."""
    text = text or ""
    extraction = PageExtraction(ocr_text=text[:MAX_OCR_TEXT_CHARS])
    extraction.isbn = extract_isbn_field(text)
    extraction.year = extract_year(text)
    extraction.publisher = extract_publisher(text)
    extraction.edition = extract_edition(text)
    entries, is_index = extract_toc(text)
    extraction.toc_entries = entries
    extraction.is_index_page = is_index
    extraction.is_content_page = bool(text) and not is_index

    title, author = extract_title_and_author(lines or text.splitlines())
    extraction.title = title
    extraction.author = author
    if not author:
        extraction.warnings.append("No author detected on this page.")
    if not extraction.isbn:
        extraction.warnings.append("No ISBN detected on this page.")
    if not extraction.title:
        extraction.warnings.append("No title detected on this page.")
    return extraction


MAX_OCR_TEXT_CHARS = 20000


def mean_confidence(blocks: list[dict[str, Any]]) -> float:
    """Average OCR confidence across recognised words."""
    if not blocks:
        return 0.0
    return round(sum(b.get("conf", 0.0) for b in blocks) / len(blocks), 2)

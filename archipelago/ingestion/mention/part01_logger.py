"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from . import _deps as _rt  # noqa: F401


logger = logging.getLogger("archipelago.ingestion.mention")


MAX_CANDIDATES = 8


MIN_FUZZY_SCORE = 62


MIN_TOKEN_LENGTH = 3


ISBN_MIN_DIGITS = 10


HF_REPO_ID = "Prataykarali/Library_books"


HF_BLOB_BASE = f"https://huggingface.co/datasets/{HF_REPO_ID}/blob/main/"


PDF_SUBDIRS = ("papers", "textbooks", "web_syllabi", "archipelago-books-cs")


_OPAC_URL = "https://uemk-opac.l2c2.co.in"


_STOPWORDS = frozenset({
    "the", "a", "an", "of", "and", "or", "for", "in", "on", "to", "is", "are",
    "with", "by", "from", "at", "as", "edition", "ed", "vol", "volume",
})


MATCH_KIND_EXACT_ISBN = "exact_isbn"


MATCH_KIND_CATALOG = "catalog_record"


MATCH_KIND_REGISTRY = "registry"


MATCH_KIND_PEARSON = "pearson_catalog"


MATCH_KIND_HF = "huggingface"


MATCH_KIND_LOCAL = "local_pdf"


METADATA_TRUST_MIN_CONFIDENCE = 95.0


SOURCE_NAMES = {
    MATCH_KIND_CATALOG: "Central Library Catalogue",
    MATCH_KIND_REGISTRY: "Archipelago Resource Registry",
    MATCH_KIND_PEARSON: "Pearson eLibrary",
    MATCH_KIND_HF: "Hugging Face Library",
    MATCH_KIND_LOCAL: "Local Corpus",
    MATCH_KIND_EXACT_ISBN: "Identifier Lookup",
}


@dataclass
class MentionMatch:
    """One resolved candidate for a librarian's book mention."""

    title: str
    match_kind: str
    source: str
    confidence: float
    source_url: str = ""
    doc_id: str = ""
    author: str = ""
    year: str = ""
    publisher: str = ""
    isbn: str = ""
    edition: str = ""
    page_count: int = 0
    domain: str = ""
    is_catalog_only: bool = False
    shelf_location: str = ""
    available_copies: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MentionResult:
    """Outcome of a mention lookup, including an explicit no-match reason."""

    query: str
    matches: list[MentionMatch] = field(default_factory=list)
    searched: list[str] = field(default_factory=list)
    no_match_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "found": bool(self.matches),
            "match_count": len(self.matches),
            "matches": [m.to_dict() for m in self.matches],
            "searched_sources": self.searched,
            "no_match_reason": self.no_match_reason,
        }


def normalize_title(value: str | None) -> str:
    """Lowercase alphanumeric form used for deterministic title comparison."""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def title_tokens(value: str | None) -> set[str]:
    """Content tokens for a title, ignoring filler words and short fragments."""
    return {
        t for t in normalize_title(value).split()
        if len(t) >= MIN_TOKEN_LENGTH and t not in _STOPWORDS
    }


def extract_isbn(value: str | None) -> str:
    """Pull a 10/13 digit ISBN out of free text, ignoring separators."""
    if not value:
        return ""
    digits = re.sub(r"[^0-9Xx]", "", str(value))
    for length in (13, 10):
        if len(digits) == length:
            return digits.upper()
    match = re.search(r"(?:97[89][\s-]?)?(?:\d[\s-]?){9}[\dXx]", str(value))
    if match:
        cleaned = re.sub(r"[\s-]", "", match.group(0))
        if len(cleaned) >= ISBN_MIN_DIGITS:
            return cleaned.upper()
    return ""


def score_against(query_tokens: set[str], candidate: str) -> float:
    """Deterministic 0-100 relevance score for a candidate title."""
    cand_tokens = title_tokens(candidate)
    if not query_tokens or not cand_tokens:
        return 0.0
    shared = query_tokens & cand_tokens
    if not shared:
        return 0.0
    coverage = len(shared) / len(query_tokens)
    precision = len(shared) / len(cand_tokens)
    return round(100.0 * (0.6 * coverage + 0.4 * precision), 2)


def _best(candidates: list[MentionMatch]) -> list[MentionMatch]:
    """Deduplicate by normalized title, keeping the strongest match."""
    best: dict[str, MentionMatch] = {}
    for candidate in candidates:
        key = normalize_title(candidate.title)
        current = best.get(key)
        if current is None or candidate.confidence > current.confidence:
            best[key] = candidate
    return sorted(best.values(), key=lambda c: c.confidence, reverse=True)[:MAX_CANDIDATES]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _search_resource_catalog(query: str, query_tokens: set[str]) -> list[MentionMatch]:
    """Search the institutional Kùzu Resource catalogue (Koha holdings)."""
    from archipelago.inference.graph_lock import graph_lock

    out: list[MentionMatch] = []
    try:
        import kuzu
        from archipelago.inference import state as st
        if getattr(st, "db", None) is None:
            return out
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            res = conn.execute(
                "MATCH (r:Resource) "
                "RETURN r.title, r.author, r.publisher, r.copyright_year, "
                "r.biblionumber, r.available_copies, r.total_copies "
                "LIMIT 5000"
            )
            while res.has_next():
                row = res.get_next()
                title = row[0] or ""
                if not title:
                    continue
                score = score_against(query_tokens, title)
                if score < MIN_FUZZY_SCORE:
                    continue
                biblionumber = str(row[4] or "").strip()
                out.append(MentionMatch(
                    title=str(title),
                    match_kind=MATCH_KIND_CATALOG,
                    source=SOURCE_NAMES[MATCH_KIND_CATALOG],
                    confidence=score,
                    # No verified per-title OPAC page exists, so link the
                    # institutional catalogue itself rather than inventing one.
                    source_url=_OPAC_URL,
                    author=str(row[1] or ""),
                    publisher=str(row[2] or ""),
                    year=str(row[3] or "") if row[3] is not None else "",
                    isbn=biblionumber if biblionumber and biblionumber != "0" else "",
                    is_catalog_only=True,
                    shelf_location=biblionumber if biblionumber and biblionumber != "0" else "",
                    available_copies=int(row[5]) if row[5] is not None else None,
                    page_count=int(row[6]) if row[6] is not None else 0,
                    notes=["Physical catalogue record; no licensed digital file."],
                ))
    except Exception as exc:
        logger.debug("Resource catalogue mention search unavailable: %s", exc)
    return out


def _search_registry(query: str, query_tokens: set[str]) -> list[MentionMatch]:
    """Search the bundled Archipelago resource registry."""
    out: list[MentionMatch] = []
    try:
        from archipelago.resolver.resource_registry import get_registry
        registry = get_registry()
    except Exception as exc:
        logger.debug("Resource registry unavailable: %s", exc)
        return out
    for record in registry.all_resources():
        score = score_against(query_tokens, record.title)
        if score < MIN_FUZZY_SCORE:
            continue
        source_url = record.blob_url or record.reader_url
        out.append(MentionMatch(
            title=record.title or record.resource_id,
            match_kind=MATCH_KIND_REGISTRY,
            source=record.source or SOURCE_NAMES[MATCH_KIND_REGISTRY],
            confidence=score,
            source_url=source_url,
            doc_id=record.hf_file_path or record.resource_id,
            author=record.author,
            isbn=record.isbn,
            edition=record.edition,
            page_count=record.page_count,
            domain=record.domain,
        ))
    return out


def _search_pearson(query: str, query_tokens: set[str]) -> list[MentionMatch]:
    """Search the Pearson eLibrary catalogue for exact reader pages."""
    out: list[MentionMatch] = []
    try:
        from archipelago.resolver.pearson import _load_pearson_catalog, build_reader_url
        catalog = _load_pearson_catalog()
    except Exception as exc:
        logger.debug("Pearson catalog unavailable: %s", exc)
        return out
    for book in catalog:
        title = book.get("title") or ""
        if not title:
            continue
        # Score title and author together: a librarian typing "Computer Networks
        # Tanenbaum" should still find the catalogue title.
        author = str(book.get("author") or "")
        best = max(
            score_against(query_tokens, title),
            score_against(query_tokens, f"{title} {author}"),
        )
        if best < MIN_FUZZY_SCORE:
            continue
        out.append(MentionMatch(
            title=title,
            match_kind=MATCH_KIND_PEARSON,
            source=SOURCE_NAMES[MATCH_KIND_PEARSON],
            confidence=best,
            # Exact reader page for this specific title.
            source_url=build_reader_url(book, page=1),
            doc_id=str(book.get("id") or ""),
            author=author,
            isbn=str(book.get("isbn") or ""),
            page_count=int(book.get("page_count") or 0),
            domain=str(book.get("domain") or ""),
            notes=["Institutional login required at Pearson eLibrary."],
        ))
    return out


def _search_huggingface(query: str, query_tokens: set[str]) -> list[MentionMatch]:
    """Search the Hugging Face dataset, returning exact per-file blob pages."""
    out: list[MentionMatch] = []
    try:
        from archipelago.resolver.huggingface import enumerate_hf_resources
        resources = enumerate_hf_resources()
    except Exception as exc:
        logger.debug("Hugging Face enumeration unavailable: %s", exc)
        return out
    for resource in resources:
        path = str(resource.get("filename") or "")
        if not path or "/librarian_uploads/" in path:
            continue
        stem = Path(path).stem.replace("_", " ")
        score = score_against(query_tokens, stem)
        if score < MIN_FUZZY_SCORE:
            continue
        out.append(MentionMatch(
            title=stem,
            match_kind=MATCH_KIND_HF,
            source=SOURCE_NAMES[MATCH_KIND_HF],
            confidence=score,
            # Exact dataset file page, never the repo root.
            source_url=resource.get("blob_url") or f"{HF_BLOB_BASE}{path}",
            doc_id=path,
        ))
    return out


def _search_local_pdfs(query: str, query_tokens: set[str]) -> list[MentionMatch]:
    """Search PDFs already present in the local corpus."""
    out: list[MentionMatch] = []
    root = _repo_root()
    pdf_dir = root / "pdfs"
    if not pdf_dir.is_dir():
        return out
    for pdf in sorted(pdf_dir.rglob("*.pdf")):
        score = score_against(query_tokens, pdf.stem)
        if score < MIN_FUZZY_SCORE:
            continue
        try:
            rel = pdf.relative_to(pdf_dir).as_posix()
        except ValueError:
            rel = pdf.name
        out.append(MentionMatch(
            title=pdf.stem.replace("_", " "),
            match_kind=MATCH_KIND_LOCAL,
            source=SOURCE_NAMES[MATCH_KIND_LOCAL],
            confidence=score,
            source_url=f"/pdfs/{rel}",
            doc_id=rel,
        ))
    return out

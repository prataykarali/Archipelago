"""Compliant Google Scholar workflow: outbound search links + user BibTeX/RIS import."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import re
from typing import Any

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.scholar_deeplink import generate_scholar_url

USER_IMPORT_SOURCE_TYPE = "USER_IMPORTED_GOOGLE_SCHOLAR"
BIBTEX_HEAD_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
BIBTEX_FIELD_RE = re.compile(r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\"|(\d+))")
RIS_LINE_RE = re.compile(r"^([A-Z0-9]{2})\s{1,2}-\s*(.*)$")
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
ARXIV_RE = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)


def build_google_scholar_link(topic: str) -> str:
    """Return a topic-specific outbound link for manual researcher verification."""
    return str(generate_scholar_url(topic))


def _split_authors(raw: str) -> list[PaperAuthor]:
    parts = [p.strip() for p in re.split(r"\s+and\s+", raw) if p.strip()]
    return [PaperAuthor(name=p) for p in parts]


def _parse_bibtex(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    for match in BIBTEX_HEAD_RE.finditer(text):
        etype, citekey = match.group(1).lower(), match.group(2)
        depth = 1
        pos = match.end()
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        if depth != 0:
            errors.append(f"malformed_bibtex_braces:{citekey}")
            continue
        body = text[match.end() : pos - 1]
        fields: dict[str, str] = {}
        for fmatch in BIBTEX_FIELD_RE.finditer(body):
            key = fmatch.group(1).lower()
            val = (fmatch.group(2) or fmatch.group(3) or fmatch.group(4) or "").strip()
            fields[key] = " ".join(val.split())
        if not fields.get("title"):
            errors.append(f"bibtex_missing_title:{citekey}")
            continue
        entries.append({"entry_type": etype, "citekey": citekey, **fields})
    if not entries and "@" in text and not errors:
        errors.append("malformed_bibtex_syntax")
    return entries, errors


def _parse_ris(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    current: dict[str, Any] = {"authors": []}
    has_tag = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rmatch = RIS_LINE_RE.match(line)
        if rmatch:
            has_tag = True
            tag, val = rmatch.group(1).upper(), rmatch.group(2).strip()
            if tag == "TY":
                current = {"authors": [], "entry_type": val.lower()}
            elif tag in {"TI", "T1"}:
                current["title"] = val
            elif tag in {"AU", "A1"}:
                current["authors"].append(val)
            elif tag in {"PY", "Y1"}:
                current["year"] = val[:4]
            elif tag in {"JO", "T2", "JF"}:
                current["venue"] = val
            elif tag == "DO":
                current["doi"] = val
            elif tag == "UR":
                current["url"] = val
            elif tag == "AB":
                current["abstract"] = val
            elif tag == "ER":
                if current.get("title"):
                    entries.append(current)
                else:
                    errors.append("ris_missing_title")
                current = {"authors": []}
    if not has_tag and "TY  -" not in text:
        errors.append("malformed_ris_syntax")
    return entries, errors


def import_scholar_citations(
    raw_text: str,
    fmt: str = "auto",
    existing_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Parse user-exported BibTeX/RIS, preserve provenance, and deduplicate safely."""
    text = (raw_text or "").strip()
    if not text:
        return {"records": [], "errors": ["empty_import_payload"], "source_type": USER_IMPORT_SOURCE_TYPE}

    chosen = fmt.lower().strip()
    if chosen == "auto":
        chosen = "bibtex" if text.lstrip().startswith("@") else ("ris" if "TY  -" in text else "unknown")
    if chosen == "bibtex":
        parsed, errors = _parse_bibtex(text)
    elif chosen == "ris":
        parsed, errors = _parse_ris(text)
    else:
        return {"records": [], "errors": ["unsupported_or_malformed_format"], "source_type": USER_IMPORT_SOURCE_TYPE}

    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    imported_candidates: list[dict[str, Any]] = []
    for item in parsed:
        doi_match = DOI_RE.search(str(item.get("doi") or item.get("url") or ""))
        doi = doi_match.group(0) if doi_match else None
        arxiv_match = ARXIV_RE.search(str(item.get("eprint") or item.get("url") or ""))
        arxiv_id = arxiv_match.group(1) if arxiv_match else None
        authors = (
            [PaperAuthor(name=a) for a in item["authors"]]
            if isinstance(item.get("authors"), list)
            else _split_authors(str(item.get("author") or ""))
        )
        paper = PaperRecord(
            title=str(item["title"]),
            identifiers=PaperIdentifiers(doi=doi, arxiv_id=arxiv_id),
            abstract=item.get("abstract"),
            authors=authors,
            venue=item.get("venue") or item.get("journal") or item.get("booktitle"),
            publication_date=str(item.get("year") or "")[:10] or None,
            publication_type=item.get("entry_type") or "article",
        )
        imported_candidates.append(
            {
                "source": USER_IMPORT_SOURCE_TYPE,
                "paper": paper,
                "provenance": ProvenancePointer(
                    source_type=USER_IMPORT_SOURCE_TYPE,
                    artifact_sha256=sha,
                    source_record_id=item.get("citekey") or doi or arxiv_id,
                    source_url=item.get("url"),
                    fetched_at=now,
                ),
                "citation_count": None,
                "source_metadata": {
                    "source_type": USER_IMPORT_SOURCE_TYPE,
                    "is_user_imported": True,
                    "import_format": chosen,
                },
            }
        )

    combined = list(existing_candidates or []) + imported_candidates
    canonical = Canonicalizer().canonicalize_candidates(combined)
    return {
        "source_type": USER_IMPORT_SOURCE_TYPE,
        "format": chosen,
        "imported_count": len(imported_candidates),
        "deduplicated_total": len(canonical),
        "errors": errors,
        "records": [
            {
                "paper_id": c["paper"].paper_id,
                "title": c["paper"].title,
                "doi": c["paper"].identifiers.doi,
                "arxiv_id": c["paper"].identifiers.arxiv_id,
                "year": c["paper"].publication_date,
                "venue": c["paper"].venue,
                "authors": [a.model_dump(mode="json") for a in c["paper"].authors],
                "source_type": (c.get("source_metadata") or {}).get("source_type") or c.get("source"),
                "is_user_imported": bool((c.get("source_metadata") or {}).get("is_user_imported")),
            }
            for c in canonical
        ],
    }

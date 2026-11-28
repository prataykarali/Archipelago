"""Structural classification, noise filtering, and section-aware segmentation.

Separates genuine body passages from Tables of Contents, bibliographies /
references, back-of-book indexes, front matter, and corrupted/tiny fragments.
Deduplicates identical normalized passages so corpus counts are never inflated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import re

from archipelago.corpus.extractors import ExtractedUnit

MAX_PASSAGE_CHARS = 1600
TARGET_PASSAGE_CHARS = 1200
MIN_PASSAGE_CHARS = 180
MIN_PASSAGE_WORDS = 30
MIN_ALPHA_RATIO = 0.55
MIN_PRINTABLE_RATIO = 0.92
MIN_QUALITY_SCORE = 0.50
TOC_DOT_LEADER_THRESHOLD = 3
REF_LINE_RATIO_THRESHOLD = 0.40
INDEX_LINE_RATIO_THRESHOLD = 0.45
MIN_LINES_FOR_STRUCTURAL_RATIO = 4
PASSAGE_HASH_PREFIX_LEN = 12

_TOC_HEADING_RE = re.compile(
    r"^\s*(?:table\s+of\s+contents|contents|list\s+of\s+(?:figures|tables))\b",
    re.IGNORECASE,
)
_DOT_LEADER_RE = re.compile(r"\.{4,}\s*\d+\s*$")
_REF_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s+)?(?:references|bibliography|works\s+cited)\s*$",
    re.IGNORECASE,
)
_REF_ENTRY_RE = re.compile(
    r"^\s*(?:\[\d+\]|\d+\.\s+[A-Z][a-z]+,|[A-Z][a-z]+,\s+[A-Z]\.|"
    r".*\(\d{4}\)\.|.*(?:arXiv:\d{4}|Proceedings\s+of|IEEE|ACM|Springer))",
)
_INDEX_HEADING_RE = re.compile(r"^\s*(?:index|subject\s+index|author\s+index)\s*$", re.IGNORECASE)
_INDEX_ENTRY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\s,\-()/]+,\s*\d+(?:\s*[-\u2013,]\s*\d+)*\s*$")
_FRONT_MATTER_RE = re.compile(
    r"\b(?:all\s+rights\s+reserved|isbn[\s:-]*\d|library\s+of\s+congress|"
    r"printed\s+in\s+the|copyright\s+©|table\s+of\s+contents)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")
_WHITESPACE_RE = re.compile(r"\s+")


class StructuralClass(StrEnum):
    """Structural classification label for an extracted page or passage."""

    BODY = "BODY"
    TOC = "TOC"
    REFERENCES = "REFERENCES"
    INDEX = "INDEX"
    FRONT_MATTER = "FRONT_MATTER"
    LOW_QUALITY = "LOW_QUALITY"


@dataclass(frozen=True)
class PassageRecord:
    """One validated, section-aware passage ready for enrichment and serialization."""

    passage_id: str
    doc_id: str
    source_id: str
    pdf_sha256: str
    page_number: int
    pdf_page_index: int | None
    printed_page: str | None
    page_offset: int | None
    section_title: str
    structural_class: StructuralClass
    text_offset_start: int
    text_offset_end: int
    word_count: int
    quality_score: float
    text: str


@dataclass
class SegmentationStats:
    """Per-document counts of kept passages and filtered structural noise."""

    kept_passages: int = 0
    filtered_toc: int = 0
    filtered_references: int = 0
    filtered_index: int = 0
    filtered_front_matter: int = 0
    filtered_low_quality: int = 0
    filtered_duplicates: int = 0


def compute_quality_score(text: str) -> float:
    """Compute a deterministic [0.0, 1.0] extraction quality score."""
    stripped = text.strip()
    if not stripped:
        return 0.0
    total = len(stripped)
    printable = sum(1 for ch in stripped if ch.isprintable() or ch in "\n\t")
    alpha = sum(1 for ch in stripped if ch.isalpha())
    words = stripped.split()
    printable_ratio = printable / total
    alpha_ratio = alpha / total
    if printable_ratio < MIN_PRINTABLE_RATIO or alpha_ratio < MIN_ALPHA_RATIO:
        return round(min(printable_ratio, alpha_ratio) * 0.5, 4)
    if len(words) < MIN_PASSAGE_WORDS or total < MIN_PASSAGE_CHARS:
        return round(min(len(words) / MIN_PASSAGE_WORDS, total / MIN_PASSAGE_CHARS) * 0.45, 4)
    avg_word_len = sum(len(w) for w in words) / len(words)
    word_len_penalty = 1.0 if 3.0 <= avg_word_len <= 14.0 else 0.7
    score = (0.45 * printable_ratio + 0.55 * min(1.0, alpha_ratio / 0.75)) * word_len_penalty
    return round(min(1.0, max(0.0, score)), 4)


def classify_structure(text: str, section_title: str = "") -> StructuralClass:
    """Classify extracted text into BODY vs non-body structural noise."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return StructuralClass.LOW_QUALITY

    first_line = lines[0]
    sec_lower = section_title.lower()

    if _TOC_HEADING_RE.match(first_line) or "table of contents" in sec_lower:
        return StructuralClass.TOC
    dot_leaders = sum(1 for ln in lines if _DOT_LEADER_RE.search(ln))
    if dot_leaders >= TOC_DOT_LEADER_THRESHOLD:
        return StructuralClass.TOC

    if _INDEX_HEADING_RE.match(first_line) or sec_lower.strip() in ("index", "subject index"):
        return StructuralClass.INDEX
    if len(lines) >= MIN_LINES_FOR_STRUCTURAL_RATIO:
        index_hits = sum(1 for ln in lines if _INDEX_ENTRY_RE.match(ln))
        if (index_hits / len(lines)) >= INDEX_LINE_RATIO_THRESHOLD:
            return StructuralClass.INDEX

    if _REF_HEADING_RE.match(first_line) or sec_lower.strip() in ("references", "bibliography"):
        return StructuralClass.REFERENCES
    if len(lines) >= MIN_LINES_FOR_STRUCTURAL_RATIO:
        ref_hits = sum(1 for ln in lines if _REF_ENTRY_RE.match(ln))
        if (ref_hits / len(lines)) >= REF_LINE_RATIO_THRESHOLD:
            return StructuralClass.REFERENCES

    if len(text) < MAX_PASSAGE_CHARS and len(_FRONT_MATTER_RE.findall(text)) >= 2:
        return StructuralClass.FRONT_MATTER

    if compute_quality_score(text) < MIN_QUALITY_SCORE:
        return StructuralClass.LOW_QUALITY

    return StructuralClass.BODY


def _split_into_chunks(text: str) -> list[tuple[int, int, str]]:
    """Split text into section-aware chunks bounded by [MIN_PASSAGE_CHARS, MAX_PASSAGE_CHARS]."""
    normalized = text.strip()
    if len(normalized) <= MAX_PASSAGE_CHARS:
        return [(0, len(normalized), normalized)]

    sentences = _SENTENCE_SPLIT_RE.split(normalized)
    chunks: list[tuple[int, int, str]] = []
    current_parts: list[str] = []
    current_len = 0
    cursor = 0

    for sentence in sentences:
        sent = sentence.strip()
        if not sent:
            continue
        if len(sent) > MAX_PASSAGE_CHARS:
            if current_parts:
                chunk_text = " ".join(current_parts).strip()
                chunks.append((cursor, cursor + len(chunk_text), chunk_text))
                cursor += len(chunk_text) + 1
                current_parts = []
                current_len = 0
            for offset in range(0, len(sent), TARGET_PASSAGE_CHARS):
                piece = sent[offset : offset + MAX_PASSAGE_CHARS].strip()
                if piece:
                    chunks.append((cursor, cursor + len(piece), piece))
                    cursor += len(piece) + 1
            continue

        projected = current_len + len(sent) + (1 if current_parts else 0)
        if projected > MAX_PASSAGE_CHARS and current_parts:
            chunk_text = " ".join(current_parts).strip()
            chunks.append((cursor, cursor + len(chunk_text), chunk_text))
            cursor += len(chunk_text) + 1
            current_parts = [sent]
            current_len = len(sent)
        else:
            current_parts.append(sent)
            current_len = projected

    if current_parts:
        chunk_text = " ".join(current_parts).strip()
        chunks.append((cursor, cursor + len(chunk_text), chunk_text))
    return chunks


def _normalized_fingerprint(text: str) -> str:
    """Return a deduplication digest over lowercased whitespace-collapsed text."""
    collapsed = _WHITESPACE_RE.sub(" ", text.lower()).strip()
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


def segment_units(
    units: list[ExtractedUnit],
    *,
    doc_id: str,
    source_id: str,
    file_sha256: str,
    seen_fingerprints: set[str] | None = None,
) -> tuple[list[PassageRecord], SegmentationStats]:
    """Classify, filter, segment, and deduplicate extracted units into passages."""
    stats = SegmentationStats()
    passages: list[PassageRecord] = []
    dedup = seen_fingerprints if seen_fingerprints is not None else set()
    sha_prefix = file_sha256[:PASSAGE_HASH_PREFIX_LEN]

    for unit in units:
        unit_class = classify_structure(unit.text, unit.section_title)
        if unit_class != StructuralClass.BODY:
            _record_filtered(stats, unit_class)
            continue

        for start, end, chunk_text in _split_into_chunks(unit.text):
            chunk_class = classify_structure(chunk_text, unit.section_title)
            if chunk_class != StructuralClass.BODY:
                _record_filtered(stats, chunk_class)
                continue
            score = compute_quality_score(chunk_text)
            if score < MIN_QUALITY_SCORE:
                stats.filtered_low_quality += 1
                continue
            fingerprint = _normalized_fingerprint(chunk_text)
            if fingerprint in dedup:
                stats.filtered_duplicates += 1
                continue
            dedup.add(fingerprint)
            words = chunk_text.split()
            passages.append(
                PassageRecord(
                    passage_id=f"d14:{sha_prefix}:p{unit.page_number}:c{start}",
                    doc_id=doc_id,
                    source_id=source_id,
                    pdf_sha256=file_sha256,
                    page_number=unit.page_number,
                    pdf_page_index=unit.pdf_page_index,
                    printed_page=unit.printed_page,
                    page_offset=unit.page_offset,
                    section_title=unit.section_title,
                    structural_class=StructuralClass.BODY,
                    text_offset_start=start,
                    text_offset_end=end,
                    word_count=len(words),
                    quality_score=score,
                    text=chunk_text,
                )
            )
            stats.kept_passages += 1

    return passages, stats


def _record_filtered(stats: SegmentationStats, structural_class: StructuralClass) -> None:
    """Increment the appropriate filtered counter for ``structural_class``."""
    if structural_class == StructuralClass.TOC:
        stats.filtered_toc += 1
    elif structural_class == StructuralClass.REFERENCES:
        stats.filtered_references += 1
    elif structural_class == StructuralClass.INDEX:
        stats.filtered_index += 1
    elif structural_class == StructuralClass.FRONT_MATTER:
        stats.filtered_front_matter += 1
    else:
        stats.filtered_low_quality += 1

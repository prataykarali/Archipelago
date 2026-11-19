"""Chunking, boilerplate/bibliography filtering, and exact/near deduplication."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import re

from .constants import (
    ALLOWED_WHITESPACE_ORDS,
    BIB_CITATION_LINE_MIN_RATIO,
    BIB_MIN_LINES,
    CONTROL_ORD_UPPER,
    MAX_CHUNK_CHARS,
    MAX_CONTROL_CHAR_RATIO,
    MAX_SHINGLE_POSTING_FREQ,
    MAX_SINGLE_CHAR_TOKEN_RATIO,
    MIN_CHUNK_CHARS,
    MIN_PROSE_WORDS_PER_SENTENCE,
    MIN_TOKENS_FOR_MATH_CHECK,
    MIN_TOKENS_FOR_NEAR_DUP,
    MIN_USABLE_CHARS,
    MIN_USABLE_TOKENS,
    NAV_BOILERPLATE_PHRASES,
    NEAR_DUP_JACCARD_THRESHOLD,
    PARAGRAPH_JOIN_SEP,
    SHINGLE_SIZE,
    TARGET_CHUNK_CHARS,
)
from .models import DuplicatePair, ExtractedUnit

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
TOKEN_RE = re.compile(r"\S+")
ALPHA_WORD_RE = re.compile(r"[A-Za-z]{2,}")
SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")
NORMALIZE_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
WHITESPACE_RE = re.compile(r"\s+")
CID_RE = re.compile(r"\(cid:\d+\)")
BIB_LINE_RE = re.compile(r"(?:^\[\w+\]|\b(?:19|20)\d{2}\b.*\bpp?\.|\bRFC\s*\d+\b|\bIEEE\b|\bACM\b)")
EXCLUDED_HEADING_KEYWORDS: tuple[str, ...] = (
    "bibliography",
    "references",
    "table of contents",
    "acknowledgements",
    "about the authors",
    "licensing",
    "index",
)


@dataclass(frozen=True)
class CandidateChunk:
    """Chunked unit prior to quality/dedup filtering."""

    chunk_index: int
    page_start: int | None
    page_end: int | None
    section_ref: str
    section_heading: str
    text: str


def normalize_for_dedup(text: str) -> str:
    """Normalize text for exact-duplicate SHA-256 and shingling."""
    alnum = NORMALIZE_NON_ALNUM_RE.sub(" ", text.lower())
    return WHITESPACE_RE.sub(" ", alnum).strip()


def compute_normalized_sha256(text: str) -> str:
    """Return SHA-256 of normalized passage text."""
    return hashlib.sha256(normalize_for_dedup(text).encode("utf-8")).hexdigest()


def compute_passage_sha256(text: str) -> str:
    """Return SHA-256 of exact UTF-8 passage text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def count_tokens(text: str) -> int:
    """Count whitespace-delimited tokens."""
    return len(TOKEN_RE.findall(text))


def _split_long_paragraph(text: str, max_chars: int) -> list[str]:
    """Split oversized paragraph deterministically on sentence/word boundaries."""
    if len(text) <= max_chars:
        return [text]
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    out: list[str] = []
    buf = ""
    for sent in sentences:
        if len(sent) > max_chars:
            if buf:
                out.append(buf)
                buf = ""
            word_buf = ""
            for word in sent.split():
                cand = f"{word_buf} {word}".strip() if word_buf else word
                if len(cand) <= max_chars:
                    word_buf = cand
                else:
                    if word_buf:
                        out.append(word_buf)
                    word_buf = word[:max_chars]
            if word_buf:
                out.append(word_buf)
            continue
        cand = f"{buf} {sent}".strip() if buf else sent
        if len(cand) <= max_chars:
            buf = cand
        else:
            if buf:
                out.append(buf)
            buf = sent
    if buf:
        out.append(buf)
    return out


def chunk_extracted_units(
    units: list[ExtractedUnit],
    target_chars: int = TARGET_CHUNK_CHARS,
    max_chars: int = MAX_CHUNK_CHARS,
    min_chars: int = MIN_CHUNK_CHARS,
) -> list[CandidateChunk]:
    """Chunk ExtractedUnits deterministically while preserving honest page/section refs."""
    chunks: list[CandidateChunk] = []
    for unit in units:
        paragraphs = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(unit.text) if p.strip()]
        segments: list[str] = []
        for para in paragraphs:
            segments.extend(_split_long_paragraph(para, max_chars=max_chars))

        buf: list[str] = []
        buf_len = 0
        for seg in segments:
            sep_len = len(PARAGRAPH_JOIN_SEP) if buf else 0
            if buf and (buf_len + sep_len + len(seg) > max_chars or buf_len >= target_chars):
                chunks.append(
                    CandidateChunk(
                        chunk_index=len(chunks),
                        page_start=unit.page_number,
                        page_end=unit.page_number,
                        section_ref=unit.section_ref,
                        section_heading=unit.section_heading,
                        text=PARAGRAPH_JOIN_SEP.join(buf).strip(),
                    )
                )
                buf = []
                buf_len = 0
            buf.append(seg)
            buf_len = sum(len(x) for x in buf) + len(PARAGRAPH_JOIN_SEP) * (len(buf) - 1)

        if buf:
            text = PARAGRAPH_JOIN_SEP.join(buf).strip()
            if (
                chunks
                and len(text) < min_chars
                and chunks[-1].section_ref == unit.section_ref
                and len(chunks[-1].text) + len(PARAGRAPH_JOIN_SEP) + len(text) <= max_chars
            ):
                prev = chunks[-1]
                chunks[-1] = CandidateChunk(
                    chunk_index=prev.chunk_index,
                    page_start=prev.page_start,
                    page_end=unit.page_number,
                    section_ref=prev.section_ref,
                    section_heading=prev.section_heading,
                    text=f"{prev.text}{PARAGRAPH_JOIN_SEP}{text}",
                )
            else:
                chunks.append(
                    CandidateChunk(
                        chunk_index=len(chunks),
                        page_start=unit.page_number,
                        page_end=unit.page_number,
                        section_ref=unit.section_ref,
                        section_heading=unit.section_heading,
                        text=text,
                    )
                )
    return [
        CandidateChunk(
            chunk_index=idx,
            page_start=c.page_start,
            page_end=c.page_end,
            section_ref=c.section_ref,
            section_heading=c.section_heading,
            text=c.text,
        )
        for idx, c in enumerate(chunks)
    ]


def _has_prose_sentence(text: str) -> bool:
    """Return True if text has at least one multi-word prose sentence."""
    if not SENTENCE_END_RE.search(text):
        return False
    for fragment in SENTENCE_END_RE.split(text):
        if len(ALPHA_WORD_RE.findall(fragment)) >= MIN_PROSE_WORDS_PER_SENTENCE:
            return True
    return False


def classify_chunk_rejection(section_heading: str, text: str) -> str | None:
    """Return rejection reason if chunk is boilerplate, bibliography, or malformed."""
    heading_lower = section_heading.lower()
    if any(kw in heading_lower for kw in EXCLUDED_HEADING_KEYWORDS):
        return "boilerplate_or_bib"

    lowered = text.lower()
    if any(phrase in lowered for phrase in NAV_BOILERPLATE_PHRASES):
        return "boilerplate_or_bib"

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= BIB_MIN_LINES:
        bib_lines = sum(1 for ln in lines if BIB_LINE_RE.search(ln))
        if (bib_lines / len(lines)) >= BIB_CITATION_LINE_MIN_RATIO:
            return "boilerplate_or_bib"

    stripped = text.strip()
    tokens = TOKEN_RE.findall(stripped)
    if len(stripped) < MIN_USABLE_CHARS or len(tokens) < MIN_USABLE_TOKENS:
        return "malformed_or_short"

    if "\ufffd" in stripped or bool(CID_RE.search(stripped)):
        return "malformed_or_short"

    bad_ctrl = sum(
        1
        for ch in stripped
        if ord(ch) < CONTROL_ORD_UPPER and ord(ch) not in ALLOWED_WHITESPACE_ORDS
    )
    if (bad_ctrl / len(stripped)) > MAX_CONTROL_CHAR_RATIO:
        return "malformed_or_short"

    if len(tokens) >= MIN_TOKENS_FOR_MATH_CHECK:
        single_char = sum(1 for tok in tokens if len(tok) == 1 and tok not in {"a", "I"})
        if (single_char / len(tokens)) >= MAX_SINGLE_CHAR_TOKEN_RATIO:
            return "malformed_or_short"

    if not _has_prose_sentence(stripped):
        return "malformed_or_short"

    return None


def extract_shingles(text: str, shingle_size: int = SHINGLE_SIZE) -> frozenset[str]:
    """Extract deterministic word n-gram shingles from normalized text."""
    tokens = normalize_for_dedup(text).split()
    if len(tokens) < MIN_TOKENS_FOR_NEAR_DUP or len(tokens) < shingle_size:
        return frozenset()
    return frozenset(
        " ".join(tokens[idx : idx + shingle_size]) for idx in range(len(tokens) - shingle_size + 1)
    )


def find_near_duplicates(
    passage_items: list[tuple[str, str]],
    threshold: float = NEAR_DUP_JACCARD_THRESHOLD,
) -> list[DuplicatePair]:
    """Find near-duplicate pairs deterministically via inverted shingle index."""
    shingles_by_id: dict[str, frozenset[str]] = {}
    inverted: dict[str, list[str]] = defaultdict(list)

    for pid, text in passage_items:
        shingles = extract_shingles(text)
        if not shingles:
            continue
        shingles_by_id[pid] = shingles
        for sh in shingles:
            inverted[sh].append(pid)

    candidates: set[tuple[str, str]] = set()
    for posting in inverted.values():
        if len(posting) <= 1 or len(posting) > MAX_SHINGLE_POSTING_FREQ:
            continue
        for i in range(len(posting)):
            for j in range(i + 1, len(posting)):
                a, b = posting[i], posting[j]
                candidates.add((a, b) if a < b else (b, a))

    pairs: list[DuplicatePair] = []
    for id_a, id_b in sorted(candidates):
        s_a = shingles_by_id[id_a]
        s_b = shingles_by_id[id_b]
        union_len = len(s_a | s_b)
        sim = (len(s_a & s_b) / union_len) if union_len > 0 else 0.0
        if sim >= threshold:
            pairs.append(
                DuplicatePair(
                    passage_id=id_b,
                    matched_passage_id=id_a,
                    kind="near",
                    similarity=round(sim, 4),
                )
            )
    return pairs

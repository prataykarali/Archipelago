"""Deterministic page-aware chunking preserving exact page_start and page_end."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .constants import (
    MAX_CHUNK_CHARS,
    MIN_CHUNK_CHARS,
    PARAGRAPH_JOIN_SEPARATOR,
    TARGET_CHUNK_CHARS,
)
from .models import PageText

MD_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class RawChunk:
    """Intermediate chunk with exact 1-based page provenance and heading."""

    chunk_index: int
    page_start: int
    page_end: int
    section_heading: str
    text: str


@dataclass(frozen=True)
class _PageSegment:
    """Single atomic text segment tied to an exact 1-based page number."""

    page_number: int
    section_heading: str
    text: str


def _split_long_segment(
    text: str,
    max_chars: int,
) -> list[str]:
    """Split an oversized paragraph deterministically on sentence/word boundaries."""
    if len(text) <= max_chars:
        return [text]

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    pieces: list[str] = []
    current = ""
    for sent in sentences:
        if len(sent) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            words = sent.split()
            word_buf = ""
            for word in words:
                candidate = f"{word_buf} {word}".strip() if word_buf else word
                if len(candidate) <= max_chars:
                    word_buf = candidate
                else:
                    if word_buf:
                        pieces.append(word_buf)
                    word_buf = word[:max_chars]
            if word_buf:
                pieces.append(word_buf)
            continue

        candidate = f"{current} {sent}".strip() if current else sent
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = sent

    if current:
        pieces.append(current)
    return pieces


def _extract_segments_from_pages(
    pages: list[PageText],
    is_markdown: bool,
    max_chars: int,
) -> list[_PageSegment]:
    """Break pages into ordered atomic segments while tracking headings."""
    segments: list[_PageSegment] = []
    active_heading = ""

    for page in pages:
        if not page.cleaned_text:
            continue
        paragraphs = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(page.cleaned_text) if p.strip()]
        for para in paragraphs:
            if is_markdown:
                first_line = para.splitlines()[0].strip()
                heading_match = MD_HEADING_RE.match(first_line)
                if heading_match:
                    active_heading = heading_match.group(2).strip()
            for sub in _split_long_segment(para, max_chars=max_chars):
                segments.append(
                    _PageSegment(
                        page_number=page.page_number,
                        section_heading=active_heading,
                        text=sub,
                    )
                )
    return segments


def chunk_pages(
    pages: list[PageText],
    is_markdown: bool = False,
    target_chars: int = TARGET_CHUNK_CHARS,
    max_chars: int = MAX_CHUNK_CHARS,
    min_chars: int = MIN_CHUNK_CHARS,
) -> list[RawChunk]:
    """Chunk extracted pages deterministically with exact page_start/page_end."""
    segments = _extract_segments_from_pages(
        pages=pages,
        is_markdown=is_markdown,
        max_chars=max_chars,
    )
    if not segments:
        return []

    raw_chunks: list[RawChunk] = []
    buf_texts: list[str] = []
    buf_pages: list[int] = []
    buf_heading = segments[0].section_heading
    buf_len = 0

    def flush_buffer() -> None:
        nonlocal buf_texts, buf_pages, buf_len
        if not buf_texts:
            return
        combined = PARAGRAPH_JOIN_SEPARATOR.join(buf_texts).strip()
        if combined:
            raw_chunks.append(
                RawChunk(
                    chunk_index=len(raw_chunks),
                    page_start=min(buf_pages),
                    page_end=max(buf_pages),
                    section_heading=buf_heading,
                    text=combined,
                )
            )
        buf_texts = []
        buf_pages = []
        buf_len = 0

    for seg in segments:
        sep_len = len(PARAGRAPH_JOIN_SEPARATOR) if buf_texts else 0
        projected = buf_len + sep_len + len(seg.text)

        heading_changed = (
            is_markdown
            and bool(buf_texts)
            and bool(seg.section_heading)
            and seg.section_heading != buf_heading
            and buf_len >= min_chars
        )

        if buf_texts and (projected > max_chars or (buf_len >= target_chars) or heading_changed):
            flush_buffer()
            buf_heading = seg.section_heading

        if not buf_texts:
            buf_heading = seg.section_heading
        buf_texts.append(seg.text)
        buf_pages.append(seg.page_number)
        buf_len = sum(len(t) for t in buf_texts) + len(PARAGRAPH_JOIN_SEPARATOR) * (
            len(buf_texts) - 1
        )

    flush_buffer()

    if len(raw_chunks) > 1 and len(raw_chunks[-1].text) < min_chars:
        prev = raw_chunks[-2]
        tail = raw_chunks[-1]
        merged_text = f"{prev.text}{PARAGRAPH_JOIN_SEPARATOR}{tail.text}"
        if len(merged_text) <= max_chars:
            raw_chunks[-2] = RawChunk(
                chunk_index=prev.chunk_index,
                page_start=min(prev.page_start, tail.page_start),
                page_end=max(prev.page_end, tail.page_end),
                section_heading=prev.section_heading,
                text=merged_text,
            )
            raw_chunks.pop()

    return [
        RawChunk(
            chunk_index=idx,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_heading=chunk.section_heading,
            text=chunk.text,
        )
        for idx, chunk in enumerate(raw_chunks)
    ]

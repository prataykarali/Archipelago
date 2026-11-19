"""Extraction quality and truncation/malformation inspector for Corpus v3."""

from __future__ import annotations

import re

from .constants import (
    FLAG_BROKEN_ENCODING,
    FLAG_EMPTY_OR_TOO_SHORT,
    FLAG_HEADER_FOOTER_ONLY,
    FLAG_MATH_EXTRACTION_NOISE,
    FLAG_TOC_OR_INDEX_LIKE,
    FLAG_TRUNCATED_END,
    FLAG_TRUNCATED_START,
    HEADER_FOOTER_MAX_CHARS,
    MAX_CONTROL_CHAR_RATIO,
    MAX_SHORT_LINE_RATIO,
    MAX_SINGLE_CHAR_TOKEN_RATIO,
    MIN_LINES_FOR_HEADER_CHECK,
    MIN_PROSE_WORDS_PER_SENTENCE,
    MIN_TOKENS_FOR_MATH_NOISE_CHECK,
    MIN_USABLE_CHARS,
    MIN_USABLE_TOKENS,
    QUALITY_MIN_USABLE_SCORE,
    QUALITY_PENALTY_MINOR,
    QUALITY_PENALTY_MODERATE,
    QUALITY_PENALTY_SEVERE,
    SEVERE_QUALITY_FLAGS,
    SHORT_LINE_MAX_CHARS,
    TOC_DOT_LEADER_MIN_COUNT,
    TOC_MIN_LINES,
    TOC_NUMERIC_LINE_MIN_RATIO,
)
from .models import QualityAssessment

TOKEN_RE = re.compile(r"\S+")
ALPHA_WORD_RE = re.compile(r"[A-Za-z]{2,}")
SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")
CID_RE = re.compile(r"\(cid:\d+\)")
DOT_LEADER_RE = re.compile(r"\.{4,}")
NUMERIC_LINE_RE = re.compile(r"^[\d\s.\-ivxlcdmIVXLCDM]+$")
VALID_END_CHARS: frozenset[str] = frozenset({".", "?", "!", ":", ";", ")", "]", '"', "'", "$", "`"})
CONTROL_ORD_UPPER = 32
ALLOWED_WHITESPACE_ORDS: frozenset[int] = frozenset({9, 10, 13})
FULL_QUALITY_SCORE = 1.0


def count_tokens(text: str) -> int:
    """Count whitespace-delimited tokens deterministically."""
    return len(TOKEN_RE.findall(text))


def _has_prose_sentence(text: str) -> bool:
    """Return True if text contains at least one multi-word prose sentence."""
    if not SENTENCE_END_RE.search(text):
        return False
    for fragment in SENTENCE_END_RE.split(text):
        if len(ALPHA_WORD_RE.findall(fragment)) >= MIN_PROSE_WORDS_PER_SENTENCE:
            return True
    return False


def _has_control_char_corruption(text: str) -> bool:
    """Return True if non-whitespace control characters exceed threshold."""
    if not text:
        return False
    bad = sum(
        1 for ch in text if ord(ch) < CONTROL_ORD_UPPER and ord(ch) not in ALLOWED_WHITESPACE_ORDS
    )
    return (bad / len(text)) > MAX_CONTROL_CHAR_RATIO


def _is_header_footer_only(text: str, lines: list[str]) -> bool:
    """Detect short running-header/footer fragments lacking prose sentences."""
    non_empty = [line.strip() for line in lines if line.strip()]
    if len(non_empty) < MIN_LINES_FOR_HEADER_CHECK:
        return False
    short_or_numeric = sum(
        1
        for line in non_empty
        if len(line) <= SHORT_LINE_MAX_CHARS or bool(NUMERIC_LINE_RE.match(line))
    )
    if (short_or_numeric / len(non_empty)) < MAX_SHORT_LINE_RATIO:
        return False
    return (len(text) <= HEADER_FOOTER_MAX_CHARS) or (not _has_prose_sentence(text))


def _is_toc_or_index_like(text: str, lines: list[str]) -> bool:
    """Detect table-of-contents or index pages via dot-leaders or page-number columns."""
    if len(DOT_LEADER_RE.findall(text)) >= TOC_DOT_LEADER_MIN_COUNT:
        return True
    non_empty = [line.strip() for line in lines if line.strip()]
    if len(non_empty) < TOC_MIN_LINES or _has_prose_sentence(text):
        return False
    numeric_lines = sum(1 for line in non_empty if bool(NUMERIC_LINE_RE.match(line)))
    return (numeric_lines / len(non_empty)) >= TOC_NUMERIC_LINE_MIN_RATIO


def _has_math_extraction_noise(tokens: list[str]) -> bool:
    """Detect heavy single-character fragmentation typical of broken PDF math."""
    if len(tokens) < MIN_TOKENS_FOR_MATH_NOISE_CHECK:
        return False
    single_char = sum(1 for tok in tokens if len(tok) == 1 and tok not in {"a", "I"})
    return (single_char / len(tokens)) >= MAX_SINGLE_CHAR_TOKEN_RATIO


def _has_mid_sentence_start(text: str) -> bool:
    """Return True if passage appears to start mid-sentence with a lowercase word."""
    stripped = text.lstrip()
    if not stripped:
        return False
    first = stripped[0]
    return first.islower()


def _has_mid_sentence_end(text: str) -> bool:
    """Return True if passage ends without terminal punctuation."""
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped[-1] not in VALID_END_CHARS


def assess_passage_quality(text: str) -> QualityAssessment:
    """Inspect a passage for truncation, encoding damage, and structural noise."""
    flags: list[str] = []
    score = FULL_QUALITY_SCORE

    stripped = text.strip()
    tokens = TOKEN_RE.findall(stripped)
    lines = stripped.splitlines()

    if len(stripped) < MIN_USABLE_CHARS or len(tokens) < MIN_USABLE_TOKENS:
        flags.append(FLAG_EMPTY_OR_TOO_SHORT)
        score -= QUALITY_PENALTY_SEVERE

    if (
        "\ufffd" in stripped
        or bool(CID_RE.search(stripped))
        or _has_control_char_corruption(stripped)
    ):
        flags.append(FLAG_BROKEN_ENCODING)
        score -= QUALITY_PENALTY_SEVERE

    if _is_header_footer_only(stripped, lines):
        flags.append(FLAG_HEADER_FOOTER_ONLY)
        score -= QUALITY_PENALTY_SEVERE

    if _is_toc_or_index_like(stripped, lines):
        flags.append(FLAG_TOC_OR_INDEX_LIKE)
        score -= QUALITY_PENALTY_MODERATE

    if _has_math_extraction_noise(tokens):
        flags.append(FLAG_MATH_EXTRACTION_NOISE)
        score -= QUALITY_PENALTY_MODERATE

    if stripped and _has_mid_sentence_start(stripped):
        flags.append(FLAG_TRUNCATED_START)
        score -= QUALITY_PENALTY_MINOR

    if stripped and _has_mid_sentence_end(stripped):
        flags.append(FLAG_TRUNCATED_END)
        score -= QUALITY_PENALTY_MINOR

    bounded_score = round(max(0.0, min(FULL_QUALITY_SCORE, score)), 4)
    has_severe = any(flag in SEVERE_QUALITY_FLAGS for flag in flags)
    is_usable = (not has_severe) and (bounded_score >= QUALITY_MIN_USABLE_SCORE)

    return QualityAssessment(
        flags=tuple(flags),
        quality_score=bounded_score,
        is_usable=is_usable,
    )

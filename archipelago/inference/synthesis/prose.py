"""Auto-split from synthesis.py — do not edit blocks by hand."""
from __future__ import annotations

import re


def _strip_latex(text):
    """Remove LaTeX/math notation from text and replace with plain description."""
    text = re.sub(r'\$([^$]*)\$', r'\1', text)
    text = re.sub(r'\$([^$]*)\$', r'\1', text)
    text = re.sub(r'\\\(([^)]*)\\\)', r'\1', text)
    text = re.sub(r'\\\[([^\]]*)\\\]', r'\1', text)
    text = re.sub(r'\\begin\{[^}]*\}([\\\\s\\S]*?)\\end\{[^}]*\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\\\([a-zA-Z]+)', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U00002600-\U000026FF"
    "]+",
    re.UNICODE,
)


_SLANG_LEAK_RE = re.compile(
    r"\b(?:"
    r"no\s+cap|fr\s+fr|lowkey|highkey|bussin|rizz|skibidi|gyatt|"
    r"bet\b|sus\b|vibe\s+check|it's\s+giving|ate\s+and\s+left|"
    r"slay|yeet|bruh|lit\b|fam\b|ong\b|iykyk|ngl\b|tbh\b|"
    r"bestie|periodt|sheesh|fire\s+emoji"
    r")\b",
    re.I,
)


def enforce_sterile_prose(text: str, fallback: str = "") -> str:
    """Hard persona lock: strip emojis/slang; fall back if still contaminated."""
    if not text:
        return fallback or text
    cleaned = _EMOJI_RE.sub("", text)
    cleaned = _SLANG_LEAK_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    # If model still leaked slang/emojis after strip, or emptied the reply
    if _EMOJI_RE.search(cleaned) or _SLANG_LEAK_RE.search(cleaned) or not cleaned:
        return (fallback or cleaned).strip()
    # Reject "general knowledge" hallucination phrase
    if re.search(
        r"based on general knowledge|outside the provided context|"
        r"as an ai language model|my (?:system )?(?:prompt|constraints?|token limits?)",
        cleaned,
        re.I,
    ):
        return (
            fallback
            or "This information is not detailed in the provided library texts."
        )
    return cleaned


def is_readable_synthesis(text: str) -> bool:
    """Detect if synthesized text contains unreadable/malformed SLM artifacts."""
    if not text or not isinstance(text, str):
        return False
    if "begincases" in text or "endcases" in text:
        return False
    if re.search(r"(?:[a-zA-Z]_[a-zA-Z0-9],?\s*){5,}", text):
        return False
    if re.search(r"(?:[a-z]',?){4,}", text):
        return False
    return True


def _scrub_slm_artifacts(text: str) -> str:
    """Scrub known SLM malformed math/artifacts without discarding surrounding clean text."""
    if not text:
        return ""
    cleaned = re.sub(r"begincases[\s\S]*?endcases", "", text)
    cleaned = re.sub(r"\\begin\{cases\}[\s\S]*?\\end\{cases\}", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

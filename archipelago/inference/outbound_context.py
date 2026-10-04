"""Minimal allowlisted academic evidence for local external synthesis."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

MAX_CONTEXT_CHARS = 6000
MAX_RECORDS = 8
MAX_SUMMARY_CHARS = 700
PRIVATE_LEVELS = frozenset({"private", "restricted", "confidential"})
SECRET_PATTERN = re.compile(
    r"(?im)\b(?:password|passwd|api[_ -]?key|secret|access[_ -]?token|"
    r"refresh[_ -]?token|authorization|student[_ -]?(?:id|email)|barcode)"
    r"\s*[:=]\s*[^\n,;]+"
)
TOKEN_PATTERN = re.compile(r"\b(?:sk-[\w-]{12,}|hf_[A-Za-z0-9]{12,}|eyJ[\w-]+\.[\w-]+\.[\w-]+)\b")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
URL_PATTERN = re.compile(r"https?://\S+")


def redact(value: str) -> str:
    """Redact credential-like literals and contacts from the bounded context."""
    value = SECRET_PATTERN.sub("[REDACTED]", value)
    value = TOKEN_PATTERN.sub("[REDACTED]", value)
    value = EMAIL_PATTERN.sub("[REDACTED]", value)
    return URL_PATTERN.sub("[LINK OMITTED]", value)


def minimal_context(records: Iterable[dict[str, Any]] | None, _notes: str = "") -> str:
    """Allow only retrieved public academic text, not arbitrary graph-note prose.

    When evidence is absent, use public concept summaries selected by the route.
    Raw notes may contain inventory or user data and are deliberately ignored.
    """
    lines: list[str] = []
    for record in records or []:
        if record.get("private") or record.get("allow_external_inference") is False:
            continue
        if str(record.get("visibility", "public")).lower() in PRIVATE_LEVELS:
            continue
        text = str(
            record.get("text_span") or record.get("text") or record.get("summary") or ""
        ).strip()
        if text:
            evidence = str(record.get("evidence_id") or "")
            topic = str(record.get("topic") or "")[:MAX_SUMMARY_CHARS]
            lines.append(redact(f"{evidence} {topic}: {text[:MAX_SUMMARY_CHARS]}"))
        if len(lines) >= MAX_RECORDS:
            break
    return "\n".join(lines)[:MAX_CONTEXT_CHARS]

"""Bounded academic context for external inference, never inventory or student history."""
from __future__ import annotations

import re

from .nodes import node_public

MAX_CONTEXT_CHARS = 6000
MAX_CONTEXT_NODES = 8
SECRET_ASSIGNMENT = re.compile(
    r"(?im)\b(?:password|passwd|api[_ -]?key|secret|access[_ -]?token|"
    r"refresh[_ -]?token|authorization|student[_ -]?(?:id|email)|barcode)"
    r"\s*[:=]\s*[^\n,;]+"
)
TOKEN_PATTERN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9]{12,}|eyJ[\w-]+\.[\w-]+\.[\w-]+)\b")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
LINK_PATTERN = re.compile(r"https?://\S+")
PRIVATE_LEVELS = frozenset({"private", "restricted", "confidential"})


def safe_text(text: str) -> str:
    """Redact credential-like strings and contact details; cap outbound context."""
    value = SECRET_ASSIGNMENT.sub("[REDACTED]", text)
    value = TOKEN_PATTERN.sub("[REDACTED]", value)
    value = EMAIL_PATTERN.sub("[REDACTED]", value)
    value = LINK_PATTERN.sub("[LINK OMITTED]", value)
    return value[:MAX_CONTEXT_CHARS]


def inference_context(graph, payload: dict) -> str:
    """Allowlist only public retrieved concept summaries, excluding OPAC and learner data."""
    selected = [payload.get("anchor_concept"), *payload.get("prerequisites", []), *payload.get("unlocks", [])]
    records, seen = [], set()
    for entry in selected:
        if not isinstance(entry, dict) or entry.get("id") in seen:
            continue
        cid = entry.get("id")
        raw = graph.nodes.get(cid, {})
        if raw.get("private") or str(raw.get("visibility") or "public").lower() in PRIVATE_LEVELS:
            continue
        if raw.get("allow_external_inference") is False:
            continue
        seen.add(cid)
        record = node_public(raw)
        if record["summary"]:
            records.append(f"{record['label']}: {record['summary']}")
        if len(records) >= MAX_CONTEXT_NODES:
            break
    return safe_text("\n".join(records))

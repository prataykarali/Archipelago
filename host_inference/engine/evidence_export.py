"""Per-query structured evidence export helper with strict credential scrubbing.

One concern: assemble a self-contained JSON or Markdown evidence bundle
(answer, clean citations, 6-state evidence contract, canonical passage IDs,
physical-vs-printed page provenance, typed graph edges, and execution trace)
while strictly stripping any credentials, bearer tokens, API keys, session
cookies, or private auth headers.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from .access_profile import active_access_profile, filter_open_access_citations
from .citation_format import sanitize_citations
from .provenance import (
    EVIDENCE_STATE_LABELS,
    format_canonical_title,
    resolve_page_provenance,
    summarize_evidence_states,
)

EXPORT_SCHEMA_VERSION = "archipelago.evidence_export.v1"
REDACTED_MARKER = "[REDACTED]"
MAX_EXPORT_EDGES = 40

_SENSITIVE_KEY_TOKENS = (
    "authorization",
    "cookie",
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "csrf",
    "bearer",
    "private_key",
    "session_id",
    "supabase_key",
    "service_role",
    "credential",
)

_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}\b"),
    re.compile(r"\bgsk_[A-Za-z0-9_\-]{12,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b"),
    re.compile(r"(?i)\b(?:archipelago_token|archipelago_csrf|sessionid)=[^;\s]+"),
    re.compile(r"(?i)\b(?:cookie|set-cookie|authorization)\s*:\s*[^\r\n]+"),
)

_ALLOWED_CITATION_FIELDS = (
    "evidence_id",
    "label",
    "doc_id",
    "doc_title",
    "authors",
    "page_number",
    "pdf_page",
    "printed_page",
    "page_offset",
    "page_display",
    "pages_differ",
    "ostep_chapter_number",
    "ostep_local_file_number",
    "section",
    "chunk_id",
    "canonical_passage_id",
    "evidence_state",
    "evidence_state_label",
    "source_kind",
    "follow_up_eligible",
    "provenance_status",
    "claim_support_status",
    "verification_status",
    "source_category",
    "source_type",
    "access_status",
    "url",
    "bibliographic_url",
    "text_passage",
    "withdrawn",
)


def _is_sensitive_key(key: str) -> bool:
    low = key.strip().lower()
    return any(tok in low for tok in _SENSITIVE_KEY_TOKENS)


def scrub_sensitive_text(value: str) -> str:
    """Redact any embedded tokens, JWTs, API keys, or cookie values from ``value``."""
    cleaned = value
    for pat in _SECRET_VALUE_PATTERNS:
        cleaned = pat.sub(REDACTED_MARKER, cleaned)
    return cleaned


def scrub_sensitive_object(obj: Any) -> Any:
    """Recursively remove sensitive keys and scrub secret patterns from any object."""
    if isinstance(obj, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, val in obj.items():
            key = str(raw_key)
            if _is_sensitive_key(key):
                continue
            sanitized[key] = scrub_sensitive_object(val)
        return sanitized
    if isinstance(obj, list):
        return [scrub_sensitive_object(item) for item in obj]
    if isinstance(obj, tuple):
        return [scrub_sensitive_object(item) for item in obj]
    if isinstance(obj, str):
        return scrub_sensitive_text(obj)
    return obj


def _extract_graph_edges(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive typed graph edges from the finalized chat payload without inventing links."""
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(src: str, dst: str, relation: str, review_status: str = "unreviewed") -> None:
        if not src or not dst or src == dst:
            return
        key = (src, dst, relation)
        if key in seen or len(edges) >= MAX_EXPORT_EDGES:
            return
        seen.add(key)
        edges.append(
            {
                "from": src,
                "to": dst,
                "relation": relation,
                "review_status": review_status,
            }
        )

    anchor = payload.get("anchor_concept")
    anchor_id = str(anchor.get("id") or "").strip() if isinstance(anchor, dict) else ""
    if anchor_id:
        for pre in payload.get("prerequisites") or []:
            if isinstance(pre, dict) and pre.get("id"):
                _add(anchor_id, str(pre["id"]), "REQUIRES")
        for unl in payload.get("unlocks") or []:
            if isinstance(unl, dict) and unl.get("id"):
                _add(anchor_id, str(unl["id"]), "UNLOCKS")
        for rel in payload.get("related_concepts") or []:
            if isinstance(rel, dict) and rel.get("id"):
                _add(anchor_id, str(rel["id"]), "RELATED")

    research_graph = payload.get("research_graph")
    if isinstance(research_graph, dict):
        for edge in research_graph.get("edges") or []:
            if isinstance(edge, dict):
                _add(
                    str(edge.get("from") or ""),
                    str(edge.get("to") or ""),
                    str(edge.get("relation") or "RELATED"),
                    str(edge.get("review_status") or "unreviewed"),
                )
    return edges


def _normalize_citations(raw_citations: Any) -> list[dict[str, Any]]:
    """Project citations onto safe public fields with clean titles and 6-state contract."""
    if not isinstance(raw_citations, list):
        return []
    filtered = filter_open_access_citations([c for c in raw_citations if isinstance(c, dict)])
    sanitized = sanitize_citations(filtered)
    cleaned: list[dict[str, Any]] = []
    for cite in sanitized:
        record = {k: cite.get(k) for k in _ALLOWED_CITATION_FIELDS if k in cite}
        doc_id = str(cite.get("doc_id") or "")
        raw_title = str(cite.get("doc_title") or cite.get("title") or "")
        record["doc_title"] = format_canonical_title(doc_id, raw_title)
        prov = resolve_page_provenance(doc_id, cite.get("page_number"), cite.get("printed_page"))
        record["pdf_page"] = prov["pdf_page"]
        record["printed_page"] = prov["printed_page"]
        record["page_display"] = prov["page_display"]
        record["pages_differ"] = prov["pages_differ"]
        cleaned.append(scrub_sensitive_object(record))
    return cleaned


def build_evidence_export(
    query: str,
    answer: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a credential-free structured evidence export bundle for one query."""
    meta = payload if isinstance(payload, dict) else {}
    citations = _normalize_citations(meta.get("citations"))
    evidence_summary = summarize_evidence_states(citations)

    trace_raw = meta.get("trace") if isinstance(meta.get("trace"), dict) else {}
    trace = scrub_sensitive_object(trace_raw)
    if isinstance(trace, dict):
        trace["evidence_state"] = evidence_summary["turn_evidence_state"]
        trace["evidence_state_label"] = evidence_summary["turn_evidence_state_label"]
        trace["evidence_backed"] = evidence_summary["evidence_backed"]

    cited_ids = {
        str(c.get("canonical_passage_id") or c.get("chunk_id"))
        for c in citations
        if c.get("canonical_passage_id") or c.get("chunk_id")
    }
    for pid in trace.get("passage_ids") or []:
        if pid:
            cited_ids.add(str(pid))
    for pid in trace.get("retrieved_passage_ids") or []:
        if pid:
            cited_ids.add(str(pid))
    passage_ids = sorted(cited_ids)

    anchor_raw = meta.get("anchor_concept")
    anchor_public = (
        scrub_sensitive_object(
            {
                "id": anchor_raw.get("id"),
                "label": anchor_raw.get("label") or anchor_raw.get("name"),
                "summary": anchor_raw.get("summary") or "",
            }
        )
        if isinstance(anchor_raw, dict) and anchor_raw.get("id")
        else None
    )

    routing = meta.get("routing") if isinstance(meta.get("routing"), dict) else {}
    route = str(routing.get("route") or meta.get("route") or trace.get("intent") or "unknown")
    contract = str(meta.get("contract") or "")

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "access_profile": active_access_profile(),
        "query": scrub_sensitive_text(str(query or "").strip()),
        "answer": scrub_sensitive_text(str(answer or "").strip()),
        "route": route,
        "contract": contract,
        "evidence_summary": evidence_summary,
        "anchor_concept": anchor_public,
        "citations": citations,
        "passage_ids": passage_ids,
        "graph_edges": _extract_graph_edges(meta),
        "trace": trace,
    }


def render_evidence_markdown(bundle: dict[str, Any]) -> str:
    """Render a structured evidence bundle as readable Markdown."""
    ev_summary = bundle.get("evidence_summary") or {}
    turn_state = str(ev_summary.get("turn_evidence_state") or "UNAVAILABLE_DOCUMENT")
    turn_label = EVIDENCE_STATE_LABELS.get(turn_state, turn_state)
    lines: list[str] = [
        "# Archipelago Evidence Export",
        "",
        f"- **Exported at:** {bundle.get('exported_at', '')}",
        f"- **Access profile:** `{bundle.get('access_profile', 'institutional')}`",
        f"- **Route:** `{bundle.get('route', 'unknown')}`",
        f"- **Evidence state:** `{turn_state}` ({turn_label})",
        "",
        "## Query",
        "",
        str(bundle.get("query") or ""),
        "",
        "## Answer",
        "",
        str(bundle.get("answer") or ""),
        "",
        "## Citations",
        "",
    ]
    citations = bundle.get("citations") or []
    if citations:
        for cite in citations:
            title = cite.get("doc_title") or cite.get("doc_id") or "Source"
            page_disp = cite.get("page_display") or (
                f"PDF p. {cite['page_number']}" if cite.get("page_number") else ""
            )
            page_str = f", {page_disp}" if page_disp else ""
            pid = cite.get("canonical_passage_id") or cite.get("chunk_id") or "unmatched"
            ev_state = cite.get("evidence_state") or "UNAVAILABLE_DOCUMENT"
            status = cite.get("provenance_status") or "unknown"
            lines.append(
                f"- **{title}**{page_str} — state `{ev_state}` · passage `{pid}` ({status})"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Graph Edges", ""])
    edges = bundle.get("graph_edges") or []
    if edges:
        for edge in edges:
            lines.append(
                f"- `{edge.get('from')}` —[{edge.get('relation')}]→ `{edge.get('to')}` "
                f"({edge.get('review_status', 'unreviewed')})"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "REDACTED_MARKER",
    "build_evidence_export",
    "render_evidence_markdown",
    "scrub_sensitive_object",
    "scrub_sensitive_text",
]

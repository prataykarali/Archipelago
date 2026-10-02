"""Contract handlers for the library chat route's non-graph intents.

Split out of :mod:`archipelago.api.routes_chat` so the route file stays a thin
pipeline and each contract's answer lives where it can be read and tested alone.

The shared thread through all six: answer the question that was *asked*.  A
combined hours-plus-access sentence used to be handed to the credential formatter
alone, which returned a portal card and silently dropped the schedule — the one
half of the answer the student could not look up anywhere else.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from archipelago.core.contract import (
    contract_for,
    graph_decision,
)
from archipelago.core.router import OUT_OF_SCOPE_MESSAGE

logger = logging.getLogger("archipelago.api.contracts")

#: Canned refusal for code-generation and other non-academic requests.
CODE_MESSAGE = (
    "Archipelago is a theoretical architecture, mathematics and institutional "
    "library assistant. It does not generate code, installation guides, or "
    "implementation scripts — I would be guessing at an answer I cannot cite. "
    "I can instead ground you in the theory behind the concept, the textbook "
    "chapters that teach it, and where to find those chapters on campus."
)

#: Code-generation cues, kept in sync with the router's guardrail patterns.
CODE_REQUEST_RE = re.compile(
    r"\b(?:write|create|generate|give|show)\s+(?:me\s+)?(?:a\s+|an\s+)?"
    r"(?:\w+\s+){0,3}?(?:python|java|c\+\+|c#|javascript|js|typescript|ts|sql|"
    r"bash|shell|go|rust|ruby|php|scala|kotlin|react)\b"
    r"|\b(?:python|java|javascript|node)\s+(?:web\s+)?(?:scraper|crawler|bot|spider)\b"
    r"|\bwrite\s+(?:me\s+)?(?:the\s+|a\s+|an\s+)?\w+\s+script\s+to\b"
    r"|\b(?:pip\s+install|npm\s+install|yarn\s+add|dockerfile|docker\s+compose|apt-get\s+install)\b",
    re.I,
)

#: How many recent ingestion jobs the contract-5 answer reports on.
INGESTION_JOB_SCAN = 8

#: Settled job states — anything still in flight has nothing to report yet.
SETTLED_STATUSES = frozenset({"COMPLETE", "FAILED", "CANCELLED"})

OPAC_URL = "http://uemk-opac.l2c2.co.in"

INGESTION_INTRO = (
    "**Uploaded-paper analysis.** Extraction is asynchronous, so I can only "
    "report what the OKF pipeline has already committed to the graph."
)

#: Contract statuses, resolved once at import so the handlers never repeat the
#: reverse lookup and cannot drift from the contract table.
CATALOG_CONTRACT = contract_for("catalog_shelf_routing")
AUTH_CONTRACT = contract_for("auth_gateway")
INGESTION_CONTRACT = contract_for("ingestion_analysis")
GUARDRAIL_CONTRACT = contract_for("guardrail_intercept")


def _schedule_text(query: str) -> str:
    """Static operating-hours answer for ``query``, or ``""`` when not asked."""
    from archipelago.inference.library_schedules import (
        detect_library_hours_query,
        format_schedule_for_response,
        get_library_hours,
    )

    detected = detect_library_hours_query(query)
    if detected is None:
        return ""
    return format_schedule_for_response(get_library_hours(detected.get("day") or None))


def _access_text(query: str) -> str:
    """Institutional access answer, or ``""`` when no credential help is asked."""
    from archipelago.inference.eresource_credentials import format_credential_reply

    return format_credential_reply(query) or ""


def auth_gateway_text(query: str) -> str:
    """Contract type 3: hours and e-resource access, each only if asked for.

    Both halves are rendered when both are requested.  The OPAC link closes every
    reply so a student asking either question has a concrete next step.
    """
    hours = _schedule_text(query)
    access = _access_text(query)
    parts: list[str] = []
    if hours and access:
        parts.append("Both halves of that question are answered below.")
    parts.extend(part for part in (hours, access) if part)
    if not parts:
        parts.append(
            "Institutional e-resources (NDLI, IEEE Xplore, Scopus, ScienceDirect) are "
            "accessible through the Central Library Portal with your institutional SSO "
            "credentials. The assistant never displays or stores passwords."
        )
    parts.append(f"**OPAC.** {OPAC_URL}")
    return "\n\n".join(parts)


def _materials_text(query: str) -> str:
    """Lab-manual / reprography locations, or ``""`` when not asked."""
    ql = query.lower()
    if not any(term in ql for term in ("lab manual", "xerox", "reprography", "muskan")):
        return ""
    return (
        "### Lab Manuals & Reprography\n"
        "- Location: **B1 LG2.7 (Muskan Xerox)**.\n"
        "- Central Library provides physical copies for reference; photocopies and "
        "lab manual reprints are available at the reprography center in B1 LG2.7."
    )


def catalog_shelf_text(query: str) -> str:
    """Contract type 2: lab-manual locations, subject holdings, and the OPAC."""
    lines: list[str] = []
    materials = _materials_text(query)
    if materials:
        lines += [materials, ""]
    try:
        from archipelago.inference.catalog_ops import subject_title_counts

        counts = subject_title_counts(limit=10)
    except Exception as exc:
        logger.warning("Subject holdings unavailable: %s", exc)
        counts = []
    if counts:
        lines += ["### Institutional Library Holdings", ""]
        lines += [
            f"- **{row.get('subject')}**: {row.get('title_count')} titles on the stacks"
            for row in counts
        ]
    else:
        lines.append(
            "The subject-wise holdings index is unavailable right now. "
            f"Search the OPAC at {OPAC_URL}, or ask at the circulation desk."
        )
    lines += [
        "",
        "Borrowing from the Central Library remains the primary route; digital "
        "access does not replace the physical collection.",
    ]
    return "\n".join(lines)


def ingestion_text() -> str:
    """Contract type 5: grounded status of the most recent ingestion jobs."""
    try:
        from ingestion_worker import job_store

        jobs = job_store.list_jobs()
    except Exception as exc:
        logger.warning("Ingestion job store unavailable: %s", exc)
        return (
            f"{INGESTION_INTRO}\n\nThe ingestion job store is unavailable, so I "
            "cannot report on any upload. Ask the librarian to check the "
            "ingestion worker."
        )

    settled = [
        job
        for job in jobs
        if isinstance(job, dict) and str(job.get("status")) in SETTLED_STATUSES
    ][:INGESTION_JOB_SCAN]

    if not settled:
        return (
            f"{INGESTION_INTRO}\n\nNo upload has reached a settled state yet, so "
            "there are no OKF nodes to project. Upload the PDF on the librarian "
            "ingest page and ask me again once extraction finishes."
        )

    lines = [INGESTION_INTRO, ""]
    for job in settled:
        source = job.get("source_filename") or "uploaded document"
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        nodes = result.get("new_node_ids") or []
        pages = result.get("source_pages") or []
        lines.append(f"- **{source}** — `{job.get('status')}`, {len(nodes)} OKF node(s)")
        if pages:
            lines.append(f"  - Extracted pages: {', '.join(str(p) for p in list(pages)[:8])}")
        if job.get("error"):
            lines.append(f"  - Error: {job['error']}")
    lines += [
        "",
        "Ask me about any of these concept names to open a grounded path with page citations.",
    ]
    return "\n".join(lines)


def guardrail_text(query: str) -> str:
    """Contract type 6: the right deflection for *why* the query was refused."""
    return CODE_MESSAGE if CODE_REQUEST_RE.search(query) else OUT_OF_SCOPE_MESSAGE


def direct_intent_reply(intent: str, norm_q: str) -> dict[str, Any] | None:
    """Answer a non-graph contract intent. ``None`` when the pipeline continues.

    The payload always carries ``contract`` and ``render_graph``, so the chat UI's
    graph-drawing behaviour is decided by the contract and never by which branch
    of the route happened to run.
    """
    handlers = {
        CATALOG_CONTRACT: catalog_shelf_text,
        AUTH_CONTRACT: auth_gateway_text,
        INGESTION_CONTRACT: ingestion_text,
        GUARDRAIL_CONTRACT: guardrail_text,
    }
    handler = handlers.get(intent)
    if handler is None:
        return None
    text = handler(norm_q) if handler is not ingestion_text else handler()
    return _payload(intent, text)


def _payload(intent: str, text: str) -> dict[str, Any]:
    """A contract-tagged, graph-free chat payload."""
    decision = graph_decision(intent)
    return {
        "status": "success",
        "intent": intent,
        "contract": intent,
        "render_graph": decision.render,
        "render_rule": decision.rule,
        "text": text,
        "citations": [],
        "topology": None,
    }


__all__ = [
    "AUTH_CONTRACT",
    "CATALOG_CONTRACT",
    "CODE_MESSAGE",
    "GUARDRAIL_CONTRACT",
    "INGESTION_CONTRACT",
    "INGESTION_INTRO",
    "OPAC_URL",
    "auth_gateway_text",
    "catalog_shelf_text",
    "direct_intent_reply",
    "guardrail_text",
    "ingestion_text",
]

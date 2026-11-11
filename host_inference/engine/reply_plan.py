"""Choose evidence-backed reply modules without changing chat stream framing."""

from __future__ import annotations

import re
from typing import Any

from .reply_templates import select_reply_template

DEEP_REQUEST = re.compile(
    r"\b(in depth|detailed|deep dive|literature review|research gaps?|compare|benchmark|derive|prove)\b",
    re.I,
)
SHORT_REQUEST = re.compile(r"^(what is|define|who is|when was|give me a short|briefly)\b", re.I)
RESOURCE_REQUEST = re.compile(
    r"\b(books?|textbooks?|library|reading|where (can|do) i (find|study|read))\b", re.I
)
PATH_REQUEST = re.compile(
    r"\b(prerequisites?|learning path|roadmap|what should i learn|connect|related)\b", re.I
)
RESEARCH_REQUEST = re.compile(
    r"\b(papers?|studies|research|evidence|literature|findings|limitations?)\b", re.I
)
MAX_SECONDARY_TEMPLATES = 3
SECONDARY_LAYOUT_CHARS = 350


def build_reply_plan(
    query: str, route: str, payload: dict[str, Any], template_id: str = ""
) -> dict[str, Any]:
    """Select primary and complementary formats from actual response evidence."""
    primary = select_reply_template(query, route, template_id)
    citations = [
        item
        for item in payload.get("citations", [])
        if isinstance(item, dict) and item.get("doc_id") and not item.get("withdrawn")
    ]
    exact_pages = [
        item
        for item in citations
        if isinstance(item.get("page_number"), int) and item["page_number"] > 0
    ]
    physical = [item for item in citations if item.get("koha_record_verified")]
    research = payload.get("research_sources") or []
    digital = payload.get("digital_resources") or []
    graph_path = bool(payload.get("anchor_concept")) and bool(
        payload.get("prerequisites") or payload.get("unlocks")
    )

    secondary_ids: list[str] = []

    def add(template: str) -> None:
        if template != primary["id"] and template not in secondary_ids:
            secondary_ids.append(template)

    if exact_pages and ("page" in query.casefold() or "cite" in query.casefold()):
        add("RES-062")
    if research and RESEARCH_REQUEST.search(query):
        add("RES-061")
    if graph_path and PATH_REQUEST.search(query):
        add("RES-121")
    if digital and RESOURCE_REQUEST.search(query):
        add("RES-125")
    if physical and RESOURCE_REQUEST.search(query):
        add("RES-124")
    if route == "DISCONNECTED":
        add("RES-130")
    if research and re.search(r"\b(limitations?|weaknesses|reliable|trustworthy)\b", query, re.I):
        add("RES-069")

    if DEEP_REQUEST.search(query):
        depth = "deep"
    elif SHORT_REQUEST.search(query):
        depth = "brief"
    else:
        depth = "normal"

    evidence: list[str] = []
    if citations:
        evidence.append(f"{len(citations)} indexed document source(s)")
    if exact_pages:
        evidence.append(f"{len(exact_pages)} verified PDF page reference(s)")
    if research:
        evidence.append(f"{len(research)} saved research source(s)")
    if digital:
        evidence.append(f"{len(digital)} licensed digital resource(s)")
    if physical:
        evidence.append(f"{len(physical)} imported holdings record(s)")
    if graph_path:
        evidence.append("indexed concept relationships")

    blocks = ["direct_answer"]
    if depth != "brief":
        blocks.append("explanation")
    if citations:
        blocks.append("sources")
    if research and RESEARCH_REQUEST.search(query):
        blocks.append("research")
    if graph_path and PATH_REQUEST.search(query):
        blocks.append("learning_path")
    if digital and RESOURCE_REQUEST.search(query):
        blocks.append("digital_resources")
    if physical and RESOURCE_REQUEST.search(query):
        blocks.append("physical_holdings")
    return {
        "primary_template": {"id": primary["id"], "name": primary["name"]},
        "secondary_templates": secondary_ids[:MAX_SECONDARY_TEMPLATES],
        "depth": depth,
        "evidence": evidence,
        "presentation": blocks,
    }


def plan_guidance(plan: dict[str, Any]) -> str:
    """Convert a validated plan to brief model guidance, without source claims."""
    secondary = [
        select_reply_template("", template_id=template_id)
        for template_id in plan["secondary_templates"]
    ]
    secondary_layouts = "\n".join(
        f"{item['id']} {item['name']}: {item['reply_template'][:SECONDARY_LAYOUT_CHARS]}"
        for item in secondary
    )
    return (
        f"Answer depth: {plan['depth']}. Start with a direct answer. "
        f"Use optional supporting layouts only when their evidence is present:\n"
        f"{secondary_layouts or 'none'}\n"
        f"Present useful parts in this order: {', '.join(plan['presentation'])}. "
        f"Available evidence classes: {', '.join(plan['evidence']) or 'none'}. "
        "A brief fact needs one short paragraph; a normal explanation needs a mechanism and example; "
        "a deep request may use sections or a comparison table. Never pad for length. "
        "Keep physical holdings separate from digital books and do not infer live availability."
    )

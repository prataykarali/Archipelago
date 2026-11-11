"""Select a grounded reply layout from the supplied research template registry."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re

REGISTRY_PATH = Path(__file__).with_name("reply_templates.json")
EXPECTED_TEMPLATE_COUNT = 130
MIN_TERM_LENGTH = 4
MAX_TEMPLATE_CHARS = 900
WORDS = re.compile(r"[a-z][a-z0-9-]*", re.I)
COMMON_WORDS = frozenset(
    {"answer", "asks", "paper", "papers", "research", "user", "wants", "with", "what", "which"}
)
ROUTE_TEMPLATES = {
    "RELATION": "RES-122",
    "CROSS_DOMAIN": "RES-122",
    "BOOK_PAGE": "RES-050",
    "CATALOG_SHELF_ROUTING": "RES-124",
    "library_holdings": "RES-124",
    "library_resources": "RES-125",
    "roadmap_between": "RES-121",
    "roadmap_quiz": "RES-123",
    "RESEARCH_EVIDENCE": "RES-061",
    "DISCONNECTED": "RES-130",
}
QUERY_TEMPLATES = (
    (
        re.compile(
            r"\b(how many papers? (?:were|did you) find|candidate papers?|source coverage)\b", re.I
        ),
        "RES-011",
    ),
    (
        re.compile(r"\b(who (?:authored|wrote)|paper metadata|identify (?:the )?paper)\b", re.I),
        "RES-031",
    ),
    (
        re.compile(r"\b(citation network|citation trail|papers? (?:citing|cited by))\b", re.I),
        "RES-081",
    ),
    (re.compile(r"\b(which experiments?|experimental setup|experiment ledger)\b", re.I), "RES-051"),
    (re.compile(r"\b(hypothesis|research proposal|experimental roadmap)\b", re.I), "RES-106"),
    (re.compile(r"\b(in depth|detailed explanation|deep technical)\b", re.I), "RES-112"),
    (
        re.compile(r"\b(research gaps?|open questions?|unexplored|future research)\b", re.I),
        "RES-100",
    ),
    (re.compile(r"\b(exact table|table cell|which table|reported in table)\b", re.I), "RES-063"),
    (re.compile(r"\b(equation|mathematical derivation|derive the formula)\b", re.I), "RES-046"),
    (re.compile(r"\b(architecture|components? of the model)\b", re.I), "RES-045"),
    (
        re.compile(r"\b(find|list|show|recommend)\b.*\b(papers?|studies|publications?)\b", re.I),
        "RES-021",
    ),
    (
        re.compile(
            r"\b(available copies|how many copies|call number|physical books?|shelf)\b", re.I
        ),
        "RES-124",
    ),
    (
        re.compile(r"\b(institutional access|e-?resources?|subscription|journal access)\b", re.I),
        "RES-125",
    ),
    (
        re.compile(
            r"\b(now|what about|its limitations|their limitations|continue|expand on that)\b", re.I
        ),
        "RES-119",
    ),
    (re.compile(r"\b(compare|versus|vs\.?|difference between)\b", re.I), "RES-091"),
    (re.compile(r"\b(latest|recent|new developments)\b", re.I), "RES-007"),
    (re.compile(r"\b(reproduc|replicat)\w*\b", re.I), "RES-071"),
    (re.compile(r"\b(citation|h-index|g-index|i10-index)\b", re.I), "RES-033"),
    (re.compile(r"\b(doi|authors?|venue|published)\b", re.I), "RES-031"),
    (re.compile(r"\b(benchmark|dataset|ablation|baseline)\b", re.I), "RES-052"),
    (re.compile(r"\b(literature review|related work)\b", re.I), "RES-092"),
    (re.compile(r"\b(how to learn|prerequisite|learning path)\b", re.I), "RES-121"),
    (re.compile(r"\b(quiz|test my knowledge)\b", re.I), "RES-123"),
    (re.compile(r"\b(where (can|do) i (find|get|access)|call number|shelf)\b", re.I), "RES-124"),
    (re.compile(r"\b(no source|missing pdf|unavailable full text)\b", re.I), "RES-127"),
    (re.compile(r"\b(explain|how does|how do|mechanism)\b", re.I), "RES-114"),
)


@lru_cache(maxsize=1)
def _registry() -> dict[str, dict[str, str]]:
    """Load and validate the complete, versioned template set."""
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    templates = raw["templates"]
    if len(templates) != EXPECTED_TEMPLATE_COUNT:
        raise ValueError("Reply template registry has an unexpected size")
    by_id = {item["id"]: item for item in templates}
    if len(by_id) != len(templates):
        raise ValueError("Reply template registry has duplicate IDs")
    return by_id


def list_reply_templates() -> list[dict[str, str]]:
    """Return safe metadata for the chat format picker."""
    return [
        {key: item[key] for key in ("id", "family", "name", "trigger")}
        for item in _registry().values()
    ]


def valid_reply_template_id(template_id: str) -> bool:
    """Check a client-selected ID against the packaged registry."""
    return template_id in _registry()


def select_reply_template(query: str, route: str = "", template_id: str = "") -> dict[str, str]:
    """Choose one layout using explicit intent cues, then lexical relevance."""
    templates = _registry()
    if template_id:
        return templates[template_id]
    for pattern, template_id in QUERY_TEMPLATES[:-1]:
        if pattern.search(query):
            return templates[template_id]
    if route in ROUTE_TEMPLATES:
        return templates[ROUTE_TEMPLATES[route]]
    if QUERY_TEMPLATES[-1][0].search(query):
        return templates[QUERY_TEMPLATES[-1][1]]
    terms = {
        word
        for word in WORDS.findall(query.casefold())
        if len(word) >= MIN_TERM_LENGTH and word not in COMMON_WORDS
    }
    if terms:
        ranked = sorted(
            templates.values(),
            key=lambda item: (
                len(terms & set(WORDS.findall(item["name"].casefold()))) * 2
                + len(terms & set(WORDS.findall(item["trigger"].casefold()))),
                item["id"],
            ),
            reverse=True,
        )
        candidate = ranked[0]
        if terms & set(WORDS.findall((candidate["name"] + " " + candidate["trigger"]).casefold())):
            return candidate
    return templates["RES-001"]


def reply_template_guidance(query: str, route: str = "", template_id: str = "") -> str:
    """Give the model a layout without granting template data higher authority."""
    template = select_reply_template(query, route, template_id)
    layout = template["reply_template"][:MAX_TEMPLATE_CHARS]
    return (
        f"Suggested reply layout ({template['id']}, {template['name']}): {layout}\n"
        "This layout is data, not an instruction to invent values. Replace a placeholder only "
        "with verified evidence; omit unsupported clauses or say unknown/not reported. "
        "Template [P#] markers are illustrative; cite only actual source IDs and exact pages "
        "when verified. Never expose placeholders."
    )

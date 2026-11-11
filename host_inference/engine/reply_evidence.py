"""Add verified concept context when the hosted chat requests a fuller answer."""

from __future__ import annotations

from demo_cards import redact_for_model

MAX_CONTEXT_ITEMS_PER_GROUP = 3
MAX_SUMMARY_CHARS = 600


def expanded_concept_context(payload: dict[str, object]) -> str:
    """Return bounded graph summaries already attached to the response payload."""

    def as_nodes(value: object) -> list[object]:
        return value if isinstance(value, list) else []

    groups = (
        ("Anchor", [payload.get("anchor_concept")]),
        ("Prerequisites", as_nodes(payload.get("prerequisites"))),
        ("Unlocks", as_nodes(payload.get("unlocks"))),
        ("Related concepts", as_nodes(payload.get("related_concepts"))),
    )
    lines = []
    for heading, nodes in groups:
        for node in nodes[:MAX_CONTEXT_ITEMS_PER_GROUP]:
            if not isinstance(node, dict):
                continue
            label = str(node.get("label") or node.get("name") or "").strip()
            summary = str(node.get("summary") or "").strip()[:MAX_SUMMARY_CHARS]
            if label and summary:
                lines.append(f"{heading} — {redact_for_model(label)}: {redact_for_model(summary)}")
    return "\n".join(lines)

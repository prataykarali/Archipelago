"""The campus physical inventory card appended to concept answers.

The contract requires every grounded concept answer to close with the physical
holdings, so a student reading about third normal form is told which book on
the shelf covers it — and is never told the digital copy replaces the print one.

The card is **appended, never substituted**: the concept answer and its
citations come first, unmodified, and the inventory section follows. Losing the
explanation in order to gain a shelf address would be a bad trade.

Attached to the payload rather than inlined into the prose, so the UI can render
it as a distinct card (and so the LLM polisher is never allowed to summarise it
away — a hallucinated call number is worse than none).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Attached only when at least this many catalogue tokens match, so a stray
#: shared word ("networks") does not attach an unrelated book to every answer.
MIN_MATCH_TOKENS = 3

#: Cap so a multi-topic graph neighbourhood cannot produce a wall of cards.
MAX_CARDS = 2


def inventory_cards_for_concept(
    node_id: str,
    node_name: str,
    node_summary: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Catalogue records that plausibly teach ``node_id``.

    Scored on the concept's name and summary, so a concept like "third normal
    form" finds the database textbook whose summary mentions normalisation.
    """
    from .inventory import best_record, match_confidence

    haystack = f"{node_name} {node_summary}".strip()
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Try the full concept first, then progressively narrower: a summary can
    # dilute the signal of a short concept name.
    for probe in (node_name, haystack):
        record, score = best_record(records, probe)
        confidence = match_confidence(score)
        if record is None or confidence == "none":
            continue
        key = str(record.get("isbn") or record.get("title") or "")
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            {
                "concept_id": node_id,
                "title": record.get("title", ""),
                "author": record.get("author", ""),
                "isbn": record.get("isbn", "") or record.get("biblionumber", ""),
                "publisher": record.get("publisher", ""),
                "available_copies": record.get("available_copies", 0),
                "total_copies": record.get("total_copies", 0),
                "match": score,
                "confidence": confidence,
                "reader_url": str(record.get("reader_base_url") or ""),
            }
        )
        if len(cards) >= MAX_CARDS:
            break
    return cards


def render_inventory_section(cards: list[dict[str, Any]]) -> str:
    """Markdown section appended to a grounded concept answer."""
    if not cards:
        return ""

    lines = [
        "",
        "---",
        "",
        "### 3. Physical Campus Library Inventory",
        "",
        "To study this topic using physical campus assets, locate the following at the "
        "Central Library:",
        "",
    ]
    for card in cards:
        available = int(card.get("available_copies") or 0)
        total = int(card.get("total_copies") or 0)
        qualifier = "" if card.get("confidence") == "confirmed" else " (closest indexed match)"
        lines.append(f"* **Resource title.** {card.get('title', '')}{qualifier}")
        if card.get("author"):
            lines.append(f"* **Author.** {card['author']}")
        if card.get("isbn"):
            lines.append(f"* **ISBN / shelf locator.** `{card['isbn']}`")
        lines.append(
            f"* **Live shelf availability.** **{available} physical cop"
            f"{'y' if available == 1 else 'ies'} available** out of {total} total."
        )
        if card.get("reader_url"):
            lines.append(f"* **Institutional e-resource.** {card['reader_url']}")

    lines += [
        "",
        "Borrowing from the Central Library remains the primary route; digital access "
        "does not replace the physical collection.",
    ]
    return "\n".join(lines)


def attach_inventory(
    payload: dict[str, Any],
    concept_id: str | None,
    concept_name: str,
    concept_summary: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach inventory cards to a chat payload. Returns the cards attached.

    Never raises: an inventory lookup failure must not cost the student their
    explanation.
    """
    if not concept_id:
        return []
    try:
        cards = inventory_cards_for_concept(
            concept_id, concept_name, concept_summary, records
        )
    except Exception as exc:
        logger.warning("Inventory lookup failed for %s: %s", concept_id, exc)
        return []

    if not cards:
        return []
    payload["inventory"] = cards
    return cards


__all__ = [
    "MAX_CARDS",
    "MIN_MATCH_TOKENS",
    "attach_inventory",
    "inventory_cards_for_concept",
    "render_inventory_section",
]

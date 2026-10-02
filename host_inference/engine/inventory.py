"""Physical campus inventory: resolve a title to a shelf card.

The concept graph answers *what a topic is*; this answers *where the book is*.
That data was unreachable from the shelf router: it only consulted the concept
graph, so every "where is a physical copy of X" query fell through to the
out-of-domain kill switch even though the institution had catalogued the title.

Sources, in order of authority:

1. the graph's ``Resource`` table (Koha + Pearson eLibrary), which carries call
   numbers, barcodes and live copy counts;
2. the hosted Pearson bookshelf export;
3. an honest "not indexed" reply.

Every physical claim is sourced. When the institution holds no physical copy the
card says so plainly and reports the demand signal instead of inventing a
location — a fabricated rack number is worse than no answer.
"""
from __future__ import annotations

from collections.abc import Iterable
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# A title mention is worth querying the catalogue when it has at least this many
# distinctive tokens. One shared word ("systems") matches half the catalogue.
MIN_TITLE_TOKENS = 2
# Below this many tokens the card explicitly says nothing is indexed rather
# than matching an arbitrary record.
STRONG_TITLE_TOKENS = 3

# Locations with no matching record are the single most damaging failure mode:
# a student walks to a rack that does not exist. Never guess.
NO_RECORD_TEMPLATE = (
    "**{title}.** No physical copy of this title is indexed in the campus "
    "catalogue for the Central Library.\n\n"
    "Search the OPAC for the current holdings: http://uemk-opac.l2c2.co.in, "
    "or ask at the circulation desk. If the library does not hold it, the "
    "acquisition desk can place a request — this has been logged as demand."
)


def _norm(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    """Content tokens, with edition/ordinal noise removed."""
    stop = {
        "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "ed",
        "edition", "vol", "volume", "book", "copy", "copies", "physical",
        "campus", "library", "find", "where", "can", "i", "me", "my", "please",
        "is", "there", "any", "have", "has", "do", "you", "available",
    }
    return {tok for tok in _norm(text).split() if tok not in stop and len(tok) > 1}


def extract_title(query: str) -> str:
    """Pull the quoted or emphasised title out of a shelf query.

    Handles the three shapes students actually use: quoted (``'Database System
    Concepts'``), titled after a preposition (``for Operating Systems Internals``),
    and bare (``barcode for Database System Concepts``).
    """
    # Students paste curly quotes from Word and search boxes, so the delimiter
    # set covers ASCII, single-curly, and double-curly forms.
    quoted = re.search(
        "[\"'\u2018\u201c]([^\"'\u2019\u201d]{3,120})[\"'\u2019\u201d]", query
    )
    if quoted:
        return quoted.group(1).strip()

    titled = re.search(
        r"\b(?:for|of|title|called|named)\s+([A-Z0-9][^?!.]{2,90})", query
    )
    if titled:
        candidate = re.split(r"\s+(?:on|at|in|for|available)\b", titled.group(1))[0]
        if candidate.strip():
            return candidate.strip(" .,")

    # Fall back to the longest capitalised run, which is how textbooks appear.
    caps = re.findall(r"\b[A-Z][A-Za-z0-9&:'\-]*(?:\s+[A-Z0-9][A-Za-z0-9&:'\-]*)*", query)
    caps = [c.strip() for c in caps if len(c.split()) >= 2]
    if caps:
        return max(caps, key=len)
    return _norm(query)


def score_record(query_tokens: set[str], title: str, author: str = "") -> int:
    """Distinctive-token overlap between the query and one catalogue record."""
    record_tokens = _tokens(f"{title} {author}")
    if not query_tokens or not record_tokens:
        return 0
    return len(query_tokens & record_tokens)


def best_record(
    records: Iterable[dict[str, Any]], title: str, author: str = ""
) -> tuple[dict[str, Any] | None, int]:
    """Highest-overlap catalogue record for ``title``."""
    wanted = _tokens(title)
    best, best_score = None, 0
    for record in records:
        score = score_record(wanted, str(record.get("title") or ""), author)
        if score > best_score:
            best, best_score = record, score
    return best, best_score


def holds_record(records: Iterable[dict[str, Any]], title: str) -> bool:
    """Whether the catalogue plausibly holds this title."""
    _record, score = best_record(records, title)
    return score >= STRONG_TITLE_TOKENS


# A 2-token overlap is usually the same book under a different title
# ("Database System Concepts" vs "Fundamentals of Database System"). Claiming
# "not indexed" there is unhelpful and arguably false, so such a match is shown
# but explicitly labelled as the closest match rather than asserted outright.
PROBABLE_TITLE_TOKENS = 2


def match_confidence(score: int) -> str:
    """``"confirmed"``, ``"probable"``, or ``"none"`` for a match score."""
    if score >= STRONG_TITLE_TOKENS:
        return "confirmed"
    if score >= PROBABLE_TITLE_TOKENS:
        return "probable"
    return "none"


def probable_match_notice(requested: str, matched: str) -> str:
    """Prepended to a probable-match card so the substitution is visible."""
    return (
        f"**Closest indexed match.** No record exactly titled *{requested}*; "
        f"the catalogue holds *{matched}*, which covers the same subject.\n"
    )


# ─── Rendering ──────────────────────────────────────────────────────────────


def _copies(record: dict[str, Any]) -> tuple[int, int]:
    """``(available, total)`` copy counts, tolerating string or null cells."""
    def as_int(value: Any) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    total = as_int(record.get("total_copies")) or 1
    available = as_int(record.get("available_copies"))
    return max(0, min(available, total)), total


def shelf_card(
    record: dict[str, Any],
    citation: str = "",
    doc_link: str = "",
    requested: str = "",
    confidence: str = "confirmed",
) -> str:
    """Render the physical inventory card for one catalogue record.

    Field order mirrors how a student uses the desk: identify the book, find the
    shelf, check availability. A ``probable`` match is labelled so a substitution
    is never presented as a confirmed holding.
    """
    title = str(record.get("title") or "").strip()
    author = str(record.get("author") or "").strip()
    publisher = str(record.get("publisher") or "").strip()
    biblionumber = str(record.get("biblionumber") or "").strip()
    available, total = _copies(record)

    lines: list[str] = []
    if confidence == "probable" and requested:
        lines.append(probable_match_notice(requested, title))
        lines.append("")

    lines.append(f"**Resource title.** {title}{citation}")
    lines.append(f"**Author / year.** {author or 'Unknown'}.")

    if biblionumber and biblionumber not in {"0", "Unknown"}:
        label = "ISBN / shelf locator" if record.get("isbn") else "Call number / shelf location"
        lines.append(f"**{label}.** `{biblionumber}`{citation}")

    lines.append(
        f"**Live shelf availability.** **{available} physical cop{'y' if available == 1 else 'ies'} "
        f"available** out of {total} total{citation}."
    )

    barcodes = _render_barcodes(record.get("barcodes"))
    if barcodes:
        lines.append(f"**System barcode.** {barcodes}")

    if publisher and publisher != "Unknown":
        lines.append(f"**Publisher.** {publisher}.")

    if doc_link:
        lines.append(f"**Digital passage mapping.** `PROVIDES_TEXT` ➔ {doc_link}")

    lines.append("")
    lines.append(
        "Borrowing from the Central Library remains the primary route; "
        "digital access does not replace the physical collection."
    )
    return "\n".join(lines)


def _render_barcodes(raw: Any) -> str:
    """Render the barcodes cell (JSON array string or list) for display."""
    import json

    values: list[str] = []
    if isinstance(raw, list):
        values = [str(v).strip() for v in raw if str(v).strip()]
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    values = [str(v).strip() for v in parsed if str(v).strip()]
            except json.JSONDecodeError:
                values = []
        if not values:
            values = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    return ", ".join(values)


def no_record_reply(title: str) -> str:
    """Honest reply when the catalogue holds nothing matching."""
    return NO_RECORD_TEMPLATE.format(title=title.strip() or "That title")


__all__ = [
    "MIN_TITLE_TOKENS",
    "PROBABLE_TITLE_TOKENS",
    "STRONG_TITLE_TOKENS",
    "best_record",
    "extract_title",
    "holds_record",
    "match_confidence",
    "no_record_reply",
    "probable_match_notice",
    "score_record",
    "shelf_card",
]

"""Library-intent detection: books, journals, hours, credentials, catalog."""
from __future__ import annotations

import re

from . import _deps as _rt


def _detect_library_intent(query: str) -> dict | None:
    """Detect all library, book, journal, inventory, hours, and holdings intents."""
    q = (query or "").strip()
    ql = q.lower()
    if not ql:
        return None

    from archipelago.inference.library_credentials import detect_credentials_query
    from archipelago.inference.library_schedules import detect_library_hours_query

    # Combined hours + access ("is the library open on weekends and what is the
    # opac link?") matched the credential branch and answered with the portal
    # card alone, silently dropping the schedule — the one half the student
    # cannot look up anywhere else. Hours is detected independently and carried
    # as a slot so the dispatcher can answer both halves in one reply.
    wants_hours = detect_library_hours_query(q) is not None
    hours_slot = {"also_hours": True} if wants_hours else {}

    catalog_stats = (
        ("subject" in ql and any(term in ql for term in ("highest", "leaderboard", "title count")))
        or ("journal" in ql and any(term in ql for term in ("title count", "issue count", "total issues")))
        or ("keyword" in ql and any(term in ql for term in ("catalog", "titles", "search")))
        or ("zero" in ql and "copies" in ql)
    )
    if catalog_stats:
        return {"intent": "library_catalog_stats", "raw": q}

    journal_status = re.search(r"\b(journals?|periodicals?|magazines?)\b", ql) and re.search(r"\b(late|issues?|subscription|status|latest|available)\b", ql)
    if journal_status:
        return {"intent": "library_journal_status", "raw": q}

    circulation_request = re.search(r"\b(borrow|check\s*out|checkout|reserve|physical\s+cop(?:y|ies)|copies?\s+of)\b|\bphysical\s+book\b", ql)
    if circulation_request:
        return {"intent": "library_resource_lookup", "raw": q}

    if re.search(r"\bworking\s+hours\b|\boperating\s+schedule\b|\blibrary\s+(?:hours?|times?|timings?|schedule)\b|\b(?:hours?|times?|timings?)\s+(?:of|for)\s+(?:the\s+)?library\b|\bwhen\s+is\s+(?:the\s+)?library\s+open\b|\btell\s+timing\s+of\s+library\b", ql):
        return {"intent": "library_hours", "raw": q, "slots": hours_slot}

    credential_request = detect_credentials_query(q)
    if credential_request:
        return {
            "intent": "library_resources",
            "resource_key": credential_request.get("resource_key", ""),
            "raw": q,
            "slots": {**credential_request.get("slots", {}), "resource_access": True, **hours_slot},
        }

    if re.search(
        r"\b(e[- ]?resources?|e[- ]?resource\s+portals?|library\s+portals?|"
        r"research\s+databases?|digital\s+library\s+portals?|pearson\s+e[- ]?library|"
        r"sciencedirect|science\s+direct|ieee\s*xplore|springer(?:\s+link)?)\b",
        ql,
    ):
        return {
            "intent": "library_resources",
            "raw": q,
            "resource_access": True,
            **({"slots": hours_slot} if hours_slot else {}),
        }

    # 0. Lab manuals and reprography. "Where are the lab manuals?" is a shelf
    #    location question, but it matched no holdings pattern and fell through
    #    to the out-of-domain reject — telling a student the library does not
    #    have the manuals when it stocks them at a known reprography counter.
    if re.search(r"\b(lab\s+manuals?|xerox|reprography|muskan)\b", ql):
        return {"intent": "library_materials", "raw": q}

    # 1. Book Details / Specific Book Summary
    book_detail_patterns = (
        r"\b(tell\s+me\s+about\s+(?:this\s+|the\s+)?(?:book|paper|textbook))\b",
        r"\b(details?\s+(?:of|for|about)\s+(?:this\s+|the\s+)?(?:book|paper|textbook))\b",
        r"\b(what\s+is\s+(?:this|the)?\s*(?:book|paper|textbook))\b",
        r"\b(about\s+this\s+book:?)\b",
        r"\b(book\s+details:?)\b",
        r"\b(details\s+(?:on|about)\s+(?:book|paper|textbook))\b",
    )
    if any(re.search(p, ql) for p in book_detail_patterns):
        return {"intent": "library_book_details", "raw": q}

    # 2. Journal & Inventory & Holdings
    holdings_patterns = (
        r"\b(journal|journals|inventory|holdings|copies|accession|periodicals?)\b",
        r"\b(how\s+many\s+copies|available\s+copies|total\s+copies|stock|shelf\s+location)\b",
        r"\b(show\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?:book|journal|library)?\s*(?:inventory|holdings|details|status|records))\b",
        r"\b(what\s+(?:books|journals|holdings)\s+(?:do\s+you\s+have|are\s+available|exist))\b",
        r"\b(is\s+.+\s+available\s+in\s+(?:the\s+)?library)\b",
        r"\b(library\s+catalog|library\s+database|library\s+records)\b",
    )
    if any(re.search(p, ql) for p in holdings_patterns):
        return {"intent": "library_holdings", "raw": q}

    # 3. Hours & Services
    hours_patterns = (
        r"\b(library\s+hours|hours\s+of\s+library|when\s+is\s+(?:the\s+)?library\s+open|library\s+timings?|library\s+schedule)\b",
        r"\b(is\s+(?:the\s+)?library\s+open\b)",
        r"\b(open\s+on\s+(?:saturdays?|sundays?|weekends?))\b",
    )
    if any(re.search(p, ql) for p in hours_patterns):
        return {"intent": "library_hours", "raw": q, "slots": hours_slot}

    # 4. Chapter lookup (must run before generic book-recommendation patterns)
    concept_verbs = r"\b(discuss(?:es|ed)?|mention(?:s|ed)?|contain(?:s|ed)?|cover(?:s|ed)?)\b"
    if (
        re.search(r"\b(which|what)\s+(chapters?|sections?)\b", ql)
        and (re.search(concept_verbs, ql) or re.search(r"\babout\b", ql))
    ):
        return {"intent": "library_chapter_lookup", "raw": q}

    if (
        re.search(r"\b(chapters?|sections?)\s+(of|in)\b", ql)
        and re.search(concept_verbs, ql)
    ):
        return {"intent": "library_chapter_lookup", "raw": q}

    if re.search(
        r"\bwhere\s+(in|does)\b", ql
    ) and re.search(r"\b(talk(?:s|ed)?|discuss(?:es|ed)?|mention(?:s|ed)?|cover(?:s|ed)?)\b", ql):
        return {"intent": "library_chapter_lookup", "raw": q}

    if re.search(
        r"\b("
        r"chapters?\s+of|chapters?\s+in|sections?\s+of|sections?\s+in|"
        r"table\s+of\s+contents|list\s+chapters|show\s+chapters|"
        r"what\s+are\s+the\s+chapters|what\s+are\s+the\s+sections"
        r")\b",
        ql,
    ):
        return {"intent": "library_chapters", "raw": q}

    # 5. Book recommendations / suggested readings
    book_patterns = (
        r"\b(suggest|recommend)\b.+\b(books?|papers?|readings?|textbooks?)\b",
        r"\b(top|best)\s+\d*\s*(books?|papers?|readings?)\b",
        r"\b(books?|papers?)\s+(for|on|about|regarding)\b",
        r"\bwhat\s+(books?|papers?)\s+(should|can|to|on|for|about)\b",
        r"\b(reading\s+list|bibliography)\b.+\b(for|on|about)\b",
        r"\b(resources?|readings?|material)\s+(for|on|about)\b",
        r"\bwhat\s+should\s+i\s+read\b",
        r"\b(suggest|recommend)\b.+\b(reading|resources?|materials?)\b",
    )
    if any(re.search(p, ql) for p in book_patterns):
        # Recommendation cards cap at 4 (chat UI shelf grid) — test-pinned.
        limit = 4
        m = re.search(r"\btop\s+(\d+)\b", ql) or re.search(r"\b(\d+)\s+(books?|papers?)\b", ql)
        if m:
            try:
                limit = max(1, min(4, int(m.group(1))))
            except ValueError:
                limit = 4
        # The topic must sit inside the library's shelf ("suggest books about
        # stars" is out of scope even though the intent is book-shaped).
        if not _rt._is_learning_or_domain_query(q):
            return None
        from archipelago.inference.ranking_seeds import detect_subject_key
        subject = detect_subject_key(q)
        return {
            "intent": "library_books",
            "raw": q,
            "limit": limit,
            **({"seed_subject": subject} if subject else {}),
        }

    return None

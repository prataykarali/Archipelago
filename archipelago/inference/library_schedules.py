"""Library Schedules — Fixed Operating Hours Lookup (SCH-1).

Grounded in institutional poster ``docs/time_library.png``:
  - Library is open 24 × 7 × 365 (including night hours and break time).
  - Open on Saturdays and Sundays; book issue/return unavailable on weekends.
  - Open-access shelves; OPAC at https://uemk-opac.l2c2.co.in

Bypasses topological RAG and language models entirely.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any


# ── SCH-1: Static Library Schedule (from time_library.png) ────────────────

LIBRARY_SCHEDULES: dict[str, dict[str, Any]] = {
    "always": {
        "label": "All Days (24 × 7 × 365)",
        "hours": "Open 24 hours (24 × 7 × 365)",
        "open_24_7": True,
        "note": (
            "Students may use the Library before or after class hours, "
            "including during night hours and break time."
        ),
    },
    "weekday": {
        "label": "Weekdays (Monday – Friday)",
        "hours": "Open 24 hours",
        "open_24_7": True,
        "book_issue": True,
        "note": "Full services including book issue and return.",
    },
    "weekend": {
        "label": "Saturdays & Sundays",
        "hours": "Open 24 hours",
        "open_24_7": True,
        "book_issue": False,
        "note": (
            "Library remains open on Saturdays and Sundays; "
            "book issue and return services are not available on weekends."
        ),
    },
    "holiday": {
        "label": "Public Holidays",
        "hours": "Open 24 hours",
        "open_24_7": True,
        "book_issue": False,
        "note": "Reading room access follows the 24×7 policy; confirm notices for service desks.",
    },
}

_DAY_SCHEDULE_MAP: dict[str, str] = {
    "monday": "weekday",
    "tuesday": "weekday",
    "wednesday": "weekday",
    "thursday": "weekday",
    "friday": "weekday",
    "saturday": "weekend",
    "sunday": "weekend",
}


def _parse_clock_token(token: str) -> int | None:
    """Parse '8 PM', '8:30am', '20:00' → minutes since midnight. None if unparsed."""
    t = (token or "").strip().lower()
    if not t:
        return None
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", t)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = m.group(3)
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def is_library_open(day: str | None = None, time_token: str | None = None) -> dict[str, Any]:
    """Answer open/closed for a day (+ optional clock time). Always open under 24×7 policy."""
    day_lower = (day or "today").strip().lower()
    if day_lower == "today":
        day_lower = datetime.now().strftime("%A").lower()
    schedule_key = _DAY_SCHEDULE_MAP.get(day_lower, "always")
    entry = LIBRARY_SCHEDULES.get(schedule_key, LIBRARY_SCHEDULES["always"])
    minutes = _parse_clock_token(time_token) if time_token else None
    # 24×7 policy → open at any valid clock time (and when no time given).
    open_now = True
    if time_token and minutes is None:
        # Unparseable time still treated as open under 24×7, with a note.
        open_now = True
    return {
        "open": open_now,
        "day": day_lower,
        "time": time_token,
        "hours": entry.get("hours", "Open 24 hours"),
        "book_issue": entry.get("book_issue", schedule_key == "weekday"),
        "label": entry.get("label", ""),
        "note": entry.get("note", ""),
        "policy": "24x7x365",
    }


def get_library_hours(day: str | None = None) -> dict[str, Any]:
    """Get library operating hours.

    Args:
        day: Optional day name ("monday", "sunday", etc.) or "today".
              If None, returns the full schedule.
    """
    if day is None:
        return {
            "schedule": LIBRARY_SCHEDULES,
            "query_type": "full_schedule",
            "policy": "24x7x365",
        }

    day_lower = day.strip().lower()

    # Allow free-text like "sunday at 8 PM"
    time_match = re.search(
        r"\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", day_lower, re.I
    )
    time_token = time_match.group(1) if time_match else None

    if day_lower == "today" or "today" in day_lower:
        now = datetime.now()
        day_name = now.strftime("%A").lower()
        schedule_key = _DAY_SCHEDULE_MAP.get(day_name, "always")
        entry = {**LIBRARY_SCHEDULES.get(schedule_key, LIBRARY_SCHEDULES["always"]), "day": day_name}
        open_info = is_library_open(day_name, time_token)
        return {
            "schedule": entry,
            "query_type": "today",
            "open": open_info,
            "policy": "24x7x365",
        }

    for dname in _DAY_SCHEDULE_MAP:
        if dname in day_lower or day_lower == dname:
            schedule_key = _DAY_SCHEDULE_MAP[dname]
            entry = {**LIBRARY_SCHEDULES.get(schedule_key, LIBRARY_SCHEDULES["always"]), "day": dname}
            open_info = is_library_open(dname, time_token)
            return {
                "schedule": entry,
                "query_type": "day_lookup",
                "open": open_info,
                "policy": "24x7x365",
            }

    return {
        "schedule": LIBRARY_SCHEDULES,
        "query_type": "full_schedule",
        "policy": "24x7x365",
        "note": f"Could not parse day '{day}'. Returning full schedule.",
    }


def format_schedule_for_response(schedule_result: dict[str, Any]) -> str:
    """Format schedule data into a human-readable response string (no LLM)."""
    qtype = schedule_result.get("query_type", "full_schedule")
    schedule = schedule_result.get("schedule", {})
    open_info = schedule_result.get("open") or {}

    if qtype in ("today", "day_lookup"):
        day = schedule.get("day", open_info.get("day", ""))
        hours = schedule.get("hours", "Open 24 hours")
        note = schedule.get("note", "")
        label = schedule.get("label", "")
        open_line = ""
        if open_info:
            status = "YES — open" if open_info.get("open") else "NO — closed"
            t = open_info.get("time")
            if t:
                open_line = f"\n   **Open at {t}?** {status} (24×7×365 policy)."
            else:
                open_line = f"\n   **Open?** {status} (24×7×365 policy)."
            if open_info.get("book_issue") is False:
                open_line += "\n   _Book issue/return is not available on weekends._"
        return (
            f"📚 Library Hours for **{str(day).capitalize()}** ({label}):\n"
            f"   **{hours}**{open_line}\n"
            f"   _{note}_"
        )

    lines = [
        "📚 **IEM/UEM Library Operating Hours**",
        "",
        "**Policy**: Open **24 × 7 × 365** (including night hours and break time).",
        "",
    ]
    for key in ("always", "weekday", "weekend", "holiday"):
        entry = LIBRARY_SCHEDULES.get(key)
        if not entry:
            continue
        lines.append(f"**{entry['label']}**: {entry['hours']}")
        lines.append(f"   _{entry['note']}_")
        lines.append("")
    lines.append("OPAC: https://uemk-opac.l2c2.co.in")
    return "\n".join(lines).rstrip()


# ── Query Router Integration ──────────────────────────────────────────────

_SCHEDULE_KEYWORDS = re.compile(
    r"("
    r"library\s+hours?|operating\s+hours?|opening\s+hours?|closing\s+times?|"
    r"working\s+hours?|"
    r"open\s+now|is\s+it\s+open|when\s+(?:do\s+|does\s+|is\s+the\s+)library\s+"
    r"(?:open|close)|"
    r"hours?\s+of\s+operation|library\s+(?:timing|timings|schedule)|"
    r"what\s+time\s+(?:does\s+|is\s+)the\s+library|"
    r"library\s+open\s+on\s+\w+|open\s+on\s+sundays?|open\s+on\s+weekends?|"
    r"weekend\s+hours?|sunday\s+hours?|holiday\s+schedule|"
    r"24\s*[x×]\s*7|24/?7|"
    r"is\s+the\s+(?:iem/?uem\s+|iem\s+|uem\s+)?library\s+open|"
    r"library\s+open"
    r")",
    re.I,
)

_DAY_PATTERN = re.compile(
    r"\b(mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?|today)\b",
    re.I,
)


def detect_library_hours_query(query: str) -> dict | None:
    """Check if a user query is asking about library operating hours."""
    if not query:
        return None

    if _SCHEDULE_KEYWORDS.search(query):
        day_match = _DAY_PATTERN.search(query)
        raw_day = day_match.group(1).lower() if day_match else None
        # Normalize plurals: "sundays" → "sunday"
        day = raw_day.rstrip("s") if raw_day and raw_day != "today" and raw_day.endswith("s") else raw_day
        if day == "today":
            pass
        # Free-text (with clock time) is passed through for get_library_hours parsing.
        day_arg = query if (day and re.search(r"\d", query)) else day
        return {
            "route": "library_hours",
            "day": day,          # canonical day name for tests / slots
            "day_arg": day_arg,  # free-text for time-aware lookup
            "raw_query": query,
        }

    return None

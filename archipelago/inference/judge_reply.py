from __future__ import annotations

import json
import re

JUDGE_SYSTEM_PROMPT: str = (
    "You are Archipelago's source-grounded library reply judge. For academic concept questions, "
    "use this compact eight-tier presentation when supported by indexed context: Overview, "
    "Mathematical Formulation, Technical Mechanism, DBMS or domain-specific detail, Learning Path, "
    "Evidence, Pilot context, and Next reading. Omit empty tiers rather than inventing facts. "
    "Never invent citations, page numbers, holdings, or source details. Keep the answer clear for "
    "undergraduate students and use only the supplied evidence."
)

JUDGE_MAX_OUTPUT_TOKENS: int = 512
JUDGE_TEMPERATURE: float = 0.0


def build_judge_user_content(
    query: str | None = None,
    answer: str | None = None,
    *,
    context: str | None = None,
    user_query: str | None = None,
    allowed_evidence_ids: set[str] | list[str] | None = None,
) -> str:
    """Serialize untrusted request/context as JSON for fixed judge instructions."""
    payload = {
        "user_query": user_query if user_query is not None else (query or ""),
        "context": context if context is not None else (answer or ""),
        "allowed_evidence_ids": sorted(str(item) for item in (allowed_evidence_ids or [])),
        "presentation": "SoFerence 8-tier grounded answer; omit unsupported tiers.",
        "reply_architecture": [
            "Overview", "Mathematical Formulation", "Technical Mechanism",
            "Domain Detail", "Learning Path", "Evidence", "Pilot Context", "Next Reading",
        ],
    }
    return "UNTRUSTED_DATA_JSON:\n" + json.dumps(payload, ensure_ascii=False)


def has_judge_section_headings(text: str) -> bool:
    """Require the core overview, formulation, learning path, and evidence tiers."""
    t = text or ""
    required = ("overview", "mathematical formulation", "learning path", "evidence")
    return all(re.search(rf"(?im)^\s*#+\s*{re.escape(h)}\s*$", t) for h in required)

"""Grounded staff replies from a completed research shortlist."""

from __future__ import annotations

from typing import Any


def build_research_reply(job: dict[str, Any]) -> dict[str, Any]:
    """Render stored topic-relevance results without inventing evidence."""
    papers = job.get("shortlist") or []
    status = str(job.get("status") or "unknown")
    topic = str(job.get("topic") or "")
    if status not in {"complete", "partial"}:
        return {
            "job_id": str(job["job_id"]),
            "status": status,
            "text": "Research discovery is still in progress.",
            "papers": [],
            "coverage_gaps": [],
        }
    lines = [f"Research papers relevant to {topic}:"]
    for paper in papers:
        reasons = "; ".join(str(reason) for reason in paper.get("topic_relevance_reason") or [])
        identity = paper.get("doi") or paper.get("arxiv_id") or paper.get("paper_id")
        lines.append(
            f"{paper['rank']}. {paper['title']} ({paper.get('year') or 'year unknown'}) — {identity}. {reasons}."
        )
    if not papers:
        lines.append("No papers met the topic-relevance threshold in this run.")
    gaps = [gap.strip() for gap in str(job.get("error") or "").split(",") if gap.strip()]
    if gaps:
        lines.append("Coverage gaps: " + ", ".join(gaps) + ".")
    return {
        "job_id": str(job["job_id"]),
        "status": status,
        "text": "\n".join(lines),
        "papers": papers,
        "coverage_gaps": gaps,
    }

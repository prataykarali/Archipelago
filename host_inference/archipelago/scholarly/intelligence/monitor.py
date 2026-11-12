"""Opt-in metadata monitoring with idempotent changed-paper detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any

from .postgres_storage import PostgresResearchStore
from .search import discover
from .storage import ResearchStore

LEASE_MINUTES = 10


def run_monitor(monitor_id: str, store: ResearchStore | PostgresResearchStore) -> dict[str, Any]:
    """Refresh one authorized monitor; repeated unchanged runs create no snapshot."""
    now = datetime.now(UTC)
    monitor = store.claim_monitor(
        monitor_id, now.isoformat(), (now + timedelta(minutes=LEASE_MINUTES)).isoformat()
    )
    if monitor is None:
        return {"status": "not_enabled_or_claimed"}
    owner = str(monitor["owner"])
    try:
        previous = store.get_run(str(monitor["last_run"]), owner) if monitor["last_run"] else None
        current = discover(json.loads(monitor["options"]))
        if not any(source["status"] in {"live", "live_empty"} for source in current["sources"]):
            raise RuntimeError("all_providers_unavailable")
        before = {row["paper_id"]: row for row in previous["papers"]} if previous else {}
        added = [row["paper_id"] for row in current["papers"] if row["paper_id"] not in before]
        citation_changes = [
            row["paper_id"]
            for row in current["papers"]
            if row["paper_id"] in before
            and row["citation_observations"] != before[row["paper_id"]].get("citation_observations")
        ]
        if previous and not added and not citation_changes:
            store.finish_monitor(monitor_id, None, None)
            return {"status": "unchanged", "run_id": monitor["last_run"], "new_papers": []}
        run_id = store.save_run(owner, current)
        store.finish_monitor(monitor_id, run_id, None)
        for row in current["papers"]:
            if row["paper_id"] in added:
                store.add_event(
                    owner,
                    monitor_id,
                    run_id,
                    "newly_indexed_paper",
                    row["paper_id"],
                    {
                        "title": row["title"],
                        "publication_date": row["publication_date"],
                        "discovered_at": current["retrieved_at"],
                    },
                )
            elif row["paper_id"] in citation_changes:
                store.add_event(
                    owner,
                    monitor_id,
                    run_id,
                    "citation_observation_changed",
                    row["paper_id"],
                    {"title": row["title"], "observations": row["citation_observations"]},
                )
        return {
            "status": "updated",
            "run_id": run_id,
            "new_papers": added,
            "citation_changes": citation_changes,
            "discovered_at": current["retrieved_at"],
        }
    except (OSError, RuntimeError, ValueError) as exc:
        store.finish_monitor(monitor_id, None, type(exc).__name__)
        store.add_event(
            owner,
            monitor_id,
            None,
            "monitor_failed",
            type(exc).__name__,
            {"error": type(exc).__name__, "occurred_at": datetime.now(UTC).isoformat()},
        )
        return {"status": "failed", "error": type(exc).__name__}

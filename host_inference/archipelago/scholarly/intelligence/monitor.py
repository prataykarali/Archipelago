"""Opt-in metadata monitoring with idempotent changed-paper detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any

from .postgres_storage import PostgresResearchStore
from .search import discover
from .storage import ResearchStore

LEASE_MINUTES = 10


def _evidence(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compare provider facts while ignoring a fresh lookup timestamp."""
    return {key: item for key, item in value.items() if key != "retrieved_at"} if value else None


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
        previous_authors = (
            {row["id"]: row for row in previous.get("author_observations", [])} if previous else {}
        )
        author_changes = [
            row["id"]
            for row in current.get("author_observations", [])
            if previous and _evidence(row) != _evidence(previous_authors.get(row["id"]))
        ]
        venue_changes = [
            row["paper_id"]
            for row in current["papers"]
            if row["paper_id"] in before
            and _evidence(row.get("venue_details"))
            != _evidence(before[row["paper_id"]].get("venue_details"))
        ]
        retraction_changes = [
            row["paper_id"]
            for row in current["papers"]
            if row["paper_id"] in before
            and row.get("retraction_status") != before[row["paper_id"]].get("retraction_status")
        ]
        if previous and not any(
            (added, citation_changes, author_changes, venue_changes, retraction_changes)
        ):
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
                        "source_url": row.get("url"),
                        "provider": row.get("source"),
                    },
                )
            elif row["paper_id"] in citation_changes:
                store.add_event(
                    owner,
                    monitor_id,
                    run_id,
                    "citation_observation_changed",
                    row["paper_id"],
                    {
                        "title": row["title"],
                        "old": before[row["paper_id"]].get("citation_observations"),
                        "new": row["citation_observations"],
                        "discovered_at": current["retrieved_at"],
                    },
                )
            if row["paper_id"] in retraction_changes:
                store.add_event(
                    owner,
                    monitor_id,
                    run_id,
                    "retraction_status_changed",
                    row["paper_id"],
                    {
                        "title": row["title"],
                        "old": before[row["paper_id"]].get("retraction_status"),
                        "new": row.get("retraction_status"),
                    },
                )
            if row["paper_id"] in venue_changes:
                store.add_event(
                    owner,
                    monitor_id,
                    run_id,
                    "venue_metadata_changed",
                    row["paper_id"],
                    {
                        "old": before[row["paper_id"]].get("venue_details"),
                        "new": row.get("venue_details"),
                    },
                )
        for row in current.get("author_observations", []):
            if row["id"] in author_changes:
                store.add_event(
                    owner,
                    monitor_id,
                    run_id,
                    "author_metadata_changed",
                    row["id"],
                    {"old": previous_authors.get(row["id"]), "new": row},
                )
        return {
            "status": "updated",
            "run_id": run_id,
            "new_papers": added,
            "citation_changes": citation_changes,
            "author_changes": author_changes,
            "venue_changes": venue_changes,
            "retraction_changes": retraction_changes,
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

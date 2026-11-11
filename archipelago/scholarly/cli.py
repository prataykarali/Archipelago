"""Operator CLI for the disabled-by-default Research Intelligence worker."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from archipelago.scholarly.pipeline.postgres_store import PostgresResearchStore
from archipelago.scholarly.pipeline.projection import rebuild_projection, refresh_pending_projection
from archipelago.scholarly.pipeline.research_job import ResearchJobRunner

DEFAULT_POLL_SECONDS = 60
logger = logging.getLogger("archipelago.scholarly.worker")


def work_cycle(store: PostgresResearchStore, *, fulltext: bool = False) -> dict[str, Any]:
    """Enqueue due topics, run one job, and refresh pending graph generations."""
    recovered = store.requeue_stale_jobs()
    due = store.enqueue_due_topics()
    result = ResearchJobRunner(store, fetch_fulltext=fulltext).run_next()
    root = os.getenv("ARCHIPELAGO_RESEARCH_PROJECTION_ROOT", "").strip()
    projection = refresh_pending_projection(store, Path(root)) if root else None
    return {"recovered_jobs": recovered, "due_topics": due, "job": result, "projection": projection}


def main() -> None:
    """Initialize private storage, process queued work, or resume a failed job."""
    parser = argparse.ArgumentParser(description="Research Intelligence pipeline operations")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init-db", help="Install private PostgreSQL schema")
    worker = subcommands.add_parser("work-once", help="Process one queued research job")
    worker.add_argument("--fulltext", action="store_true", help="Process rights-approved PDFs")
    resume = subcommands.add_parser("resume", help="Requeue an interrupted or failed job")
    resume.add_argument("job_id")
    projection = subcommands.add_parser(
        "rebuild-projection", help="Build a new Kùzu research projection"
    )
    projection.add_argument("output_path", type=Path)
    cycle = subcommands.add_parser(
        "work-cycle", help="Process one queued job and refresh derived projection"
    )
    cycle.add_argument("--fulltext", action="store_true", help="Process rights-approved PDFs")
    daemon = subcommands.add_parser("work-daemon", help="Continuously poll jobs and tracked topics")
    daemon.add_argument("--fulltext", action="store_true", help="Process rights-approved PDFs")
    daemon.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    args = parser.parse_args()

    store = PostgresResearchStore()
    if args.command == "init-db":
        store.initialize_schema()
        print("Private research schema initialized")
        return
    if os.getenv("ARCHIPELAGO_RESEARCH_ENABLED", "0").lower() not in {"1", "true", "yes"}:
        parser.error("Research pipeline is disabled in this environment")
    if args.command == "resume":
        store.resume_job(args.job_id)
        print("Job requeued")
        return
    if args.command == "rebuild-projection":
        print(json.dumps(rebuild_projection(store, args.output_path)))
        return
    if args.command == "work-cycle":
        print(json.dumps(work_cycle(store, fulltext=args.fulltext), default=str))
        return
    if args.command == "work-daemon":
        if args.poll_seconds < 1:
            parser.error("Poll interval must be positive")
        try:
            while True:
                try:
                    cycle_result = work_cycle(store, fulltext=args.fulltext)
                    if (
                        cycle_result["job"]
                        or cycle_result["projection"]
                        or cycle_result["due_topics"]
                    ):
                        print(json.dumps(cycle_result, default=str), flush=True)
                except Exception:
                    logger.exception("Research worker cycle failed; retrying after poll interval")
                time.sleep(args.poll_seconds)
        except KeyboardInterrupt:
            return
    result = ResearchJobRunner(store, fetch_fulltext=args.fulltext).run_next()
    print(json.dumps(result or {"status": "queue_empty"}, default=str))


if __name__ == "__main__":
    main()

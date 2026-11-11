"""Local academic metadata checks, gated OKF staging, and reviewed publication."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "host_research"))

from archipelago.academic_automation import AcademicStore  # noqa: E402
from archipelago.academic_automation.candidate import (  # noqa: E402
    ALLOWED_LICENSES,
    enqueue_manifest,
)
from archipelago.academic_automation.discovery import discover_opac_query  # noqa: E402
from archipelago.academic_automation.gpu import gpu_snapshot  # noqa: E402
from archipelago.academic_automation.matching import match_repository  # noqa: E402
from archipelago.academic_automation.open_books import (  # noqa: E402
    PROVIDERS,
    find_open_book,
    harvest,
    queue_open_book,
)
from archipelago.academic_automation.publication import publish_reviewed  # noqa: E402
from archipelago.academic_automation.scan import scan_configured_queries  # noqa: E402
from archipelago.academic_automation.scheduler import sync_sources  # noqa: E402
from archipelago.academic_automation.worker import run_once  # noqa: E402

WORKER_POLL_SECONDS = 30
DAILY_HARVEST_PAGES = 5
STATE_PATH = Path(
    os.getenv(
        "ARCHIPELAGO_ACADEMIC_STATE", str(ROOT / "data" / "academic_automation" / "state.sqlite3")
    )
)


def _sources(include_opac: bool) -> dict[str, Any]:
    from koha_snapshot import build_snapshot
    from opac_daily import fetch_daily_opac

    def koha() -> list[dict[str, Any]]:
        return list(build_snapshot(ROOT / "data" / "koha")["holdings"])

    def pearson() -> list[dict[str, Any]]:
        raw = json.loads(
            (ROOT / "data" / "catalogs" / "pearson_bookshelf.json").read_text(encoding="utf-8")
        )
        rows = raw.get("books", []) if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            raise ValueError("Pearson bookshelf must contain books")
        return rows

    sources = {"koha_export": koha, "pearson_bookshelf": pearson}
    if include_opac:
        sources["opac_arrivals"] = lambda: list(fetch_daily_opac()["new_arrivals"])
    return sources


def _queue_open_book(store: AcademicStore, record_key: str) -> dict[str, Any]:
    """Re-verify the indexed match, then explicitly download and queue its eligible PDF."""
    record = next((r for r in store.match_rows() if r["record_key"] == record_key), None)
    if record is None:
        raise ValueError("Unknown record key")
    hits = find_open_book(
        store,
        record_key,
        str(record["title"]),
        str(record.get("isbn") or ""),
        str(record.get("author") or ""),
    )
    eligible = [h for h in hits if h["eligible_extraction"] and h["provider"] == "oapen"]
    if not eligible:
        return {
            "queued": False,
            "evidence": [{k: h[k] for k in ("provider", "content_status", "reason")} for h in hits],
        }
    return {"queued": True, "job_id": queue_open_book(store, ROOT, eligible[0])}


def _sync(store: AcademicStore, *, include_opac: bool) -> list[dict[str, Any]]:
    """Reconcile configured metadata feeds without withdrawing on failure."""
    output = sync_sources(store, _sources(include_opac))
    try:
        from repository_feed import discover_repository_items

        repository_items, _metadata = discover_repository_items()
        matched = match_repository(store, repository_items)
        store.provider_result("institutional_repository")
        output.append(
            {"provider": "institutional_repository", "status": "metadata_only", "matches": matched}
        )
    except (OSError, ValueError, ImportError, requests.RequestException) as exc:
        store.provider_result("institutional_repository", error=type(exc).__name__)
        output.append(
            {
                "provider": "institutional_repository",
                "status": "unavailable",
                "error": type(exc).__name__,
            }
        )
    return output


def _auto_publish_eligible(store: AcademicStore, worker: dict[str, Any]) -> dict[str, Any] | None:
    """Publish only validated PDF evidence with real pages and complete provenance."""
    operator = os.getenv("ARCHIPELAGO_ACADEMIC_REVIEWER", "").strip()
    if (
        worker.get("status") != "review_ready"
        or os.getenv("ARCHIPELAGO_ACADEMIC_AUTO_PUBLISH_OPEN") != "1"
        or not operator
    ):
        return None
    validation = worker.get("validation") or {}
    if (
        any(validation.get(key) for key in ("missing_concepts", "missing_edges"))
        or validation.get("added_concepts", 0) < 1
    ):
        return None
    job_id = str(worker["job_id"])
    job = store.job(job_id)
    if job is None or Path(str(job["content_path"])).suffix.lower() != ".pdf":
        return None
    path = ROOT / "data" / "academic_jobs" / job_id / "results.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not rows or any(
        not row.get("summary")
        or not row.get("section_title")
        or not isinstance(row.get("page_number"), int)
        or row["page_number"] < 1
        or row.get("source_license") not in ALLOWED_LICENSES
        for row in rows
    ):
        return None
    return publish_reviewed(store, job_id, ROOT, reviewer=f"automated_quality_gate:{operator}")


def daily_cycle(
    store: AcademicStore, *, skip_live_opac: bool = False, auto_publish_reviewed_open: bool = False
) -> dict[str, Any]:
    """Run one bounded daily discovery cycle, then at most one consent-gated job."""
    store.audit("scheduler", "daily_cycle_started", "queue", {})
    sync = _sync(store, include_opac=not skip_live_opac)
    scan: dict[str, Any] | None = None
    if not skip_live_opac:
        try:
            scan = scan_configured_queries(
                store, ROOT, ROOT / "data/academic_automation/opac_queries.json"
            )
        except (OSError, ValueError, requests.RequestException) as exc:
            store.provider_result("opac_live", error=type(exc).__name__)
            scan = {"status": "unavailable", "error": type(exc).__name__}
    harvests = [
        harvest(store, provider, max_pages=DAILY_HARVEST_PAGES) for provider in ("doab", "oapen")
    ]
    with store._connect() as db:
        eligible = db.execute(
            "SELECT count(*) FROM jobs WHERE status IN ('awaiting_approval','approved','cpu_requested')"
        ).fetchone()[0]
    new_records = sum(int(outcome.get("counts", {}).get("new", 0)) for outcome in sync)
    if scan:
        new_records += int(scan.get("reconciliation", {}).get("counts", {}).get("new", 0))
    if not eligible:
        store.audit(
            "scheduler",
            "daily_cycle_noop",
            "queue",
            {"new_records": new_records, "eligible_jobs": 0},
        )
        store.provider_result("daily_cycle")
        return {
            "status": "noop",
            "sync": sync,
            "scan": scan,
            "harvests": harvests,
            "eligible_jobs": 0,
        }
    worker = run_once(store, ROOT)
    publication = (
        _auto_publish_eligible(store, worker) if auto_publish_reviewed_open and worker else None
    )
    store.provider_result("daily_cycle")
    return {
        "status": "processed",
        "sync": sync,
        "scan": scan,
        "harvests": harvests,
        "eligible_jobs": eligible,
        "worker": worker,
        "publication": publication,
    }


def main() -> int:
    """Execute one explicit local operation; no command silently starts GPU work."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--skip-live-opac", action="store_true")
    cycle = sub.add_parser("daily-cycle")
    cycle.add_argument("--skip-live-opac", action="store_true")
    cycle.add_argument("--auto-publish-reviewed-open", action="store_true")
    discover = sub.add_parser("discover")
    discover.add_argument("--query", required=True)
    discover.add_argument("--offset", type=int, default=0)
    discover.add_argument("--max-records", type=int, default=20)
    configured = sub.add_parser("scan-configured")
    configured.add_argument(
        "--queries-file", type=Path, default=ROOT / "infrastructure" / "academic-opac-queries.json"
    )
    harvest_cmd = sub.add_parser("harvest")
    harvest_cmd.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    harvest_cmd.add_argument("--max-pages", type=int, default=50)
    open_cmd = sub.add_parser("queue-open-book")
    open_cmd.add_argument("--record-key", required=True)
    sub.add_parser("worker-once")
    sub.add_parser("worker-loop")
    sub.add_parser("status")
    queue = sub.add_parser("queue")
    queue.add_argument("manifest", type=Path)
    publish = sub.add_parser("publish")
    publish.add_argument("job_id")
    publish.add_argument("--reviewer", required=True)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("job_id")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("grant_id")
    args = parser.parse_args()
    store = AcademicStore(STATE_PATH)
    if args.command == "sync":
        output = _sync(store, include_opac=not args.skip_live_opac)
    elif args.command == "daily-cycle":
        output = daily_cycle(
            store,
            skip_live_opac=args.skip_live_opac,
            auto_publish_reviewed_open=args.auto_publish_reviewed_open,
        )
    elif args.command == "discover":
        output = discover_opac_query(
            store, ROOT, args.query, offset=args.offset, max_records=args.max_records
        )
    elif args.command == "harvest":
        output = harvest(store, args.provider, max_pages=args.max_pages)
    elif args.command == "queue-open-book":
        output = _queue_open_book(store, args.record_key)
    elif args.command == "scan-configured":
        output = scan_configured_queries(store, ROOT, args.queries_file)
    elif args.command == "worker-once":
        store.recover_stale()
        output = run_once(store, ROOT)
    elif args.command == "worker-loop":
        while True:
            store.recover_stale()
            output = run_once(store, ROOT)
            print(json.dumps(output or {"status": "idle"}, sort_keys=True), flush=True)
            time.sleep(WORKER_POLL_SECONDS)
    elif args.command == "queue":
        output = {"job_id": enqueue_manifest(store, ROOT, args.manifest)}
    elif args.command == "publish":
        output = publish_reviewed(store, args.job_id, ROOT, reviewer=args.reviewer)
    elif args.command == "cancel":
        output = {"cancelled": store.cancel(args.job_id, "local_operator")}
    elif args.command == "revoke":
        output = {"revoked": store.revoke(args.grant_id, "local_operator")}
    else:
        output = {**store.dashboard(), "gpu": gpu_snapshot()}
    print(json.dumps(output, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Automated twice-daily scholarly discovery and manifest synchronization.

Executes 2 times per day (every 12 hours):
1. Concurrent 4-way parallel harvest (arXiv, UEMK OPAC, IEM CRP, Google Scholar).
2. Source-labeled manifests for downstream chat and library pages.
3. Manifest-only synchronization to Hugging Face and Vercel.

Supports:
- Daemon mode (`--daemon`) for continuous 12-hour background execution.
- Single execution (`--run-once`) for programmatic or ad-hoc runs.
- System crontab generation/installation (`--install-cron` / `--print-cron`).
- Status inspection (`--status`).
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Any

from archipelago.scholarly.discovery.scholar_deeplink import generate_scholar_url
from archipelago.scholarly.pipeline.cloud_sync import CloudSyncPipeline
from archipelago.scholarly.pipeline.parallel_harvester import ParallelHarvester

logger = logging.getLogger("archipelago.scholarly.scheduler")

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
STATUS_LOG_PATH = DATA_DIR / "catalogs/scheduler_status.json"

DEFAULT_TOPICS = [
    "deep learning architectures",
    "computer networks",
    "data structures and algorithms",
    "distributed systems",
    "natural language processing",
]

TWELVE_HOURS_SECONDS = 12 * 3600


class HarvestScheduler:
    """Manage periodic discovery and manifest synchronization."""

    def __init__(
        self,
        interval_hours: float = 12.0,
        topics: list[str] | None = None,
        use_api_anything: bool = True,
    ):
        self.interval_seconds = int(interval_hours * 3600)
        self.topics = topics or DEFAULT_TOPICS
        self.harvester = ParallelHarvester(use_api_anything=use_api_anything)
        self.cloud_sync = CloudSyncPipeline()
        self._stop_event = threading.Event()

    def run_cycle(self) -> dict[str, Any]:
        """Run discovery and sync manifests without changing SLM training data."""
        cycle_start = time.time()
        start_str = datetime.datetime.now(datetime.UTC).isoformat()
        logger.info(
            "================================================================================"
        )
        logger.info("Starting scholarly discovery cycle: %s", start_str)
        logger.info(
            "================================================================================"
        )

        total_canonical = 0
        harvest_summaries = []
        manifests: list[dict[str, Any]] = []

        # Harvest across topics
        for topic in self.topics:
            logger.info(">>> Processing Topic: '%s'", topic)
            try:
                res = self.harvester.harvest_parallel(topic, limit_per_source=4, persist=False)
                total_canonical += res.get("total_canonical", 0)
                manifests.append(res["manifest"])
                harvest_summaries.append(
                    {
                        "query": topic,
                        "source_status": res["source_status"],
                        "total_canonical": res["total_canonical"],
                    }
                )
            except Exception as e:
                logger.error("Failed processing topic '%s': %s", topic, e)

        if manifests:
            combined = dict(manifests[-1])
            combined["query"] = ", ".join(self.topics)
            combined["scholar_verification_url"] = generate_scholar_url(combined["query"])
            for field in ("items", "resources"):
                unique = {
                    (entry["source"], entry["id"]): entry
                    for manifest in manifests
                    for entry in manifest[field]
                }
                combined[field] = list(unique.values())
            combined["total_cataloged"] = len(combined["items"])
            for source in combined["source_status"]:
                statuses = [manifest["source_status"][source] for manifest in manifests]
                live_count = sum(status["live_records"] for status in statuses)
                fallback_count = sum(status["fallback_records"] for status in statuses)
                combined["source_status"][source] = {
                    "mode": "live"
                    if live_count
                    else "fallback"
                    if fallback_count
                    else "link_only"
                    if source == "google_scholar"
                    else "unavailable",
                    "live_records": live_count,
                    "fallback_records": fallback_count,
                    "content_type": statuses[-1]["content_type"],
                }
            combined["source_status"]["google_scholar"]["verification_url"] = combined[
                "scholar_verification_url"
            ]
            self.harvester._update_live_manifests(combined, time.time() - cycle_start)

        # Publish discovery metadata only. SLM datasets and models are a later stage.
        logger.info(">>> Synchronizing discovery manifests...")
        sync_result: dict[str, Any] = {}
        try:
            sync_result = {
                "huggingface": self.cloud_sync.sync_to_huggingface(
                    upload_datasets=False, upload_manifests=True, upload_lora_adapters=False
                ),
                "vercel": self.cloud_sync.sync_to_vercel(),
            }
        except Exception as e:
            logger.error("Cloud synchronization failed: %s", e)
            sync_result = {"status": "error", "error": str(e)}

        elapsed = time.time() - cycle_start
        cycle_summary = {
            "last_run_timestamp": start_str,
            "duration_seconds": round(elapsed, 2),
            "topics_processed": len(self.topics),
            "total_canonical_records": total_canonical,
            "new_slm_training_pairs": 0,
            "ingestion_status": "not_started",
            "harvests": harvest_summaries,
            "cloud_sync": sync_result,
            "status": "completed",
        }

        # Save scheduler status
        STATUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(cycle_summary, f, indent=2)

        logger.info(
            "================================================================================"
        )
        logger.info(
            "Discovery cycle complete in %.2fs. %d topics searched.",
            elapsed,
            len(harvest_summaries),
        )
        logger.info(
            "================================================================================"
        )
        return cycle_summary

    def run_daemon(self) -> None:
        """Run as a persistent daemon executing every 12 hours (2x per day)."""
        logger.info(
            "Starting 2x/Day Harvest Daemon. Execution interval: %.1f hours (%d seconds).",
            self.interval_seconds / 3600,
            self.interval_seconds,
        )

        def _handle_exit(sig: int, frame: Any) -> None:
            logger.info("Received signal %s. Shutting down daemon gracefully...", sig)
            self._stop_event.set()

        signal.signal(signal.SIGINT, _handle_exit)
        signal.signal(signal.SIGTERM, _handle_exit)

        while not self._stop_event.is_set():
            try:
                self.run_cycle()
            except Exception as e:
                logger.error("Unhandled error during harvest cycle: %s", e)

            if self._stop_event.is_set():
                break

            next_run_dt = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                seconds=self.interval_seconds
            )
            logger.info(
                "Sleeping until next 12-hour cycle (Next run at: %s)...", next_run_dt.isoformat()
            )

            # Sleep in short increments to respond quickly to termination signals
            sleep_chunks = self.interval_seconds // 5
            for _ in range(sleep_chunks):
                if self._stop_event.is_set():
                    break
                time.sleep(5)

    def print_crontab_entry(self) -> str:
        """Generate standard crontab entry for 2x/day execution at 00:00 and 12:00."""
        python_bin = sys.executable
        log_file = DATA_DIR / "catalogs/cron_harvest.log"
        cron_line = f"0 0,12 * * * cd {ROOT} && {python_bin} -m archipelago.scholarly.pipeline.scheduler --run-once >> {log_file} 2>&1"
        return cron_line

    def install_crontab(self) -> bool:
        """Install or update the 2x/day cron entry in user crontab."""
        cron_line = self.print_crontab_entry()
        cron_marker = "# ARCHIPELAGO_2X_DAILY_HARVEST"
        tagged_line = f"{cron_line} {cron_marker}"

        try:
            current_crontab = ""
            res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if res.returncode == 0:
                current_crontab = res.stdout

            # Remove previous Archipelago harvest lines
            lines = [line for line in current_crontab.splitlines() if cron_marker not in line]
            lines.append(tagged_line)
            new_crontab = "\n".join(lines).strip() + "\n"

            # Write updated crontab
            write_res = subprocess.run(
                ["crontab", "-"], input=new_crontab, text=True, capture_output=True
            )
            if write_res.returncode == 0:
                logger.info("Successfully installed 2x/day crontab entry:\n%s", tagged_line)
                return True
            else:
                logger.error("Failed to install crontab: %s", write_res.stderr)
                return False
        except Exception as e:
            logger.error("Error updating crontab: %s", e)
            return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archipelago Scholarly 2x/Day Harvest & Ingestion Scheduler"
    )
    parser.add_argument(
        "--daemon", action="store_true", help="Run continuously in background (every 12 hours)"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute one complete harvest, stack-up, and cloud sync cycle now",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=12.0,
        help="Interval in hours for daemon mode (default: 12.0 = 2x/day)",
    )
    parser.add_argument(
        "--install-cron",
        action="store_true",
        help="Install standard 2x/day crontab entry (00:00, 12:00)",
    )
    parser.add_argument(
        "--print-cron", action="store_true", help="Print the crontab configuration line"
    )
    parser.add_argument("--status", action="store_true", help="Display last run status and metrics")
    parser.add_argument("--topic", type=str, action="append", help="Specific topic(s) to harvest")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.status:
        if STATUS_LOG_PATH.is_file():
            with open(STATUS_LOG_PATH, encoding="utf-8") as f:
                print(json.dumps(json.load(f), indent=2))
        else:
            print("No previous scheduler runs found at:", STATUS_LOG_PATH)
        return

    scheduler = HarvestScheduler(
        interval_hours=args.interval_hours,
        topics=args.topic,
    )

    if args.print_cron:
        print("\n--- Standard 2x/Day Crontab Entry ---")
        print(scheduler.print_crontab_entry())
        print()
        return

    if args.install_cron:
        ok = scheduler.install_crontab()
        if ok:
            print("✅ 2x/Day cron job successfully installed.")
        else:
            print("❌ Failed installing crontab. You can add this line manually:")
            print(scheduler.print_crontab_entry())
        return

    if args.run_once:
        scheduler.run_cycle()
        return

    if args.daemon:
        scheduler.run_daemon()
        return

    # Default if no arguments provided: print usage or run once
    parser.print_help()


if __name__ == "__main__":
    main()

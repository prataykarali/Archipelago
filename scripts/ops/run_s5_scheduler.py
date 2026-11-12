"""Run one bounded pass of the independent S5 metadata monitor queue."""

from __future__ import annotations

import logging

from archipelago.scholarly.intelligence.monitor import run_monitor
from archipelago.scholarly.intelligence.postgres_storage import PostgresResearchStore

MAX_MONITORS_PER_PASS = 4


def main() -> int:
    """Claim due monitors and execute each one with provider budgets."""
    logging.basicConfig(level=logging.INFO)
    store = PostgresResearchStore()
    for monitor_id in store.due_monitor_ids(MAX_MONITORS_PER_PASS):
        outcome = run_monitor(monitor_id, store)
        logging.info("S5 monitor %s: %s", monitor_id, outcome["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

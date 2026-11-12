"""Run one explicitly enabled S5 monitor from an operator scheduler."""

from __future__ import annotations

import argparse
import json

from archipelago.scholarly.intelligence.monitor import run_monitor
from archipelago.scholarly.intelligence.storage import ResearchStore


def main() -> None:
    """Print a bounded status record for external scheduling and alerts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("monitor_id")
    args = parser.parse_args()
    print(json.dumps(run_monitor(args.monitor_id, ResearchStore()), sort_keys=True))


if __name__ == "__main__":
    main()

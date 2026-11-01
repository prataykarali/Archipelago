"""Publish changed Koha ODS metadata from the local authorized export folder."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host_research"))
from koha_snapshot import build_snapshot, load_snapshot, save_snapshot  # noqa: E402
from opac_daily import fetch_daily_opac  # noqa: E402
from repository_feed import discover_repository_items  # noqa: E402


def main() -> int:
    """Validate four exports, publish changed metadata, and report staleness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "data" / "koha")
    parser.add_argument("--env-file", type=Path, default=ROOT / "host_inference" / ".env")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.env_file.is_file():
        for name, value in dotenv_values(args.env_file).items():
            if value is not None:
                os.environ.setdefault(name, value)
    snapshot = build_snapshot(args.directory)
    exports = snapshot["exports"]
    assert isinstance(exports, dict)
    repository_status = "available"
    try:
        candidates, metadata = discover_repository_items()
        snapshot["repository_candidates"] = candidates
        exports["repository_feed"] = {
            "source_url": metadata["source_url"],
            "sha256": metadata["sha256"],
            "count": metadata["count"],
        }
        snapshot["repository_checked_at"] = metadata["fetched_at"]
    except (requests.RequestException, ValueError) as exc:
        repository_status = f"unavailable:{type(exc).__name__}"
        if not args.dry_run:
            previous = load_snapshot()
            if previous:
                snapshot["repository_candidates"] = previous.get("repository_candidates", [])
                previous_exports = previous.get("exports")
                if isinstance(previous_exports, dict) and "repository_feed" in previous_exports:
                    exports["repository_feed"] = previous_exports["repository_feed"]
                snapshot["repository_checked_at"] = previous.get("repository_checked_at")
    opac_status = "available"
    try:
        opac = fetch_daily_opac()
        snapshot["opac_daily"] = opac
        exports["opac_daily"] = {
            "sha256": opac["sha256"],
            "checked_at": opac["checked_at"],
            "count": len(opac["sections"]) + len(opac["new_arrivals"]),
        }
    except (requests.RequestException, ValueError) as exc:
        opac_status = f"unavailable:{type(exc).__name__}"
        if not args.dry_run:
            previous = load_snapshot()
            if previous:
                snapshot["opac_daily"] = previous.get("opac_daily")
                previous_exports = previous.get("exports")
                if isinstance(previous_exports, dict) and "opac_daily" in previous_exports:
                    exports["opac_daily"] = previous_exports["opac_daily"]
    changed = False if args.dry_run else save_snapshot(snapshot)
    print(
        json.dumps(
            {
                "changed": changed,
                "dry_run": args.dry_run,
                "stale": snapshot["stale"],
                "source_updated_at": snapshot["source_updated_at"],
                "repository_status": repository_status,
                "opac_status": opac_status,
                "repository_candidates": len(snapshot.get("repository_candidates", [])),
                "counts": {
                    key: len(snapshot[key])
                    for key in ("holdings", "journal_issues", "subject_counts", "subject_titles")
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

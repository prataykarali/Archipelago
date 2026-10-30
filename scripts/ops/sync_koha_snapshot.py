"""Publish changed Koha ODS metadata from the local authorized export folder."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host_research"))
from koha_snapshot import build_snapshot, save_snapshot  # noqa: E402


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
    changed = False if args.dry_run else save_snapshot(snapshot)
    print(
        json.dumps(
            {
                "changed": changed,
                "dry_run": args.dry_run,
                "stale": snapshot["stale"],
                "source_updated_at": snapshot["source_updated_at"],
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

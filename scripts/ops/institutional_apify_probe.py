"""Run or resume one bounded public institutional Apify source probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from archipelago.ingestion.institutional_apify import probe_public_source


def main() -> None:
    """Write a source-labelled result without storing the Apify token."""
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=("opac", "iemcrp"))
    parser.add_argument("--query", default="computer science")
    parser.add_argument("--run-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_dotenv(override=False)
    result = probe_public_source(args.source, query=args.query, run_id=args.run_id)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "source": result["source"],
                "source_status": result["source_status"],
                "run_id": result["actor_run"].get("run_id"),
                "dataset_items": result["dataset_items"],
                "records": len(result["records"]),
                "failure_state": result.get("failure_state"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

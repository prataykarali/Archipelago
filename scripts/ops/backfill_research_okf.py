"""Refresh one completed research session from its stored metadata and abstracts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from archipelago.scholarly.bridge.supabase_store import ResearchQueueStore  # noqa: E402
from archipelago.scholarly.extraction.abstract_fields import extract_abstract_fields  # noqa: E402
from archipelago.scholarly.extraction.structured_okf import build_paper_okf  # noqa: E402

PAPER_SELECT = "paper_id,okf"
RECORD_SELECT = (
    "record_key,kind,title,source_name,source_url,topic,content,published_at,metadata,updated_at"
)
MAX_PAPERS = 30


def backfill(store: ResearchQueueStore, job_id: str) -> dict[str, int]:
    """Rebuild OKF for saved papers without fetching or downloading a PDF."""
    job_rows = store._request(
        "GET",
        "research_processing_jobs",
        params={"job_id": f"eq.{job_id}", "select": "job_id,topic,status", "limit": 1},
    )
    if not job_rows or job_rows[0]["status"] not in {"completed", "partial"}:
        raise ValueError("A completed research job is required")
    papers = store._request(
        "GET",
        "research_processing_papers",
        params={"job_id": f"eq.{job_id}", "select": PAPER_SELECT, "limit": MAX_PAPERS},
    )
    counts: Counter[str] = Counter()
    for paper in papers or []:
        key = (paper.get("okf") or {}).get("paper_key")
        if not key:
            continue
        rows = store._request(
            "GET",
            "research_intake_records",
            params={"record_key": f"eq.{key}", "select": RECORD_SELECT, "limit": 1},
        )
        if not rows:
            counts["missing_record"] += 1
            continue
        record: dict[str, Any] = rows[0]
        record["metadata"] = dict(record.get("metadata") or {})
        record["metadata"]["verified_extractions"] = extract_abstract_fields(
            str(record.get("content") or "")
        )
        okf = build_paper_okf(record, job_rows[0]["topic"])
        store._request(
            "PATCH",
            "research_intake_records",
            params={"record_key": f"eq.{key}"},
            headers={"Prefer": "return=minimal"},
            json={"metadata": record["metadata"], "updated_at": datetime.now(UTC).isoformat()},
        )
        store._request(
            "PATCH",
            "research_processing_papers",
            params={"job_id": f"eq.{job_id}", "paper_id": f"eq.{paper['paper_id']}"},
            headers={"Prefer": "return=minimal"},
            json={"okf": okf},
        )
        counts["papers"] += 1
        counts["abstract_facts"] += len(record["metadata"]["verified_extractions"])
    return dict(counts)


def main() -> None:
    """Refresh a selected completed job in the user's existing Supabase project."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    print(backfill(ResearchQueueStore(), args.job_id))


if __name__ == "__main__":
    main()

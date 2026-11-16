"""Exercise live scholarly discovery and validate both research workbook modes."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from archipelago.scholarly.intelligence.search import discover  # noqa: E402
from archipelago.scholarly.intelligence.workbook import build_workbook  # noqa: E402
from archipelago.scholarly.intelligence.workbook_standard import STANDARD_SHEETS  # noqa: E402

OUTPUT = ROOT / "outputs" / "research-overhaul-20261116"
TOPICS = (
    ("state-space models in machine learning", 100),
    ("retrieval augmented generation", 20),
    ("CRISPR gene editing", 20),
)
BANNED = ("PROVIDER_UNAVAILABLE", "LICENSE_RESTRICTED", "IDENTITY_REVIEW_REQUIRED", "NOT_AVAILABLE")


def _audit_workbook(path: Path, expected_sheets: int) -> dict[str, Any]:
    book = load_workbook(path)
    assert len(book.sheetnames) == expected_sheets, book.sheetnames
    if expected_sheets == len(STANDARD_SHEETS):
        assert tuple(book.sheetnames) == STANDARD_SHEETS
        titles: set[str] = set()
        for row in book["Papers"].iter_rows(min_row=2, values_only=True):
            title = str(row[0] or "").casefold().strip()
            assert title and title not in titles, title
            titles.add(title)
        for sheet in book:
            for row in sheet:
                for cell in row:
                    assert cell.data_type != "f", (sheet.title, cell.coordinate)
                    if isinstance(cell.value, str):
                        assert not any(code in cell.value for code in BANNED), (
                            sheet.title,
                            cell.coordinate,
                        )
        assert book["Papers"].auto_filter.ref
        assert book["Papers"].freeze_panes == "A2"
        return {
            "sheets": book.sheetnames,
            "papers": len(titles),
            "authors": book["Authors"].max_row - 1,
        }
    return {"sheets": book.sheetnames}


def main() -> None:
    """Run three unrelated live searches and write a verified paired export."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    audits: list[dict[str, Any]] = []
    for topic, limit in TOPICS:
        run = discover({"topic": topic, "top_k": limit, "sort": "relevance"})
        if topic == TOPICS[0][0]:
            (OUTPUT / "state_space_live_run.json").write_text(
                json.dumps(run, indent=2, default=str)
            )
        sources = [source for source in run["sources"] if source["status"] != "skipped"]
        if not any(source["status"] in {"live", "live_partial"} for source in sources):
            raise RuntimeError(f"No live provider records for {topic}")
        audit: dict[str, Any] = {
            "topic": topic,
            "requested_count": limit,
            "retrieved_at": run["retrieved_at"],
            "candidate_count": run["candidate_count"],
            "filtered_count": run["filtered_count"],
            "returned_count": len(run["papers"]),
            "methods": sum(bool(p.get("methods")) for p in run["papers"]),
            "datasets": sum(bool(p.get("datasets")) for p in run["papers"]),
            "evaluation_metrics": sum(bool(p.get("evaluation_metrics")) for p in run["papers"]),
            "sources": [
                source.summary() if hasattr(source, "summary") else source for source in sources
            ],
            "waterfall": (run.get("provider_selection") or {}).get("waterfall") or {},
        }
        if topic == TOPICS[0][0]:
            for mode, expected in (("standard", 5), ("advanced", 14)):
                path = OUTPUT / f"Archipelago_State_Space_Models_{mode.title()}.xlsx"
                path.write_bytes(build_workbook(run, mode=mode).getvalue())
                audit[mode] = _audit_workbook(path, expected)
                audit[f"{mode}_file"] = str(path)
        audits.append(audit)
        print(
            json.dumps(
                {
                    "topic": topic,
                    "returned": audit["returned_count"],
                    "sources": [(s["source"], s["status"], s["record_count"]) for s in sources],
                }
            ),
            flush=True,
        )
        (OUTPUT / "live_audit.json").write_text(json.dumps(audits, indent=2, default=str))


if __name__ == "__main__":
    main()

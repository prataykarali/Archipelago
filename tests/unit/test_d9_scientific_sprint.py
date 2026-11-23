"""D9 privacy, reblinding, and scientific integrity gates."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "research" / "d5_sigir_evaluation"
EXPECTED_ITEMS = 731


@pytest.mark.unit
def test_reblind_packets_are_fresh_blank_and_external(tmp_path: Path) -> None:
    """Fresh IDs never reuse legacy IDs and reviewer grades remain blank."""
    output = tmp_path / "packets"
    subprocess.run(
        [sys.executable, str(EVAL / "reblind_and_prepare_packets.py"), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    legacy = json.loads((EVAL / "worksheets" / "pool_key_SEALED.json").read_text())
    key = json.loads((output / "private" / "sealed_key.json").read_text())
    assert len(key["items"]) == EXPECTED_ITEMS
    assert {entry["blinded_candidate_id"] for entry in key["items"].values()}.isdisjoint(
        {entry["blinded_candidate_id"] for entry in legacy["entries"].values()}
    )
    assert (output / "private" / "sealed_key.json").stat().st_mode & 0o077 == 0
    for reviewer in ("A", "B"):
        with (output / f"reviewer_{reviewer}_packet.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == EXPECTED_ITEMS
        assert all(not row["relevance_grade"] and not row["reviewer_id"] for row in rows)


@pytest.mark.unit
def test_post_annotation_refuses_blank_grades(tmp_path: Path) -> None:
    """No human metrics file may be emitted before genuine completed worksheets."""
    output = tmp_path / "packets"
    subprocess.run(
        [sys.executable, str(EVAL / "reblind_and_prepare_packets.py"), "--output", str(output)],
        check=True,
        capture_output=True,
    )
    report = tmp_path / "human_metrics.json"
    run = subprocess.run(
        [
            sys.executable,
            str(EVAL / "post_annotation_analysis.py"),
            "--packets",
            str(output),
            "--output",
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode != 0
    assert "missing or invalid grade" in run.stderr
    assert not report.exists()


@pytest.mark.unit
def test_frozen_q45_is_compilers() -> None:
    """Frozen Q45 remains the compiler question throughout D9."""
    queries = json.loads((EVAL / "queries_heldout_50.json").read_text())
    q45 = next(item for item in queries if item["query_id"] == "Q45")
    assert q45["query"] == "How do compilers transform source code into machine instructions?"

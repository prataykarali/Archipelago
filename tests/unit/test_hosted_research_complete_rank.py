"""Verify the hosted workbook and chat use complete, linked research records."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit
HOST = Path(__file__).resolve().parents[2] / "host_inference"


def test_hosted_rank_has_no_missing_cells_and_chat_links_saved_papers() -> None:
    """Exercise the actual Vercel package rather than the repository package."""
    script = """
import runpy
from openpyxl import load_workbook
from archipelago.scholarly.intelligence.workbook import build_workbook
from archipelago.scholarly.intelligence.run_dossier import build_run_dossier
from hostapp.research_run_chat import FIND, _list

run = runpy.run_path('../tests/unit/test_standard_research_xlsx.py')['_sample_run']()
run_id = '1697862f-dd1e-4250-932d-06cea52c5d4c'
book = load_workbook(build_workbook(run), data_only=True)
assert book.sheetnames == ['Start Here', 'Papers', 'Authors', 'Sources']
for name in ('Papers', 'Authors'):
    rows = list(book[name].values)
    assert rows[1:]
    assert all(value is not None and value != '' for row in rows[1:] for value in row)
headers = [cell.value for cell in book['Papers'][1]]
assert 'Discovery Fit Score (%)' in headers
assert 'FWCI (OpenAlex)' not in headers
dossier = build_run_dossier(run)
assert len(dossier['papers']) == book['Papers'].max_row - 1
assert sorted(p['rankable_values'][headers.index('Discovery Rank')] for p in dossier['papers']) == [1, 2]
assert FIND.search('recommend me 30 papers on space state model').group('count') == '30'
assert f'/research/paper?run={run_id}&paper=0' in _list(run, run_id)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=HOST,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

"""Check positional Kùzu export rows and multi-result responses."""

from __future__ import annotations

import json

import pytest

from okf.exports_extra import export_gold_template


class FakeResult:
    def __init__(self, rows: list[list[object]]) -> None:
        self.rows = iter(rows)
        self.next_row: list[object] | None = None

    def has_next(self) -> bool:
        if self.next_row is None:
            self.next_row = next(self.rows, None)
        return self.next_row is not None

    def get_next(self) -> list[object]:
        assert self.next_row is not None
        row = self.next_row
        self.next_row = None
        return row


class FakeConnection:
    def execute(self, query: str) -> FakeResult | list[FakeResult]:
        if "REQUIRES" in query:
            return [FakeResult([["concept-a", "Prerequisite"]])]
        if "UNLOCKS" in query or "RELATED" in query:
            return FakeResult([])
        return FakeResult(
            [["doc-a", "chunk-a", "concept-a", "Concept A", "definition", "intro", "Summary"]]
        )


@pytest.mark.unit
def test_gold_export_accepts_positional_multi_result_rows(tmp_path) -> None:
    output = tmp_path / "gold.json"
    export_gold_template(FakeConnection(), output)

    concepts = json.loads(output.read_text())[0]["concepts"]
    assert concepts[0]["concept_name"] == "Concept A"
    assert concepts[0]["prerequisites"] == ["Prerequisite"]

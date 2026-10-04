"""Idempotent transactional spreadsheet writes against a real isolated Kuzu database."""

from __future__ import annotations

import kuzu
import pytest

from archipelago.inference import state
from archipelago.ingestion import spreadsheet

pytestmark = pytest.mark.integration


def test_real_graph_append_update_idempotence_and_rollback(tmp_path, monkeypatch):
    db = kuzu.Database(str(tmp_path / "inventory.kuzu"))
    conn = kuzu.Connection(db)
    conn.execute("""CREATE NODE TABLE Resource (
        id STRING PRIMARY KEY, title STRING, author STRING, publisher STRING,
        copyright_year INT64, biblionumber STRING, total_copies INT64,
        available_copies INT64, overdue_items INT64, is_periodical BOOLEAN)""")
    monkeypatch.setattr(state, "db", db)
    path = tmp_path / "inventory.csv"
    path.write_text(
        "Title,Author,Total Copies,Available Copies,Call Number,Shelf\nBook A,A,3,2,QA184,4\nBook B,B,2,1,QA185,5\n"
    )
    first = spreadsheet.apply_merge(path, dry_run=False)
    assert first["success"] and first["writes_performed"] == 2
    assert conn.execute(
        "MATCH (r:Resource {id:'res_book_a'}) RETURN r.call_number, r.shelf"
    ).get_next() == ["QA184", "4"]
    second = spreadsheet.apply_merge(path, dry_run=False)
    assert second["success"] and second["writes_performed"] == 0 and second["idempotent"]
    path.write_text("Title,Author,Total Copies,Available Copies\nBook A,A,3,1\nBook B,B,2,1\n")
    third = spreadsheet.apply_merge(path, dry_run=False)
    assert third["success"] and third["writes_performed"] == 1
    assert conn.execute("MATCH (r:Resource) RETURN count(r)").get_next()[0] == 2
    original = spreadsheet._resource_params

    def failing(change):
        statement, params = original(change)
        if change.title == "Book D":
            return "INVALID CYPHER", params
        return statement, params

    monkeypatch.setattr(spreadsheet, "_resource_params", failing)
    path.write_text("Title,Author,Total Copies,Available Copies\nBook C,C,1,1\nBook D,D,1,1\n")
    result = spreadsheet.apply_merge(path, dry_run=False)
    assert not result["success"] and not result["applied"] and result["writes_performed"] == 0
    assert conn.execute("MATCH (r:Resource) RETURN count(r)").get_next()[0] == 2
    conn.close()
    db.close()

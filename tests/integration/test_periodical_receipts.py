"""A real Kùzu import retains each serial issue's source receipt status."""

from __future__ import annotations

import kuzu
import pytest

from archipelago.inference.ods_ingestion import ingest_ods_journal_report

pytestmark = pytest.mark.integration

ISSUE_HEADERS = [
    "Journal Title",
    "Issue Number/Volume",
    "Published Date",
    "Issue Status",
]


def _rows(first_status: str) -> list[list[str]]:
    return [
        ISSUE_HEADERS,
        ["Journal A", "Vol. 2 Issue 3", "2026-10-01", first_status],
        ["Journal A", "Vol. 2 Issue 3", "2026-10-01", first_status],
        ["Journal B", "Issue 4", "2026-10-02", ""],
        ["Journal C", "", "2026-10-03", "Expected"],
    ]


def test_issue_receipts_deduplicate_and_update_status(tmp_path) -> None:
    database = kuzu.Database(str(tmp_path / "periodicals.db"))
    conn = kuzu.Connection(database)
    try:
        first = ingest_ods_journal_report(conn, _rows("Late"))
        assert first["receipts_upserted"] == 2
        assert first["receipts_dropped"] == 1
        result = conn.execute(
            "MATCH (r:JournalReceipt) RETURN r.journal_title, r.status ORDER BY r.journal_title"
        )
        assert result.get_next() == ["Journal A", "Late"]
        assert result.get_next() == ["Journal B", "Unknown"]
        assert not result.has_next()

        corrected = _rows("Received")
        corrected[1][2] = "2026-10-04"
        corrected[2][2] = "2026-10-04"
        second = ingest_ods_journal_report(conn, corrected)
        assert second["receipts_upserted"] == 2
        result = conn.execute(
            "MATCH (r:JournalReceipt) RETURN r.journal_title, r.status ORDER BY r.journal_title"
        )
        assert result.get_next() == ["Journal A", "Received"]
        assert result.get_next() == ["Journal B", "Unknown"]
        assert not result.has_next()

        publication = conn.execute(
            "MATCH (r:JournalReceipt) WHERE r.journal_title = 'Journal A' RETURN r.published_date"
        )
        assert publication.get_next() == ["2026-10-04"]

        count = conn.execute(
            "MATCH (j:JournalReport) WHERE j.journal_title = 'Journal A' RETURN j.issue_count"
        )
        assert count.get_next() == [1]
    finally:
        database.close()


def test_aggregate_journal_report_does_not_invent_issue_receipts(tmp_path) -> None:
    database = kuzu.Database(str(tmp_path / "aggregate.db"))
    conn = kuzu.Connection(database)
    try:
        report = ingest_ods_journal_report(
            conn,
            [
                ["Journal Title", "ISSN", "Issue Count", "Publisher"],
                ["Journal D", "1234-5678", "5", "Publisher D"],
            ],
        )
        assert report["inserted"] == 1
        assert report["receipts_upserted"] == 0
        count = conn.execute("MATCH (r:JournalReceipt) RETURN count(r)")
        assert count.get_next() == [0]
    finally:
        database.close()

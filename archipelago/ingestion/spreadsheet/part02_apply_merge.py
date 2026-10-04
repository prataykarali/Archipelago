"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import _deps as _rt  # noqa: F401


def apply_merge(
    path: str | Path,
    record_type: str = "resource",
    dry_run: bool = True,
    retire_missing: bool = False,
) -> dict[str, Any]:
    """Apply a spreadsheet merge. Idempotent: re-running yields UNCHANGED only."""
    plan = _rt.plan_merge(path, record_type=record_type, retire_missing=retire_missing)
    writes: list[dict[str, Any]] = []
    if not dry_run and not plan.errors:
        writes = _write_plan(plan, record_type)
    summary = plan.summary()
    summary["applied"] = not dry_run and not plan.errors
    summary["dry_run"] = dry_run
    summary["retire_missing"] = retire_missing
    summary["writes_performed"] = len(writes)
    summary["success"] = not plan.errors
    summary["idempotent"] = all(
        c["outcome"] in (_rt.OUTCOME_UNCHANGED, _rt.OUTCOME_RETIRE)
        for c in summary["changes"]
    )
    return summary


def _subject_params(change: _rt.RecordChange) -> tuple[str, dict[str, Any]]:
    """MERGE statement + params for a Subject node."""
    f = change.fields
    return (
        "MERGE (s:Subject {id: $id, subject_name: $name, total_titles: $total})",
        {
            "id": change.record_id,
            "name": f.get("title", ""),
            "total": _rt._to_int(f.get("total_copies")),
        },
    )


def _resource_params(change: _rt.RecordChange) -> tuple[str, dict[str, Any]]:
    """MERGE statement + params for a Resource node."""
    f = change.fields
    year_match = _rt._YEAR_RE.search(str(f.get("year") or ""))
    return (
        "MERGE (r:Resource {"
        "id: $id, title: $title, author: $author, publisher: $publisher, "
        "copyright_year: $year, biblionumber: $isbn, total_copies: $total, "
        "available_copies: $available, overdue_items: $overdue, "
        "is_periodical: $periodical})",
        {
            "id": change.record_id,
            "title": f.get("title", ""),
            "author": f.get("author", ""),
            "publisher": f.get("publisher", ""),
            "year": int(year_match.group(1)) if year_match else 0,
            "isbn": f.get("isbn", ""),
            "total": _rt._to_int(f.get("total_copies")),
            "available": _rt._to_int(f.get("available_copies")),
            "overdue": _rt._to_int(f.get("overdue_items")),
            "periodical": bool(f.get("is_periodical")),
        },
    )


def _update_statements(record_type: str) -> tuple[str, str]:
    """(subject SET, resource SET) statements used for in-place updates."""
    if record_type == "subject":
        return (
            "MATCH (s:Subject {id: $id}) SET s.subject_name = $name, s.total_titles = $total",
            "",
        )
    return (
        "",
        "MATCH (r:Resource {id: $id}) SET "
        "r.title = $title, r.author = $author, r.publisher = $publisher, "
        "r.copyright_year = $year, r.biblionumber = $isbn, r.total_copies = $total, "
        "r.available_copies = $available, r.overdue_items = $overdue, "
        "r.is_periodical = $periodical",
    )


def _write_plan(plan: _rt.MergePlan, record_type: str) -> list[dict[str, Any]]:
    """Upsert each CREATE/UPDATE row; UNCHANGED and RETIRE are no-ops.

    Kùzu's MERGE fails on an existing primary key, so an update is a
    MATCH…SET and a create is a MERGE. That keeps the whole operation idempotent.
    """
    from archipelago.inference.graph_lock import graph_lock

    written: list[dict[str, Any]] = []
    pending = [c for c in plan.changes if c.outcome in (_rt.OUTCOME_CREATE, _rt.OUTCOME_UPDATE)]
    if not pending:
        return written
    try:
        import kuzu

        from archipelago.inference import state as st
        if getattr(st, "db", None) is None:
            plan.errors.append("Graph database unavailable; nothing was written.")
            return written
        builder = _rt._subject_params if record_type == "subject" else _rt._resource_params
        subject_set, resource_set = _update_statements(record_type)
        update_stmt = subject_set if record_type == "subject" else resource_set
        with graph_lock.write_lock():
            conn = kuzu.Connection(st.db)
            from archipelago.ingestion.catalog_locations import ensure_fields, store_fields

            if record_type == "resource":
                ensure_fields(conn)
            conn.execute("BEGIN TRANSACTION")
            try:
                for change in pending:
                    merge_stmt, params = builder(change)
                    if change.outcome == _rt.OUTCOME_UPDATE:
                        conn.execute(update_stmt, params)
                    else:
                        conn.execute(merge_stmt, params)
                    if record_type == "resource":
                        store_fields(conn, change.record_id, change.fields)
                    written.append({"record_id": change.record_id, "outcome": change.outcome})
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                written.clear()
                raise
    except Exception as exc:
        plan.errors.append(f"Merge aborted: {exc}")
    return written

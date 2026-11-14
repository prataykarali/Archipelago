"""S6 Privacy-Preserving Library Analytics & Institutional Source Audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
import hashlib
import json
import sqlite3
from typing import Any
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ALLOWED_SOURCES = frozenset(
    {
        "staff_manual_counter",
        "koha_circulation_sync",
        "qr_gate_adapter",
        "inventory_audit",
        "academic_event_log",
    }
)
ALLOWED_EVENT_TYPES = frozenset(
    {
        "entry_count",
        "exit_count",
        "checkin_count",
        "occupancy_snapshot",
        "circulation_issue",
        "circulation_return",
        "inventory_check",
        "academic_event",
    }
)
FORBIDDEN_PII_KEYS = frozenset(
    {
        "student_id",
        "patron_id",
        "user_id",
        "email",
        "full_name",
        "name",
        "phone",
        "mobile",
        "roll_number",
        "card_number",
        "borrower_id",
        "ip_address",
    }
)
MAX_EVENT_QUANTITY = 100_000
MAX_CATEGORY_LEN = 120
MAX_KEY_LEN = 160
DEFAULT_TIMEZONE = "Asia/Kolkata"
NOT_CONNECTED = "Data source not connected"


def resolve_timezone(tz_name: str | None) -> tuple[ZoneInfo, str]:
    """Return a valid ZoneInfo object and its canonical name."""
    candidate = (tz_name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(candidate), candidate
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise ValueError("invalid_timezone") from exc


def normalize_utc_timestamp(raw: object) -> str:
    """Parse an ISO-8601 timestamp and normalize it to UTC ISO format."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("invalid_occurred_at")
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("invalid_occurred_at") from exc
    parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return parsed.isoformat()


def _reject_pii(payload: dict[str, Any]) -> None:
    for key in payload:
        if str(key).strip().lower() in FORBIDDEN_PII_KEYS:
            raise ValueError(f"pii_field_forbidden:{key}")
    metadata = payload.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("invalid_metadata")
        for key in metadata:
            if str(key).strip().lower() in FORBIDDEN_PII_KEYS:
                raise ValueError(f"pii_field_forbidden:{key}")


def validate_library_event(payload: object, actor_id: str) -> dict[str, Any]:
    """Validate, sanitize, and normalize a privacy-preserving library analytics event."""
    if not isinstance(payload, dict):
        raise ValueError("invalid_event_payload")
    _reject_pii(payload)
    src = str(payload.get("source_id") or "").strip()
    if src not in ALLOWED_SOURCES:
        raise ValueError("invalid_source_id")
    etype = str(payload.get("event_type") or "").strip()
    if etype not in ALLOWED_EVENT_TYPES:
        raise ValueError("invalid_event_type")
    qty = payload.get("quantity")
    if isinstance(qty, bool) or not isinstance(qty, int) or not 0 <= qty <= MAX_EVENT_QUANTITY:
        raise ValueError("invalid_quantity")
    occ = normalize_utc_timestamp(payload.get("occurred_at"))
    cat = str(payload.get("subject_category") or "").strip()[:MAX_CATEGORY_LEN]
    is_demo = bool(payload.get("is_demo", False))
    raw_key = str(payload.get("idempotency_key") or "").strip()
    if raw_key and len(raw_key) > MAX_KEY_LEN:
        raise ValueError("invalid_idempotency_key")
    ikey = raw_key or hashlib.sha256(f"{src}:{etype}:{occ}:{cat}:{qty}:{is_demo}".encode()).hexdigest()[:40]
    meta = {
        str(k)[:40]: (str(v)[:200] if not isinstance(v, (int, float, bool)) else v)
        for k, v in (payload.get("metadata") or {}).items()
    }
    return {
        "id": str(uuid.uuid4()),
        "idempotency_key": ikey,
        "source_id": src,
        "event_type": etype,
        "subject_category": cat or None,
        "quantity": qty,
        "occurred_at": occ,
        "recorded_by": str(actor_id),
        "is_demo": is_demo,
        "metadata": meta,
    }


def _ensure_sqlite_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS s6_library_events ("
        "id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, source_id TEXT NOT NULL, "
        "event_type TEXT NOT NULL, subject_category TEXT, quantity INTEGER NOT NULL, "
        "occurred_at TEXT NOT NULL, recorded_by TEXT NOT NULL, is_demo INTEGER NOT NULL, "
        "metadata TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS s6_analytics_audit_log ("
        "id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, action TEXT NOT NULL, "
        "source_id TEXT NOT NULL, event_id TEXT, created_at TEXT NOT NULL)"
    )


def record_event(store: Any, payload: object, actor_id: str) -> dict[str, Any]:
    """Validate and persist an analytics event with deduplication and audit logging."""
    ev = validate_library_event(payload, actor_id)
    if hasattr(store, "_rpc"):
        return {**store._rpc("record_library_event", ev), "event": ev}
    if not hasattr(store, "path"):
        raise RuntimeError("analytics_storage_not_configured")
    now_iso = datetime.now(UTC).isoformat()
    vals = (
        ev["id"], ev["idempotency_key"], ev["source_id"], ev["event_type"], ev["subject_category"],
        ev["quantity"], ev["occurred_at"], ev["recorded_by"], int(ev["is_demo"]), json.dumps(ev["metadata"]), now_iso,
    )
    with store._connect() as conn:
        _ensure_sqlite_tables(conn)
        cur = conn.execute("INSERT OR IGNORE INTO s6_library_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", vals)
        ins = cur.rowcount == 1
        if ins:
            conn.execute(
                "INSERT INTO s6_analytics_audit_log VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), str(actor_id), f"record_{ev['event_type']}", ev["source_id"], ev["id"], now_iso),
            )
    return {"inserted": ins, "deduplicated": not ins, "event_id": ev["id"], "event": ev}


def fetch_events(
    store: Any,
    *,
    is_demo: bool = False,
    source_id: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch filtered library analytics events and recent audit logs."""
    src, fts, tts = (source_id or "").strip(), (normalize_utc_timestamp(from_ts) if from_ts else ""), (normalize_utc_timestamp(to_ts) if to_ts else "")
    if hasattr(store, "_rpc"):
        res = store._rpc("list_library_events", {"is_demo": bool(is_demo), "source_id": src, "from_ts": fts, "to_ts": tts})
        return list(res.get("events") or []), list(res.get("audit") or [])
    if not hasattr(store, "path"):
        return [], []
    with store._connect() as conn:
        _ensure_sqlite_tables(conn)
        rows = conn.execute(
            "SELECT id, idempotency_key, source_id, event_type, subject_category, quantity, occurred_at, is_demo, created_at "
            "FROM s6_library_events WHERE is_demo = ? AND (? = '' OR source_id = ?) AND (? = '' OR occurred_at >= ?) "
            "AND (? = '' OR occurred_at <= ?) ORDER BY occurred_at DESC LIMIT 500",
            (int(bool(is_demo)), src, src, fts, fts, tts, tts),
        ).fetchall()
        aud = conn.execute("SELECT id, action, source_id, event_id, created_at FROM s6_analytics_audit_log ORDER BY created_at DESC LIMIT 50").fetchall()
    return [{**dict(r), "is_demo": bool(r["is_demo"])} for r in rows], [dict(a) for a in aud]


SOURCE_META = (
    ("physical_entry_exit", "Physical Library Entry & Exit Counts", "staff_manual_counter / qr_gate_adapter", "Automated optical turnstiles are not connected. Website traffic and book loans are never counted as physical visits."),
    ("qr_attendance", "Check-ins & QR Attendance", "qr_gate_adapter", "Requires campus QR attendance scanner export or webhook."),
    ("occupancy", "Current & Historical Occupancy", "staff_manual_counter", "Real-time room occupancy sensors are not connected."),
    ("circulation", "Book Circulation, Borrowing & Returns", "koha_circulation_sync", "Reflects catalog copy availability and staff circulation notes; never conflated with physical footfall."),
    ("inventory_activity", "Library Inventory & Subject Catalogue Activity", "inventory_audit", "Keyword-filtered Koha holdings, journal issues, and subject-wise title counts."),
    ("academic_events", "Academic Event Participation", "academic_event_log", "Populated only when staff log verified library seminars or workshops."),
)


def audit_sources(
    koha_snapshot: dict[str, Any] | None,
    staff_records: dict[str, list[dict[str, Any]]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return honest institutional source connection status without fabricating feeds."""
    bt = Counter(str(e.get("event_type")) for e in events)
    hc = len(koha_snapshot.get("holdings") or []) if koha_snapshot else 0
    foot, circ = bt["entry_count"] + bt["exit_count"], bt["circulation_issue"] + bt["circulation_return"]
    counts = {
        "physical_entry_exit": (foot > 0, foot),
        "qr_attendance": (bt["checkin_count"] > 0, bt["checkin_count"]),
        "occupancy": (bt["occupancy_snapshot"] > 0, bt["occupancy_snapshot"]),
        "circulation": (bool(koha_snapshot or staff_records.get("circulation") or circ), hc + len(staff_records.get("circulation") or []) + circ),
        "inventory_activity": (bool(koha_snapshot or staff_records.get("catalog") or bt["inventory_check"]), hc + len(staff_records.get("catalog") or []) + bt["inventory_check"]),
        "academic_events": (bt["academic_event"] > 0, bt["academic_event"]),
    }
    out: list[dict[str, Any]] = []
    for cat, label, adapter, note in SOURCE_META:
        conn, cnt = counts[cat]
        is_koha = cat in {"circulation", "inventory_activity"}
        status = (("Connected (Authorized Koha ODS + Staff Log)" if koha_snapshot else "Staff Log Only") if is_koha and conn else ("Verified events present" if conn else NOT_CONNECTED))
        row: dict[str, Any] = {"category": cat, "label": label, "connected": conn, "status": status, "adapter": adapter, "records_count": cnt, "note": note}
        if is_koha:
            row["last_updated_at"] = (koha_snapshot or {}).get("source_updated_at")
            row["stale"] = bool((koha_snapshot or {}).get("stale", True))
        out.append(row)
    return out


def build_analytics_summary(
    *,
    koha_snapshot: dict[str, Any] | None,
    staff_records: dict[str, list[dict[str, Any]]],
    events: list[dict[str, Any]],
    audit_log: list[dict[str, Any]],
    tz_name: str | None = None,
    include_demo: bool = False,
) -> dict[str, Any]:
    """Aggregate verified library analytics with explicit missing-source states."""
    tz, canonical_tz = resolve_timezone(tz_name)
    daily_entries: dict[str, int] = defaultdict(int)
    hourly: dict[int, int] = dict.fromkeys(range(24), 0)
    monthly: dict[str, dict[str, int]] = defaultdict(lambda: {"entries": 0, "circulation": 0, "events": 0})
    subjects, totals = Counter[str](), Counter[str]()
    occ_snaps: list[tuple[str, int]] = []
    for item in events:
        etype, qty = str(item.get("event_type") or ""), int(item.get("quantity") or 0)
        try:
            dt = datetime.fromisoformat(str(item.get("occurred_at") or "").replace("Z", "+00:00")).astimezone(tz)
        except ValueError:
            continue
        day_key, month_key = dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m")
        hourly[dt.hour] += qty
        totals[etype] += qty
        if etype in {"entry_count", "checkin_count"}:
            daily_entries[day_key] += qty
            monthly[month_key]["entries"] += qty
        elif etype == "occupancy_snapshot":
            occ_snaps.append((dt.isoformat(), qty))
        elif etype in {"circulation_issue", "circulation_return"}:
            monthly[month_key]["circulation"] += qty
        else:
            monthly[month_key]["events"] += qty
        if cat := str(item.get("subject_category") or "").strip():
            subjects[cat] += qty
    holdings = (koha_snapshot or {}).get("holdings") or []
    total_copies = available_copies = 0
    for row in holdings:
        if isinstance(row, dict):
            try:
                tot = max(0, int(str(row.get("No. of copies") or 0).strip()))
                total_copies += tot
                available_copies += min(tot, max(0, int(str(row.get("Available Copies") or 0).strip())))
            except ValueError:
                continue
    for row in (koha_snapshot or {}).get("subject_counts") or []:
        if isinstance(row, dict) and (subj := str(row.get("Subject") or "").strip()):
            try:
                if (cnt := int(str(row.get("Total Titles") or 0).strip())) > 0:
                    subjects[subj] += cnt
            except ValueError:
                continue
    peak = max(hourly.items(), key=lambda kv: kv[1]) if any(hourly.values()) else None
    foot_ok, occ_ok = (totals["entry_count"] + totals["checkin_count"]) > 0, len(occ_snaps) > 0
    circ_ok = bool(koha_snapshot or totals["circulation_issue"] or totals["circulation_return"])
    return {
        "schema": "archipelago.s6.library_analytics.v1", "generated_at": datetime.now(UTC).isoformat(),
        "timezone": canonical_tz, "demo_isolated": not include_demo, "include_demo": include_demo,
        "sources": audit_sources(koha_snapshot, staff_records, events),
        "physical_footfall": {
            "status": "connected" if foot_ok else NOT_CONNECTED,
            "total_entries": totals["entry_count"] if foot_ok else None, "total_exits": totals["exit_count"] if foot_ok else None,
            "total_qr_checkins": totals["checkin_count"] if totals["checkin_count"] > 0 else None,
            "daily_entries": [{"date": d, "entries": c} for d, c in sorted(daily_entries.items())],
            "hourly_activity": [{"hour": f"{h:02d}:00", "count": c} for h, c in sorted(hourly.items())] if peak else [],
            "peak_period": f"{peak[0]:02d}:00-{(peak[0] + 1) % 24:02d}:00 ({peak[1]} events)" if peak else NOT_CONNECTED,
        },
        "occupancy": {"status": "connected" if occ_ok else NOT_CONNECTED, "current_occupancy": occ_snaps[0][1] if occ_ok else None, "last_measured_at": occ_snaps[0][0] if occ_ok else None},
        "circulation": {
            "status": "connected" if circ_ok else NOT_CONNECTED, "koha_catalog_titles": len(holdings),
            "koha_total_copies": total_copies, "koha_available_copies": available_copies,
            "koha_checked_out_copies": max(0, total_copies - available_copies),
            "recorded_issue_events": totals["circulation_issue"], "recorded_return_events": totals["circulation_return"],
            "staff_circulation_notes": len(staff_records.get("circulation") or []), "staff_catalog_notes": len(staff_records.get("catalog") or []),
            "staff_order_notes": len(staff_records.get("orders") or []), "staff_fine_notes": len(staff_records.get("fines") or []),
            "journal_issues_tracked": len((koha_snapshot or {}).get("journal_issues") or []),
        },
        "subject_categories": [{"subject": n, "count": c} for n, c in subjects.most_common(12)],
        "monthly_trends": [{"month": m, **v} for m, v in sorted(monthly.items())],
        "freshness": {
            "koha_source_updated_at": (koha_snapshot or {}).get("source_updated_at"), "koha_oldest_export_at": (koha_snapshot or {}).get("oldest_export_at"),
            "koha_stale": bool((koha_snapshot or {}).get("stale", True)), "latest_event_at": events[0].get("occurred_at") if events else None, "events_in_window": len(events),
        },
        "data_quality_notes": [
            "Website traffic and online chat queries are never counted as physical library visits.",
            "Book circulation (Koha checked-out copies and loan logs) is reported separately from physical footfall.",
            "Personally identifying patron fields (student ID, email, name, phone) are rejected at ingestion.",
            "Automated optical gate and room occupancy sensors are marked 'Data source not connected' until linked.",
        ],
        "audit_log": audit_log[:25],
    }

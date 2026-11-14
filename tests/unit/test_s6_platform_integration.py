"""S6 Platform Integration, Live Library Analytics, Review Guards & Data-Quality Tests."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from archipelago.scholarly.discovery.crossref_adapter import CrossrefAdapter, _clean_author_name
from archipelago.scholarly.discovery.openalex_adapter import OpenAlexAdapter
from archipelago.scholarly.intelligence.analytics import (
    NOT_CONNECTED,
    build_analytics_summary,
    fetch_events,
    record_event,
    validate_library_event,
)
from archipelago.scholarly.intelligence.storage import ResearchStore

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


@pytest.fixture
def s6_hosted_app(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_DB", str(tmp_path / "s6_research.sqlite3"))
    import engine as hosted_engine

    class Graph:
        graph_version = "9818ac0e8fd3"
        corpus_source = "full"
        nodes = {  # noqa: RUF012
            "graph_retrieval": {"summary": "Retrieval over a graph."},
            "embeddings": {"summary": "Vector representations."},
        }
        out = {"graph_retrieval": [("REQUIRES", "embeddings")]}  # noqa: RUF012
        inn = {"embeddings": [("UNLOCKS", "graph_retrieval")]}  # noqa: RUF012

        def rank(self, query, top_k=1):
            return [(0.9, "graph_retrieval")]

        def label(self, node_id):
            return node_id.replace("_", " ").title()

    fake_engine = SimpleNamespace(graph=Graph(), books=[], cache_info={"source": "supabase"})
    monkeypatch.setattr(hosted_engine, "Engine", lambda: fake_engine)
    sys.modules.pop("server", None)
    server = importlib.import_module("server")
    yield server
    sys.modules.pop("server", None)


def test_author_name_cleaning_and_corporate_fallback():
    assert _clean_author_name("Qing Wang,mying Li") == "Qing Wang, mying Li"
    assert _clean_author_name("  Asela   Hevapathige &amp; Co. ; ") == "Asela Hevapathige & Co."

    cr = CrossrefAdapter()
    transformed = cr._transform_item(
        {
            "DOI": "10.1000/test",
            "title": ["Test Corporate Author"],
            "author": [
                {"name": "IEEE Standards Association"},
                {"given": "Qing", "family": "Wang"},
            ],
        },
        "a" * 64,
    )
    names = [a.name for a in transformed["paper"].authors]
    assert names == ["IEEE Standards Association", "Qing Wang"]

    oa = OpenAlexAdapter()
    oa_item = oa._transform_item(
        {
            "id": "https://openalex.org/W123",
            "title": "Test OA",
            "authorships": [
                {"author": {"display_name": "Qing  Wang,mying Li"}, "institutions": []}
            ],
        },
        "b" * 64,
    )
    assert oa_item["paper"].authors[0].name == "Qing Wang, mying Li"


def test_analytics_honest_not_connected_and_no_footfall_conflation(tmp_path):
    store = ResearchStore(tmp_path / "analytics.sqlite3")
    koha_snap = {
        "source": "authorized_koha_ods_export",
        "source_updated_at": "2026-11-10T00:00:00+00:00",
        "stale": False,
        "holdings": [
            {"biblionumber": "1", "Title": "OS", "No. of copies": "10", "Available Copies": "6"},
            {"biblionumber": "2", "Title": "DBMS", "No. of copies": "5", "Available Copies": "5"},
        ],
        "subject_counts": [{"Subject": "Computer Science", "Total Titles": "42"}],
        "journal_issues": [{"Journal Title": "IEEE Spectrum"}],
    }
    events, audit = fetch_events(store, is_demo=False)
    summary = build_analytics_summary(
        koha_snapshot=koha_snap,
        staff_records={"circulation": [{"record_key": "1", "status": "issued"}]},
        events=events,
        audit_log=audit,
        tz_name="Asia/Kolkata",
    )
    # Physical footfall & occupancy must honestly state Data source not connected
    # even when Koha book loans and circulation records exist!
    assert summary["physical_footfall"]["status"] == NOT_CONNECTED
    assert summary["physical_footfall"]["total_entries"] is None
    assert summary["occupancy"]["status"] == NOT_CONNECTED
    assert summary["occupancy"]["current_occupancy"] is None
    assert summary["circulation"]["status"] == "connected"
    assert summary["circulation"]["koha_total_copies"] == 15
    assert summary["circulation"]["koha_available_copies"] == 11
    assert summary["circulation"]["koha_checked_out_copies"] == 4
    assert summary["subject_categories"][0] == {"subject": "Computer Science", "count": 42}


@pytest.mark.parametrize(
    "pii_payload",
    [
        {
            "source_id": "staff_manual_counter",
            "event_type": "entry_count",
            "quantity": 5,
            "occurred_at": "2026-11-14T06:00:00Z",
            "student_id": "S123",
        },
        {
            "source_id": "qr_gate_adapter",
            "event_type": "checkin_count",
            "quantity": 1,
            "occurred_at": "2026-11-14T06:00:00Z",
            "email": "reader@iem.edu.in",
        },
        {
            "source_id": "staff_manual_counter",
            "event_type": "entry_count",
            "quantity": 2,
            "occurred_at": "2026-11-14T06:00:00Z",
            "metadata": {"patron_id": "P99"},
        },
    ],
)
def test_analytics_rejects_pii_fields(pii_payload):
    with pytest.raises(ValueError, match="pii_field_forbidden"):
        validate_library_event(pii_payload, "actor-1")


def test_analytics_deduplication_demo_isolation_and_timezone(tmp_path):
    store = ResearchStore(tmp_path / "analytics.sqlite3")
    payload = {
        "idempotency_key": "gate-batch-001",
        "source_id": "staff_manual_counter",
        "event_type": "entry_count",
        "quantity": 18,
        "subject_category": "AI & ML",
        "occurred_at": "2026-11-14T04:30:00Z",  # 10:00 IST
        "is_demo": False,
    }
    first = record_event(store, payload, "lib-1")
    second = record_event(store, payload, "lib-1")
    assert first["inserted"] is True
    assert second["inserted"] is False
    assert second["deduplicated"] is True

    # Record a demo event and verify it never leaks into production summary
    record_event(
        store,
        {
            "idempotency_key": "demo-batch-999",
            "source_id": "staff_manual_counter",
            "event_type": "entry_count",
            "quantity": 500,
            "occurred_at": "2026-11-14T05:30:00Z",
            "is_demo": True,
        },
        "lib-1",
    )
    prod_events, prod_audit = fetch_events(store, is_demo=False)
    assert len(prod_events) == 1
    assert prod_events[0]["quantity"] == 18
    assert len(prod_audit) >= 1

    summary = build_analytics_summary(
        koha_snapshot=None,
        staff_records={},
        events=prod_events,
        audit_log=prod_audit,
        tz_name="Asia/Kolkata",
    )
    assert summary["physical_footfall"]["status"] == "connected"
    assert summary["physical_footfall"]["total_entries"] == 18
    assert "10:00-11:00 (18 events)" in summary["physical_footfall"]["peak_period"]


def test_s6_routes_role_guards_and_s4_review_protection(s6_hosted_app, monkeypatch):
    from hostapp.routes import analytics as analytics_routes

    ctx = s6_hosted_app.app.extensions["archipelago"]
    monkeypatch.setattr(ctx.limiter, "check_api", lambda: (False, 0))
    role = {"id": "user-1", "role": "student"}
    monkeypatch.setattr(
        ctx.auth,
        "principal",
        lambda: (role if role["role"] else None, "unauthenticated"),
    )
    monkeypatch.setattr(
        analytics_routes,
        "_load_s4_snapshot",
        lambda _b: {
            "configured": True,
            "dashboard": {
                "jobs": [
                    {"job_id": "bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe", "status": "review_ready"}
                ]
            },
            "reviews": {
                "bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe": {
                    "job_id": "bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe",
                    "status": "review_ready",
                    "publication_status": "BLOCKED",
                    "review_digest": "0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77",
                    "rows": [{"concept_name": "Convexity"}],
                    "edges": [
                        {"from_id": "convex_sets", "to_id": "convex_functions", "type": "REQUIRES"}
                    ],
                }
            },
        },
    )
    client = s6_hosted_app.app.test_client()

    # UI shells render cleanly
    assert client.get("/analytics").status_code == 200
    assert client.get("/librarian").status_code == 200
    assert client.get("/librarian/analytics").status_code == 200
    assert client.get("/academic/graph").status_code == 200
    assert client.get("/academic-automation").status_code == 200

    # Student role blocked from analytics and S4 review
    assert client.get("/api/analytics/summary").status_code == 403
    assert client.post("/api/analytics/events", json={}).status_code == 403
    assert client.get("/api/academic-automation/status").status_code == 403
    assert (
        client.get(
            "/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe"
        ).status_code
        == 403
    )

    # Faculty can view analytics summary and S4 status, but cannot write events or decide S4 review
    role["role"] = "faculty"
    assert client.get("/api/analytics/summary").status_code == 200
    assert client.post("/api/analytics/events", json={}).status_code == 403
    assert client.get("/api/academic-automation/status").status_code == 200
    assert (
        client.get(
            "/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe"
        ).status_code
        == 403
    )

    # Librarian can record verified events and inspect S4 review packet
    role["role"] = "librarian"
    ev_resp = client.post(
        "/api/analytics/events",
        json={
            "source_id": "staff_manual_counter",
            "event_type": "entry_count",
            "quantity": 12,
            "occurred_at": "2026-11-14T06:00:00Z",
        },
    )
    assert ev_resp.status_code == 201
    rev_resp = client.get("/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe")
    assert rev_resp.status_code == 200
    assert rev_resp.get_json()["publication_status"] == "BLOCKED"

    # S4 review decision guards: dev token -> 403, bad digest -> 400, reject without note -> 400
    dec_url = "/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe/decision"
    assert (
        client.post(
            dec_url,
            headers={"Authorization": "Bearer local-dev-token"},
            json={"decision": "approve", "review_digest": "0fba3b14"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            dec_url, json={"decision": "approve", "review_digest": "wrong-digest"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            dec_url,
            json={
                "decision": "reject",
                "review_digest": "0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77",
                "note": "   ",
            },
        ).status_code
        == 400
    )

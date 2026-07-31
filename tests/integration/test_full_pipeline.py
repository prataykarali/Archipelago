"""
test_full_pipeline.py — Integration Tests for Archipelago Catalog, Smart UI & Upload Estimation.
"""

import json
import pytest
from archipelago.inference.context_tracker import get_or_create_context, SESSION_CONTEXTS
from archipelago.inference.routes_misc import estimate_ingestion_time

pytestmark = pytest.mark.integration


def test_library_info_route(flask_test_client):
    """Verify library_info intent handles rules/timing queries and returns expected details."""
    payload = {"query": "Is the library open on weekends and what is the opac link?"}
    res = flask_test_client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.get_data(as_text=True)
    assert "24 \u00d7 7" in data or "24 \\u00d7 7" in data or "24 × 7" in data or "24 \u00d7 7 \u00d7 365" in data
    assert "uemk-opac.l2c2.co.in" in data
    assert "weekend" in data.lower() or "weekdays" in data.lower() or "saturday" in data.lower()


def test_library_info_lab_manuals(flask_test_client):
    """Lab-manual questions get the materials section with the B1 LG2.7 location."""
    payload = {"query": "Where are the lab manuals?"}
    res = flask_test_client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.get_data(as_text=True)
    assert "B1 LG2.7" in data


def test_estimate_ingestion_time_calculation():
    """Test ingestion duration estimation logic for various file sizes and extensions."""
    # Small PDF (~1 MB)
    est1 = estimate_ingestion_time(1 * 1024 * 1024, "paper.pdf")
    assert 20 <= est1["estimated_seconds"] <= 45
    assert "seconds" in est1["estimated_time_formatted"]

    # Medium PDF (~3 MB)
    est2 = estimate_ingestion_time(3 * 1024 * 1024, "book_chapter.pdf")
    assert est2["estimated_seconds"] > 50
    
    # Markdown file (~500 KB)
    est3 = estimate_ingestion_time(500 * 1024, "notes.md")
    assert est3["estimated_seconds"] >= 5


def test_context_status_endpoint(flask_test_client):
    """Test /api/context-status endpoint response format."""
    res = flask_test_client.get("/api/context-status?session_id=test_session_123")
    assert res.status_code == 200
    data = res.get_json()
    assert "session_id" in data
    assert data["session_id"] == "test_session_123"
    assert "shift_detected" in data
    assert "is_idle" in data
    assert "reading_trail" in data


def test_page_view_endpoint_structure(flask_test_client):
    """Test /api/page-view endpoint parameter validation and error handling."""
    res = flask_test_client.get("/api/page-view")
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data

    res_missing = flask_test_client.get("/api/page-view?doc_id=non_existent_doc_xyz")
    assert res_missing.status_code in (404, 500)

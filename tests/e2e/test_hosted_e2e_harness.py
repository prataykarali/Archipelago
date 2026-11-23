"""Unit and live-gated E2E tests for the hosted E2E verification harness (Issue #12).

Unit tests exercise the real byte validators, revision-vs-graph separation,
abstention checks, secret redaction, and strict verdict honesty rules.
Live hosted checks are gated behind ``RUN_LIVE_E2E=1``.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import sys

import openpyxl
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.e2e.hosted_e2e_checks import (  # noqa: E402
    JourneyResult,
    parse_chat_response,
    redact_evidence,
    verify_abstention_payload,
    verify_pdf_bytes,
    verify_readiness_separation,
    verify_xlsx_bytes,
)

MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
    b"4 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
    b"xref\n0 5\n0000000000 65535 f \n"
    b"trailer << /Size 5 /Root 1 0 R >>\nstartxref\n220\n%%EOF\n"
)


def _build_valid_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Papers"
    ws.append(["Title", "DOI", "Year"])
    ws.append(["Dense Passage Retrieval", "10.18653/v1/2020.emnlp-main.550", 2020])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.unit
def test_verify_pdf_bytes_accepts_valid_pdf_and_rejects_html() -> None:
    """Real PDF bytes pass validation; HTML error pages with HTTP 200 fail."""
    ok = verify_pdf_bytes(MINIMAL_PDF_BYTES, requested_page=2)
    assert ok["valid"] is True
    assert ok["has_pdf_magic"] is True
    assert ok["page_count"] == 2
    assert ok["page_in_range"] is True

    out_of_range = verify_pdf_bytes(MINIMAL_PDF_BYTES, requested_page=9)
    assert out_of_range["valid"] is False
    assert out_of_range["page_in_range"] is False

    html_fake = verify_pdf_bytes(b"<html><body>Not a PDF</body></html>", requested_page=1)
    assert html_fake["valid"] is False
    assert html_fake["has_pdf_magic"] is False


@pytest.mark.unit
def test_verify_xlsx_bytes_accepts_real_workbook_and_rejects_corrupt_bytes() -> None:
    """Real OOXML XLSX bytes pass validation; arbitrary bytes fail."""
    valid_bytes = _build_valid_xlsx_bytes()
    ok = verify_xlsx_bytes(valid_bytes)
    assert ok["valid"] is True
    assert ok["has_zip_magic"] is True
    assert ok["has_required_xml"] is True
    assert ok["has_worksheet_xml"] is True
    assert "Papers" in ok["sheet_names"]

    corrupt = verify_xlsx_bytes(b"not-a-zip-or-xlsx-file")
    assert corrupt["valid"] is False


@pytest.mark.unit
def test_verify_readiness_separation_distinguishes_revision_from_graph_fingerprint() -> None:
    """Deployed code revision must be tracked separately from graph_version fingerprint."""
    unversioned = verify_readiness_separation(
        headers={"X-Archipelago-Release": "unversioned", "X-Vercel-Id": "bom1::test"},
        payload={"graph_version": "9818ac0e8fd3", "concepts": 610, "corpus": {"source": "full"}},
    )
    assert unversioned["deployed_revision"] == "unversioned"
    assert unversioned["deployed_revision_versioned"] is False
    assert unversioned["graph_fingerprint"] == "9818ac0e8fd3"
    assert unversioned["revision_distinct_from_graph"] is True

    versioned = verify_readiness_separation(
        headers={"X-Archipelago-Release": "00f38b81351e"},
        payload={"graph_version": "9818ac0e8fd3", "concepts": 610},
    )
    assert versioned["deployed_revision_versioned"] is True
    assert versioned["revision_distinct_from_graph"] is True


@pytest.mark.unit
def test_parse_chat_response_handles_stream_start_and_abstention() -> None:
    """Stream-framed /api/chat metadata parses cleanly and verifies Q39 abstention."""
    framed = (
        '{"citations": [], "graph": {"nodes": [], "edges": []}, '
        '"trace": {"grounding_status": "no_verified_match", '
        '"provenance_status": "abstained", "claim_support_status": "not_assessed"}}'
        "[STREAM_START]Spanner TrueTime is outside the indexed corpus."
    )
    parsed = parse_chat_response(framed)
    abstain = verify_abstention_payload(parsed)
    assert abstain["clean_abstention"] is True
    assert abstain["citation_count"] == 0
    assert abstain["graph_node_count"] == 0
    assert abstain["graph_edge_count"] == 0
    assert abstain["claim_support_status"] == "not_assessed"


@pytest.mark.unit
def test_redact_evidence_strips_tokens_cookies_and_emails() -> None:
    """Evidence serialization must never leak emails, JWTs, bearer tokens, or cookies."""
    sample = {
        "auth": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature123456",
        "email": "student@uem.edu.in",
        "cookie": "archipelago_session=secret_cookie_val; Path=/",
        "key": "sb_publishable_ABC123xyz",
    }
    redacted = redact_evidence(sample)
    serialized = str(redacted)
    assert "student@uem.edu.in" not in serialized
    assert "secret_cookie_val" not in serialized
    assert "signature123456" not in serialized
    assert "ABC123xyz" not in serialized


@pytest.mark.unit
def test_journey_result_rejects_unknown_verdict() -> None:
    """Only PASS, FAIL, and BLOCKED are valid verdicts."""
    with pytest.raises(ValueError, match="Invalid verdict"):
        JourneyResult(
            journey_id="J1",
            title="Invalid",
            verdict="SOFT_PASS",
            environment="hosted_live",
            requires_auth=True,
        )


@pytest.mark.e2e
def test_live_hosted_e2e_harness_no_unexpected_failures() -> None:
    """Run live hosted harness when RUN_LIVE_E2E=1 is explicitly enabled."""
    if os.environ.get("RUN_LIVE_E2E", "").strip() != "1":
        pytest.skip("Set RUN_LIVE_E2E=1 to run live hosted E2E verification")
    from scripts.e2e.hosted_e2e_harness import execute_hosted_suite

    report = execute_hosted_suite(run_browser=True)
    assert report["metadata"]["summary"]["FAIL"] == 0
    j4 = next(j for j in report["journeys"] if j["journey_id"] == "J4")
    assert j4["verdict"] == "PASS"

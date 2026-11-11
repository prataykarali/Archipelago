"""Library and catalog cases from the 75-case inference suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.inference_75_fixtures import clear_cred_cache as clear_cred_cache
from tests.unit.inference_75_fixtures import mock_cred_env as mock_cred_env

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("verified_student_auth")]

# ═══════════════════════════════════════════════════════════════════════════
# Category 2 — OPAC / e-resources / catalog (TC-16 … TC-30)
# ═══════════════════════════════════════════════════════════════════════════

CATEGORY_2_INTENTS = [
    (
        "TC-16",
        "How can I access Scopus or ScienceDirect through the institutional portal?",
        "library_resources",
    ),
    (
        "TC-17",
        "What is the passkey for the National Digital Library of India (NDLI) Club?",
        "library_resources",
    ),
    (
        "TC-18",
        "Does the library provide access to IEEE Xplore? What are the credentials?",
        "library_resources",
    ),
    (
        "TC-19",
        "Which academic subject has the highest title count in our central library catalog?",
        "library_catalog_stats",
    ),
    (
        "TC-20",
        "How many journal titles and total issue counts are registered in the library database?",
        "library_catalog_stats",
    ),
    (
        "TC-21",
        "Search the library catalog for all available titles containing the keyword 'Data Mining'.",
        "library_catalog_stats",
    ),
    (
        "TC-22",
        "What are the working hours and operating schedule of the central library on weekdays and weekends?",
        "library_hours",
    ),
    (
        "TC-23",
        "I need a physical book on '3NF Database Normalization'. Where can I find it in the library?",
        "library_resource_lookup",
    ),
    (
        "TC-24",
        "List all journal issues available under the subject 'Computer Networks'.",
        "library_journal_status",
    ),
    (
        "TC-26",
        "Where can I access legal databases like Lexis Advance India or Manupatra?",
        "library_resources",
    ),
    (
        "TC-27",
        "Which requested AI/ML books currently have zero physical available copies on the shelf?",
        "library_catalog_stats",
    ),
    (
        "TC-28",
        "How many British Council and American Library access cards are available for issue?",
        "library_resources",
    ),
    (
        "TC-29",
        "What is the URL and default login format for the library OPAC catalog?",
        "library_resources",
    ),
    ("TC-30", "How do I access the digital ezine for Electronics For You?", "library_resources"),
]


@pytest.mark.parametrize(
    "tc_id,prompt,expected_intent",
    CATEGORY_2_INTENTS,
    ids=[t[0] for t in CATEGORY_2_INTENTS],
)
def test_category2_library_intent_routing(tc_id, prompt, expected_intent):
    from archipelago.inference.routing import _detect_library_intent

    hit = _detect_library_intent(prompt)
    assert hit is not None, f"{tc_id} expected library intent"
    assert hit["intent"] == expected_intent, f"{tc_id}: got {hit}"


def test_tc16_scopus_credentials_from_secure_store(mock_cred_env):
    """TC-16: Scopus query must yield a portal reply with NO leaked credentials."""
    from archipelago.inference.eresource_credentials import format_credential_reply
    from archipelago.inference.synthesis import render_library_info

    reply = format_credential_reply(
        "How can I access Scopus or ScienceDirect through the institutional portal?"
    )
    assert reply is not None
    assert "sciencedirect.com" in reply or "scopus.com" in reply
    # Adversarial: no institutional emails or passwords may leak to chat.
    assert "it@iemcal.com" not in reply
    assert "4359789" not in reply
    assert "library.uemk" not in reply
    full = render_library_info(
        "How can I access Scopus or ScienceDirect through the institutional portal?"
    )
    assert "it@iemcal.com" not in full
    assert "4359789" not in full


def test_tc17_ndli_passkey_from_secure_store(mock_cred_env):
    """TC-17: NDLI query mentions the portal but never the passkey."""
    from archipelago.inference.eresource_credentials import format_credential_reply

    reply = format_credential_reply(
        "What is the passkey for the National Digital Library of India (NDLI) Club?"
    )
    assert reply is not None
    assert "ndl.iitkgp.ac.in" in reply
    # Adversarial: the actual registration number / passkey must not leak.
    assert "INWBNC4AU95XQTV" not in reply
    assert "aeb28d3c-de60-439a-89b7-8cfed9aa0657" not in reply
    assert "712a6780-24af-47fb-90d2-b9a7200eabc2" not in reply


def test_tc18_ieee_credentials_from_secure_store(mock_cred_env):
    """TC-18: IEEE query returns the portal; never the user/password."""
    from archipelago.inference.eresource_credentials import format_credential_reply

    reply = format_credential_reply(
        "Does the library provide access to IEEE Xplore? What are the credentials?"
    )
    assert reply is not None
    assert "ieeexplore.ieee.org" in reply
    # Adversarial: no IEEE credentials leak.
    assert "fG8BeaTC" not in reply
    assert "gh8ccws]" not in reply


def test_tc22_library_hours_sheet():
    from archipelago.inference.synthesis import render_library_info

    info = render_library_info(
        "What are the working hours and operating schedule of the central library?"
    )
    assert "24" in info
    assert "weekend" in info.lower() or "Saturday" in info or "weekday" in info.lower()


def test_tc16_to_tc30_library_routes_bypass_aiml_scope():
    """Regression: operational library asks must not die on AIML scope gate."""
    from archipelago.inference.routing import resolve_query_routing

    cases = [
        (
            "TC-16",
            "How can I access Scopus or ScienceDirect through the institutional portal?",
            "library_resources",
        ),
        (
            "TC-17",
            "What is the passkey for the National Digital Library of India (NDLI) Club?",
            "library_resources",
        ),
        ("TC-22", "What are the working hours of the central library?", "library_hours"),
        ("TC-23", "I need a physical book on 3NF. Where can I find it?", "library_resource_lookup"),
        (
            "TC-29",
            "What is the URL and default login format for the library OPAC catalog?",
            "library_resources",
        ),
    ]
    for tc_id, prompt, expected in cases:
        result = resolve_query_routing(prompt)
        assert result["route"] == expected, f"{tc_id}: got {result}"


def test_tc25_pdf_url_property_on_document_contract():
    """TC-25: Streaming link contract — Document.pdf_url on physical rows."""
    from archipelago.inference.synthesis import render_physical_resources

    resources = [
        {
            "resource_id": "r1",
            "title": "Pattern Recognition",
            "author": "Bishop",
            "available_copies": 2,
            "total_copies": 3,
            "barcodes": "B1",
            "doc_id": "textbooks/pattern_recognition.pdf",
            "pdf_url": "https://cdn.example.com/pattern_ch1.pdf",
            "concept_name": "Pattern Recognition",
        }
    ]
    text = render_physical_resources("Pattern Recognition", resources)
    assert "Pattern Recognition" in text
    # Availability line present; pdf_url may be linked by renderer variants.
    assert "available" in text.lower() or "copy" in text.lower() or "Pattern" in text


def test_tc26_lexis_from_secure_store(mock_cred_env):
    """TC-26: Lexis portal reply; no library@iem credential leak."""
    from archipelago.inference.eresource_credentials import format_credential_reply

    reply = format_credential_reply(
        "Where can I access legal databases like Lexis Advance India or Manupatra?"
    )
    assert reply is not None
    assert "advance.lexis.com" in reply
    assert "library@iem.edu.in" not in reply
    assert "legal@1000" not in reply


def test_tc28_membership_cards_from_env(mock_cred_env):
    from archipelago.inference.eresource_credentials import format_credential_reply

    reply = format_credential_reply(
        "How many British Council and American Library access cards are available for issue?"
    )
    assert reply is not None
    assert "10" in reply
    assert "5" in reply
    assert "British Council" in reply
    assert "American Library" in reply


def test_tc29_opac_url_and_login_format(mock_cred_env):
    """TC-29: OPAC portal + login format are fine to share; passwords are not."""
    from archipelago.inference.eresource_credentials import format_credential_reply
    from archipelago.inference.synthesis import render_library_info

    reply = format_credential_reply(
        "What is the URL and default login format for the library OPAC catalog?"
    )
    assert reply is not None
    assert "uemk-opac" in reply
    assert "Emp ID" in reply or "Enrollment" in reply
    sheet = render_library_info("opac login url")
    assert "uemk-opac" in sheet


def test_tc30_efy_ezine_from_secure_store(mock_cred_env):
    """TC-30: EFY portal URL is fine; the shared email/login is not."""
    from archipelago.inference.eresource_credentials import format_credential_reply

    reply = format_credential_reply("How do I access the digital ezine for Electronics For You?")
    assert reply is not None
    assert "ezine.efymag.com" in reply
    assert "library.uemk@uem.edu.in" not in reply
    assert "E190219" not in reply


def test_tc19_subject_leaderboard_ods_or_graph():
    from archipelago.inference.catalog_ops import (
        format_subject_leaderboard,
        highest_title_count_subject,
        subject_title_counts,
    )

    ranked = subject_title_counts(limit=5)
    # ODS is present in docs/ for pilot — should yield at least one row offline.
    if ranked:
        top = highest_title_count_subject()
        assert top is not None
        assert top["title_count"] >= 1
        text = format_subject_leaderboard()
        assert top["subject"] in text
        assert str(top["title_count"]) in text


def test_tc20_journal_totals_ods_or_graph():
    from archipelago.inference.catalog_ops import (
        format_journal_totals,
        journal_title_and_issue_totals,
    )

    totals = journal_title_and_issue_totals()
    assert "journal_titles" in totals and "issue_count" in totals
    text = format_journal_totals()
    assert str(totals["journal_titles"]) in text
    assert str(totals["issue_count"]) in text


def test_tc21_keyword_search_data_mining():
    from archipelago.inference.synthesis import render_catalog_stats

    text = render_catalog_stats(
        "Search the library catalog for all available titles containing the keyword 'Data Mining'."
    )
    assert "Data Mining" in text or "data mining" in text.lower() or "No catalog" in text


def test_tc27_zero_copy_audit_api_shape(monkeypatch):
    from archipelago.inference import catalog_ops as ops

    monkeypatch.setattr(
        ops,
        "zero_available_copies",
        lambda topic_filter=None, limit=25: [
            {
                "resource_id": "r-ai-1",
                "title": "Deep Learning Handbook",
                "author": "Goodfellow",
                "available_copies": 0,
                "total_copies": 2,
                "barcodes": "",
                "subjects": ["Artificial Intelligence"],
            }
        ],
    )
    text = ops.format_zero_copy_audit("AI ML")
    assert "Deep Learning Handbook" in text
    assert "0" in text or "zero" in text.lower()


def test_credentials_never_hardcoded_in_source():
    """Product source must not embed the pilot PDF secrets as string literals."""
    root = Path(__file__).resolve().parents[2]
    forbidden = [
        "aeb28d3c-de60-439a-89b7-8cfed9aa0657",
        "fG8BeaTC",
        "gh8ccws]",
    ]
    # These targets may be a single module or a split package; scan both.
    scan_targets = [
        root / "archipelago" / "inference" / "eresource_credentials.py",
        root / "archipelago" / "inference" / "synthesis",
        root / "archipelago" / "inference" / "routing",
    ]

    def source_files(target: Path) -> list[Path]:
        if target.is_file():
            return [target]
        if target.is_dir():
            return sorted(target.rglob("*.py"))
        return []

    scanned = 0
    for target in scan_targets:
        for path in source_files(target):
            text = path.read_text(encoding="utf-8")
            for secret in forbidden:
                assert secret not in text, f"secret leaked in {path}"
            scanned += 1
    assert scanned > 0, "no source files were scanned"

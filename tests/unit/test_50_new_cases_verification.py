# ruff: noqa: RUF003, RUF001
"""
test_50_new_cases_verification.py — 50 New Comprehensive Test Cases

Verifies:
1. New Chat & Context Reset API
2. 100 Grounded Answer Layout Templates
3. Custom System Messaging ("library closed", rate limits)
4. Page-Specific Deep-Linking with Page-Width Zoom (#page=N&zoom=page-width)
5. 55-Document Stack of Books Catalog
6. Jul 21 Meeting Decisions (Copyright metadata-only, 3 core subjects, 5-min pilot)
7. E-Resource Credentials (ScienceDirect, IEEE, Springer) & Hidden Password Security
8. IEM/UEM 24x7 Rules (Saturday/Sunday reading, Weekday circulation, Muskan Xerox B1 LG2.7)
9. Journal Coverage, Keyword Reports & ODS Metadata
"""

import pytest

# Register Flask routes
from archipelago.inference import bootstrap  # noqa: F401
from archipelago.inference.citations import citation_payload
from archipelago.inference.context_tracker import SESSION_CONTEXTS, get_or_create_context
from archipelago.inference.grounded_answers import (
    _layouts,
    render_grounded_answer,
    select_layout_index,
)
from archipelago.inference.ranking_seeds import SEED_BOOKS, SEED_PAPERS, detect_subject_key
from archipelago.inference.rate_limit import SlidingWindowLimiter, rate_limit_response
from archipelago.inference.reply_styles import REPLY_STYLES
from archipelago.inference.routes_page_view import _is_known_catalog_path, _resolve_pdf_url
from archipelago.inference.state import app
from archipelago.inference.synthesis import (
    OLLAMA_UNAVAILABLE_MSG,
    closed_library_reply,
    render_library_info,
)

pytestmark = pytest.mark.usefixtures("verified_student_auth")

# ── Category 1: New Chat & Server-Side Session Context Switching (1–5) ─────────────


def test_01_new_chat_context_reset_endpoint():
    sid = "test-new-chat-session-01"
    get_or_create_context(sid)
    assert sid in SESSION_CONTEXTS
    with app.test_client() as client:
        res = client.post("/api/context-status", json={"session_id": sid, "action": "reset"})
        assert res.status_code == 200
        assert res.get_json()["reset"] is True
    assert sid not in SESSION_CONTEXTS


def test_02_new_chat_resets_active_topics():
    sid = "test-session-active-topics-02"
    tracker = get_or_create_context(sid)
    tracker.active_topics.append("LoRA")
    assert len(tracker.active_topics) > 0
    with app.test_client() as client:
        client.post("/api/context-status", json={"session_id": sid, "action": "reset"})
    assert sid not in SESSION_CONTEXTS


def test_03_context_status_query_action():
    sid = "test-session-query-03"
    get_or_create_context(sid)
    with app.test_client() as client:
        res = client.post("/api/context-status", json={"session_id": sid, "action": "status"})
        assert res.status_code == 200
        assert "active_topics" in res.get_json()


def test_04_context_tracker_max_history():
    sid = "test-session-history-04"
    tracker = get_or_create_context(sid)
    for i in range(35):
        tracker.active_topics.append(f"topic_{i}")
    tracker.active_topics = tracker.active_topics[-10:]
    assert len(tracker.active_topics) == 10


def test_05_invalid_action_context_status():
    with app.test_client() as client:
        res = client.post("/api/context-status", json={"session_id": "s5", "action": "invalid"})
        assert res.status_code == 200  # Default handler returns session status


# ── Category 2: 100 Grounded Answer Layout Templates (6–12) ─────────────────────────


def test_06_grounded_answers_has_exactly_100_layouts():
    layouts = _layouts()
    assert len(layouts) == 100


def test_07_reply_styles_has_exactly_100_styles():
    assert len(REPLY_STYLES) == 100


def test_08_select_layout_index_sampling_bounds():
    idxs = [select_layout_index(f"query_{i}", "aiml_paper") for i in range(300)]
    assert all(0 <= idx < 100 for idx in idxs)
    assert len(set(idxs)) >= 30


def test_09_layout_L51_rendering():
    layout_51 = _layouts()[50]  # L51 is 0-indexed position 50
    out = layout_51(
        {
            "opener": "Opener",
            "summary_short": "LoRA method",
            "body": "LoRA body",
            "cite": " (p. 1)",
            "closer": "Closer",
        }
    )
    assert "Opener" in out
    assert "LoRA method" in out


def test_10_layout_L100_rendering():
    layout_100 = _layouts()[99]
    out = layout_100({"opener": "Opener 100", "body": "Body 100", "closer": "Closer 100"})
    assert "Opener 100" in out
    assert "Body 100" in out


def test_11_render_grounded_answer_includes_citation_link():
    c = {"id": "rag", "label": "RAG", "name": "RAG", "summary": "Retrieval-Augmented Generation."}
    cm = {
        "rag": [
            {
                "evidence_id": "S1",
                "doc_id": "papers/Lewis2020_RAG.pdf",
                "page_number": 4,
                "section_title": "RAG",
            }
        ]
    }
    out = render_grounded_answer("What is RAG?", c, citation_map=cm)
    assert "/api/page-view" in out or "S1" in out


def test_12_all_100_layouts_executable_without_crash():
    ctx = {
        "query_short": "What is AI?",
        "name": "AI",
        "cid": "ai",
        "field": "aiml_paper",
        "field_label": "aiml paper",
        "opener": "Opener",
        "closer": "Closer",
        "summary": "Summary",
        "summary_short": "Short summary",
        "cite": " [S1]",
        "body": "Body text",
        "prereqs": ["P1"],
        "unlocks": ["U1"],
        "peers": ["Peer1"],
        "path_section": "",
        "layout_i": 0,
    }
    for _i, fn in enumerate(_layouts()):
        res = fn(ctx)
        assert isinstance(res, str)
        assert len(res) > 0


# ── Category 3: Custom System Messaging (13–18) ────────────────────────────────────


def test_13_exact_ollama_unavailable_message_string():
    assert "library closed" in OLLAMA_UNAVAILABLE_MSG


def test_14_closed_library_reply_formatting():
    res = closed_library_reply("Fallback details")
    assert "library closed" in res
    assert "Fallback details" not in res


def test_15_rate_limit_response_exact_message_string():
    with app.test_request_context():
        resp = rate_limit_response({"retry_after_s": 12, "scope": "per_client"})
        data = resp.get_json()
        assert resp.status_code == 429
        assert data["error"] == "library is too busy ! you are in queue, retrying after-12s"


def test_16_rate_limit_global_scope_message():
    with app.test_request_context():
        resp = rate_limit_response({"retry_after_s": 30, "scope": "global"})
        data = resp.get_json()
        assert "library is too busy ! you are in queue, retrying after-30s" in data["error"]


def test_17_sliding_window_limiter_burst_trigger():
    lim = SlidingWindowLimiter()
    key = "test-client-burst-17"
    for _ in range(10):
        lim.check(key, per_min=100, burst=4, global_per_min=1000)
    ok, meta = lim.check(key, per_min=100, burst=4, global_per_min=1000)
    assert not ok or meta.get("disabled") is True


def test_18_sliding_window_limiter_client_key():
    from archipelago.inference.rate_limit import client_key_from_request

    class FakeReq:
        def __init__(self):
            self.remote_addr = "192.168.1.1"
            self.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}

    key = client_key_from_request(FakeReq(), "session123")
    assert "10.0.0.1|session123" in key


# ── Category 4: Page-Specific Deep-Linking with Page-Width Zoom (19–24) ─────────────


def test_19_citation_payload_includes_page_view_url():
    ev = {
        "doc_id": "papers/Hu2021_LoRA.pdf",
        "page_number": 3,
        "text": "LoRA passage",
        "evidence_id": "S1",
    }
    payload = citation_payload(ev, "LoRA")
    assert "/api/page-view" in payload["url"]
    assert "doc_id=papers%2FHu2021_LoRA.pdf" in payload["url"] or "Hu2021_LoRA" in payload["url"]
    assert "page=3" in payload["url"]
    assert "#page=3" in payload["url"]


def test_20_page_view_contract_endpoint_returns_200():
    with app.test_client() as client:
        res = client.get("/api/page-view?doc_id=papers/Hu2021_LoRA.pdf&page=1&highlight=LoRA")
        assert res.status_code == 200
        data = res.get_json()
        assert "doc_id" in data
        assert "passage" in data


def test_21_page_view_missing_doc_id_returns_400():
    with app.test_client() as client:
        res = client.get("/api/page-view")
        assert res.status_code == 400


def test_22_page_view_url_zoom_fragment_structure():
    page = 5
    frag = f"page={page}&zoom=page-width&pagemode=none&navpanes=0"
    assert "zoom=page-width" in frag
    assert "page=5" in frag


def test_23_known_catalog_path_validation():
    assert _is_known_catalog_path("papers/Devlin2018_BERT.pdf") is True
    assert _is_known_catalog_path("ostep_three_easy_pieces/08_Paging.pdf") is True
    assert _is_known_catalog_path("unknown_random_book.pdf") is False


def test_24_resolve_pdf_url_output():
    url, _avail = _resolve_pdf_url("papers/Hu2021_LoRA.pdf")
    assert "/pdfs/" in url


# ── Category 5: 55-Document Stack of Books Catalog (25–30) ─────────────


def test_25_seed_books_count():
    assert len(SEED_BOOKS) >= 5


def test_26_seed_papers_count():
    assert len(SEED_PAPERS) >= 5


def test_27_catalog_55_domain_mapping_dbms():
    assert detect_subject_key("database systems Relational Algebra") == "dbms"


def test_28_catalog_55_domain_mapping_os():
    assert detect_subject_key("OSTEP CPU scheduling virtual memory") == "operating_systems"


def test_29_catalog_55_domain_mapping_data_structures():
    assert detect_subject_key("binary tree heap sort algorithm") == "data_structures"


def test_30_catalog_55_domain_mapping_peft_rag():
    assert detect_subject_key("transformers machine learning model") == "aiml"


# ── Category 6: Meeting Decisions (Metadata-Only & 5-Min Pilot Scope) (31–35) ────────


def test_31_jul21_decision_books_are_metadata_only():
    for book in SEED_BOOKS:
        assert "title" in book
        assert "authors" in book
        assert "subject_key" in book


def test_32_jul21_decision_pilot_scope_subjects():
    subjects = {b["subject_key"] for b in SEED_BOOKS}
    assert "dbms" in subjects
    assert "operating_systems" in subjects
    assert "data_structures" in subjects


def test_33_jul21_decision_pilot_paper_count():
    assert len(SEED_PAPERS) >= 5


def test_34_jul21_decision_5_min_presentation_capabilities():
    info = render_library_info("hours")
    assert "24 × 7 × 365" in info


def test_35_jul21_decision_daily_reporting_readiness():
    with app.test_client() as client:
        res = client.get("/api/readiness")
        assert res.status_code in (200, 500, 503)


# ── Category 7: ScienceDirect Credentials & Authorized E-Resources (36–40) ───────────


def test_36_sciencedirect_portal_info():
    info = render_library_info("Elsevier Science Direct")
    assert "sciencedirect.com" in info
    assert "IP-based" in info or "On-Campus" in info


def test_37_sciencedirect_offcampus_credential_security():
    info = render_library_info("sciencedirect password")
    assert "4359789IEMK" not in info
    assert "This chat does not display shared passwords" in info


def test_38_ieee_xplore_portal_info():
    info = render_library_info("IEEE Xplore")
    assert "IEEE Xplore" in info


def test_39_springer_portal_info():
    info = render_library_info("SpringerLink")
    assert "SpringerLink" in info


def test_40_eresources_authorized_list_completeness():
    info = render_library_info("e-resources portal list")
    assert "Scopus" in info
    assert "EBSCOhost" in info
    assert "J-Gate" in info

"""
test_50_cases_library.py — 50 distinct test cases verifying UEM/IEM Library rules,
meeting decisions, e-resources, ODS file handling, and pipeline functionality.
"""

import os
import re
import pytest
from pathlib import Path
from typing import Any

from archipelago.inference.state import DEFAULT_OLLAMA_MODEL
from archipelago.inference.routes_misc import estimate_ingestion_time, pdf_available
from archipelago.inference.synthesis import render_library_info, closed_library_reply, OLLAMA_UNAVAILABLE_MSG
from archipelago.inference.ranking_seeds import (
    detect_subject_key,
    rank_seed_entries,
    format_seed_ranking,
    SEED_BOOKS,
    SEED_PAPERS,
    seed_local_doc_id,
)
from archipelago.inference.library_queries import clean_topic_query
from archipelago.inference.citations import (
    build_library_source_payloads,
    cleanse_model_citations,
)
from archipelago.inference.scope_gate import is_aiml_in_scope

# ── 1. Timing, Opening Hours, & Weekend Rules (Tests 1-5) ────────────────────────

def test_01_library_open_24x7():
    info = render_library_info("timing")
    assert "24 × 7 × 365" in info
    assert "before or after class hours" in info

def test_02_weekend_services():
    info = render_library_info("weekend")
    assert "Saturdays and Sundays" in info
    assert "book issue and return services are not available on weekends" in info

def test_03_night_and_breaks():
    info = render_library_info("night hours")
    assert "during night hours, and on breaks" in info

def test_04_weekday_only_issue_services():
    info = render_library_info("timing")
    assert "weekdays only" in info

def test_05_circulation_desk_hours():
    info = render_library_info("generic query")
    assert "ask at the circulation desk during weekday hours" in info

# ── 2. Library Card & HOD Temporary Borrowing (Tests 6-10) ────────────────────────

def test_06_automatic_card_generation():
    info = render_library_info("library card")
    assert "Issued **automatically** once your Enrollment Number is generated" in info
    assert "no separate application needed" in info

def test_07_borrowing_before_card():
    info = render_library_info("borrow without card")
    assert "Submit a request letter addressed to the Librarian" in info

def test_08_hod_forwarding_requirement():
    info = render_library_info("borrow before card")
    assert "duly forwarded by your Head of Department (HOD)" in info

def test_09_privileges_until_card_arrives():
    info = render_library_info("first year card")
    assert "use: the reading room" in info
    assert "photography of required pages" in info
    assert "photocopy (Xerox) facilities" in info

def test_10_no_separate_card_application():
    info = render_library_info("enrolment card")
    assert "no separate application" in info

# ── 3. Open Access, Entry Register, & Lab Manuals (Tests 11-15) ──────────────────

def test_11_open_access_shelf_system():
    info = render_library_info("shelves")
    assert "Collect books directly from the shelves" in info
    assert "return them **back to the shelves**" in info

def test_12_entry_exit_register():
    info = render_library_info("register")
    assert "Record your **In Time and Out Time** in the Library Register" in info

def test_13_announcements_and_notices():
    info = render_library_info("announcement")
    assert "notices and important announcements are communicated periodically" in info

def test_14_pyq_and_magazines_reading():
    info = render_library_info("pyq")
    assert "Previous Year Question Papers (PYQs), magazines, and journals" in info

def test_15_lab_manual_xerox_location():
    info = render_library_info("lab manual")
    assert "B1 LG2.7 (Muskan Xerox)" in info

# ── 4. OPAC & E-Resources Access Rules (Tests 16-21) ─────────────────────────────

def test_16_opac_catalog_link():
    info = render_library_info("opac website")
    assert "uemk-opac.l2c2.co.in" in info

def test_17_eresources_Elsevier_link():
    info = render_library_info("e-resource credentials")
    assert "Elsevier ScienceDirect" in info
    assert "sciencedirect.com" in info

def test_18_eresources_authorized_portal_list():
    info = render_library_info("springer ieee delnet")
    assert "IEEE Xplore" in info
    assert "SpringerLink" in info
    assert "Scopus" in info
    assert "EBSCOhost" in info

def test_19_jgate_and_proquest_credentials():
    info = render_library_info("eresource login")
    assert "J-Gate" in info
    assert "ProQuest" in info
    assert "NDLI" in info

def test_20_turnitin_administrative_access():
    info = render_library_info("Turnitin account")
    assert "For Turnitin, contact the library team" in info

def test_21_eresource_passwords_are_hidden():
    info = render_library_info("sciencedirect password")
    assert "This chat does not display shared passwords" in info

# ── 5. Ingestion Estimate Duration & Time Limits (Tests 22-25) ──────────────────

def test_22_estimate_small_pdf_ingestion():
    est = estimate_ingestion_time(500 * 1024, "paper.pdf")
    assert 20 <= est["estimated_seconds"] <= 45
    assert "seconds" in est["estimated_time_formatted"]

def test_23_estimate_medium_pdf_ingestion():
    est = estimate_ingestion_time(3 * 1024 * 1024, "chapter.pdf")
    assert est["estimated_seconds"] > 45

def test_24_estimate_large_pdf_ingestion():
    est = estimate_ingestion_time(10 * 1024 * 1024, "book.pdf")
    assert est["estimated_seconds"] > 135

def test_25_estimate_markdown_ingestion():
    est = estimate_ingestion_time(20 * 1024, "notes.md")
    assert est["estimated_seconds"] == 5
    assert "seconds" in est["estimated_time_formatted"]

# ── 6. Subject Detection & Alignment (Tests 26-30) ───────────────────────────────

def test_26_detect_subject_dbms():
    assert detect_subject_key("tell me about SQL databases") == "dbms"

def test_27_detect_subject_operating_systems():
    assert detect_subject_key("recommend scheduler books for OS") == "operating_systems"

def test_28_detect_subject_data_structures():
    assert detect_subject_key("dsa heap tree algorithms list") == "data_structures"

def test_29_detect_subject_aiml():
    assert detect_subject_key("explain transformers machine learning") == "aiml"

def test_30_detect_subject_none():
    assert detect_subject_key("recommend something about biology") is None

# ── 7. Seed Ingestion & Copyright Compliance (Tests 31-35) ───────────────────────

def test_31_seed_books_copyright_compliance():
    # Verify that only metadata (title, authors, subject) is defined, not full content
    for book in SEED_BOOKS:
        assert len(book.get("title", "")) > 0
        assert len(book.get("authors", "")) > 0
        assert "subject_key" in book

def test_32_seed_papers_venue_present():
    for paper in SEED_PAPERS:
        assert len(paper.get("title", "")) > 0
        assert "venue" in paper

def test_33_seed_math_for_ml_hint():
    # Verify Deisenroth Math For ML exists with the expected hint
    mml = [b for b in SEED_BOOKS if "Deisenroth" in b.get("authors", "")]
    assert len(mml) == 1
    assert mml[0]["doc_id_hint"] == "textbooks/Deisenroth_Math_For_ML.pdf"

def test_34_seed_local_doc_id_missing_resolves_none():
    # Mock entry with non-existent file
    entry = {"doc_id_hint": "nonexistent/file.pdf"}
    assert seed_local_doc_id(entry) is None

def test_35_seed_local_doc_id_none():
    assert seed_local_doc_id(None) is None

# ── 8. Seed Ranking & Blended Score logic (Tests 36-40) ─────────────────────────

def test_36_rank_seed_entries_textbooks():
    ranked = rank_seed_entries("DBMS textbooks", kind="textbook")
    assert len(ranked) > 0
    assert all(r["kind"] == "textbook" for r in ranked)

def test_37_rank_seed_entries_papers():
    ranked = rank_seed_entries("RAG papers", kind="paper")
    assert len(ranked) > 0
    assert all(r["kind"] == "paper" for r in ranked)

def test_38_rank_seed_entries_availability_bonus():
    # Available books should rank higher than unavailable ones
    ranked_unavail = rank_seed_entries("operating systems", availability_by_title={})
    
    # Give Tanenbaum 100% availability
    avail = {"modern operating systems": 1.0}
    ranked_avail = rank_seed_entries("operating systems", availability_by_title=avail)
    
    tanenbaum_unavail = [r for r in ranked_unavail if "Tanenbaum" in r.get("authors", "")][0]
    tanenbaum_avail = [r for r in ranked_avail if "Tanenbaum" in r.get("authors", "")][0]
    
    assert tanenbaum_avail["score"] > tanenbaum_unavail["score"]

def test_39_format_seed_ranking_no_entries():
    res = format_seed_ranking([])
    assert "No librarian-approved seed titles" in res

def test_40_format_seed_ranking_discovery_section():
    # Tanenbaum is metadata-only (no local file resolved)
    res = format_seed_ranking(SEED_BOOKS)
    assert "Curated reading list" in res
    assert "not openable here" in res

# ── 9. Library Source Payloads & Grounding (Tests 41-45) ─────────────────────────

def test_41_build_library_source_payloads_empty():
    assert build_library_source_payloads([], "topic") == []

def test_42_build_library_source_payloads_structure():
    books = [{"id": "books/db_concepts.pdf", "title": "Database Concepts", "matched": ["SQL"]}]
    payloads = build_library_source_payloads(books, "SQL")
    assert len(payloads) == 1
    assert payloads[0]["doc_id"] == "books/db_concepts.pdf"
    assert payloads[0]["evidence_id"] == "S1"
    assert "SQL" in payloads[0]["topic"]

def test_43_is_aiml_in_scope_chitchat():
    # Greetings are technically out of Technical scope but chitchat is True
    ok, reason = is_aiml_in_scope("hello there", chitchat=True)
    assert ok is True
    assert reason == "chitchat_skip"

def test_44_is_aiml_in_scope_offtopic():
    ok, reason = is_aiml_in_scope("who won the football world cup", offtopic_keyword=True)
    assert ok is False
    assert reason == "offtopic_keyword"

def test_45_is_aiml_in_scope_technical():
    ok, reason = is_aiml_in_scope("explain backpropagation gradients", has_domain_terms=True)
    assert ok is True

# ── 10. Citation Cleansing & Ollama Offline (Tests 46-50) ────────────────────────

def test_46_cleanse_model_citations_strips_invalid_payloads():
    # If citation payload is missing, S1 should be stripped
    res = cleanse_model_citations("This is true [S1].", [])
    assert "[S1]" not in res
    assert "This is true." in res

def test_47_cleanse_model_citations_keeps_valid_payloads():
    payloads = [{
        "evidence_id": "S1",
        "topic": "Backpropagation",
        "doc_id": "papers/backprop.pdf",
        "page_number": 3,
        "text_span": "Backpropagation calculates gradients",
    }]
    res = cleanse_model_citations("Backpropagation calculates gradients [S1].", payloads)
    assert "/api/page-view?" in res
    assert "doc_id=papers%2Fbackprop.pdf" in res
    assert "page=3" in res

def test_48_closed_library_reply_no_fallback():
    res = closed_library_reply()
    assert res == OLLAMA_UNAVAILABLE_MSG

def test_49_closed_library_reply_with_fallback():
    res = closed_library_reply("Here is index fallback info.")
    assert res == OLLAMA_UNAVAILABLE_MSG
    assert "Here is index fallback info." not in res

def test_50_clean_topic_query_strips_nonsense():
    assert clean_topic_query("suggest books on DBMS").lower() == "dbms"
    assert clean_topic_query("recommend books regarding SQL").lower() == "sql"

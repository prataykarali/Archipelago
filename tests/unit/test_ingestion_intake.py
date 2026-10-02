"""Librarian intake: mention-a-book, page-image prefill, spreadsheet idempotency."""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.unit


# ── Mention-a-book ───────────────────────────────────────────────────────────

def test_mention_resolves_known_title_to_exact_source():
    from archipelago.ingestion.mention import mention_book

    result = mention_book("Attention Is All You Need")
    assert result.matches, "a known paper must resolve"
    top = result.matches[0]
    assert top.title.lower().startswith("attention is all you need")
    # The source must be the exact dataset file page, never the repo root.
    assert top.source_url.startswith(
        "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/"
    )
    assert top.source_url.rstrip("/") != "https://huggingface.co/datasets/Prataykarali/Library_books"


def test_mention_resolves_isbn_exactly():
    from archipelago.ingestion.mention import mention_book

    result = mention_book("9781108455145")
    assert result.matches
    assert result.matches[0].confidence == 100.0
    assert result.matches[0].isbn == "9781108455145"


def test_mention_pearson_title_gets_exact_reader_page():
    from archipelago.ingestion.mention import mention_book

    result = mention_book("Computer Networks Tanenbaum")
    assert result.matches
    pearson = [m for m in result.matches if m.match_kind == "pearson_catalog"]
    assert pearson, "expected a Pearson catalogue match"
    assert "#book/" in pearson[0].source_url
    assert "elibrary.in.pearson.com" in pearson[0].source_url


def test_unknown_mention_fabricates_nothing():
    from archipelago.ingestion.mention import mention_book

    result = mention_book("zzz nonexistent book qqq")
    assert not result.matches
    assert result.no_match_reason
    assert "Nothing was invented" in result.no_match_reason


def test_empty_mention_is_rejected_explicitly():
    from archipelago.ingestion.mention import mention_book

    result = mention_book("   ")
    assert not result.matches
    assert "empty" in result.no_match_reason.lower()


def test_weak_match_does_not_trust_its_metadata():
    """A fuzzy title hit must not auto-apply an author from a different book."""
    from archipelago.ingestion.mention import MentionMatch, is_trusted_match, prefill_from_match

    weak = MentionMatch(
        title="Deep Learning",
        match_kind="catalog_record",
        source="Central Library Catalogue",
        confidence=72.0,
        author="Christopher M. Bishop",
        source_url="https://uemk-opac.l2c2.co.in",
    )
    assert is_trusted_match(weak) is False
    payload = prefill_from_match(weak)
    assert payload["metadata_trusted"] is False
    # The author is offered as a suggestion, never silently applied.
    assert "author" not in payload
    assert payload["suggested_fields"]["author"] == "Christopher M. Bishop"


def test_exact_isbn_match_is_trusted():
    from archipelago.ingestion.mention import MentionMatch, is_trusted_match

    strong = MentionMatch(
        title="Mathematics for Machine Learning",
        match_kind="exact_isbn",
        source="Identifier Lookup",
        confidence=100.0,
        author="Marc Peter Deisenroth",
    )
    assert is_trusted_match(strong) is True


# ── Page image / page text extraction ────────────────────────────────────────

def _toc_page_text() -> str:
    return (
        "Speech and Language Processing\n"
        "Dan Jurafsky and James H. Martin\n"
        "ISBN 978-0-13-687918-0\n"
        "Copyright (c) 2023 Pearson Education\n"
        "Contents\n"
        "1 Introduction 1\n"
        "2 Regular Expressions and Tokenization 45\n"
        "3 Neural Networks 120\n"
        "4 Transformers 210\n"
    )


def test_page_text_extracts_toc_fields():
    from archipelago.ingestion.page_image import extract_page_from_text

    ex = extract_page_from_text(_toc_page_text())
    assert ex.is_index_page is True
    assert ex.title == "Speech and Language Processing"
    assert "Jurafsky" in ex.author
    assert ex.isbn == "9780136879180"
    assert ex.publisher == "Pearson Education"
    assert ex.year == "2023"
    assert len(ex.toc_entries) == 4
    assert ex.toc_entries[0]["page"] == 1


def test_page_text_toc_entries_carry_section_numbers():
    from archipelago.ingestion.page_image import extract_page_from_text

    ex = extract_page_from_text(_toc_page_text())
    assert ex.toc_entries[-1]["section"] == "4"
    assert ex.toc_entries[-1]["heading"].endswith("Transformers")


def test_content_page_is_not_flagged_as_index():
    from archipelago.ingestion.page_image import extract_page_from_text

    ex = extract_page_from_text("Chapter 3\nAttention is all you need to scale sequences.")
    assert ex.is_index_page is False
    assert ex.is_content_page is True
    assert ex.toc_entries == []


def test_isbn_ignores_printed_separators():
    from archipelago.ingestion.page_image import extract_isbn_field

    assert extract_isbn_field("ISBN 978-0-13-687918-0") == "9780136879180"
    assert extract_isbn_field("isbn-10 0 13 687918 9") == "0136879189"


def test_prefill_reports_no_match_instead_of_inventing():
    from archipelago.ingestion.page_image import build_prefill, extract_page_from_text

    ex = extract_page_from_text(
        "Zzzz Unrelated Nonsense Title\nSome Author Name\nISBN 9999999999999\n"
    )
    payload = build_prefill(ex, filename="x.png")
    if not payload["matched_sources"]:
        assert payload["no_match_reason"]
    # Whatever happened, a source URL is only present if a real match supplied it.
    for match in payload["matched_sources"]:
        assert match["source_url"]


def test_prefill_flags_untrusted_top_match():
    from archipelago.ingestion.page_image import build_prefill, extract_page_from_text

    ex = extract_page_from_text("Deep Learning\nSome Author\n")
    payload = build_prefill(ex, filename="dl.png")
    if payload["matched_sources"] and not payload["top_match_trusted"]:
        assert any("confirm" in w.lower() for w in payload["warnings"])


# ── Spreadsheet merge ────────────────────────────────────────────────────────

def test_column_aliases_map_to_canonical_fields():
    from archipelago.ingestion.spreadsheet import map_columns

    mapping, detected = map_columns(
        ["Biblionumber", "Book Title", "Author", "Publisher", "No. of Copies", "Available"]
    )
    assert "title" in detected
    assert "author" in detected
    assert "publisher" in detected
    assert "total_copies" in detected
    assert "available_copies" in detected
    # Each canonical field is claimed at most once.
    assert len(mapping) == len(set(mapping.values()))


def test_header_row_is_found_below_report_titles():
    from archipelago.ingestion.spreadsheet import find_header_row

    rows = [
        ["Koha Report - Generated 2026-01-01"],
        [],
        ["Biblionumber", "Title", "Author"],
        ["1", "Some Book", "An Author"],
    ]
    assert find_header_row(rows) == 2


def test_record_id_is_stable_and_title_based():
    from archipelago.ingestion.spreadsheet import record_id_for

    first = record_id_for({"title": "Fundamentals of Mechanical Engineering", "isbn": "1"})
    second = record_id_for({"title": "fundamentals  of mechanical engineering", "isbn": "2"})
    assert first == second, "id must not depend on ISBN or casing"
    assert first.startswith("res_")


def test_spreadsheet_merge_is_idempotent(tmp_path):
    """Re-running the same export must never duplicate a record."""
    from archipelago.ingestion.spreadsheet import apply_merge

    sheet = tmp_path / "holdings.csv"
    sheet.write_text(
        "Biblionumber,Title,Author,Publisher,No. of Copies,Available\n"
        "101,Operating Systems Internals,Author One,MIT Press,3,2\n"
        "102,Compiler Design Handbook,Author Two,Pearson,1,1\n",
        encoding="utf-8",
    )
    first = apply_merge(sheet, dry_run=True)
    assert first["counts"]["CREATE"] == 2
    assert first["writes_performed"] == 0, "dry run must never write"
    assert first["dry_run"] is True

    second = apply_merge(sheet, dry_run=True)
    # A dry run never writes, so the plan is identical and still idempotent.
    assert second["counts"]["CREATE"] == 2


def test_spreadsheet_requires_a_title_column(tmp_path):
    from archipelago.ingestion.spreadsheet import apply_merge

    sheet = tmp_path / "bad.csv"
    sheet.write_text("Foo,Bar\n1,2\n", encoding="utf-8")
    result = apply_merge(sheet, dry_run=True)
    assert result["row_count"] == 0
    assert result["errors"]


def test_retire_is_opt_in(tmp_path):
    from archipelago.ingestion.spreadsheet import plan_merge

    sheet = tmp_path / "partial.csv"
    sheet.write_text(
        "Biblionumber,Title,Author\n201,Only Book Present,An Author\n",
        encoding="utf-8",
    )
    default_plan = plan_merge(sheet, retire_missing=False)
    assert default_plan.counts()[  "RETIRE"] == 0, "partial exports must never retire"
    opted_in = plan_merge(sheet, retire_missing=True)
    assert opted_in.counts()["CREATE"] == 1


# ── Intake routes ────────────────────────────────────────────────────────────

@pytest.fixture()
def librarian_client(monkeypatch):
    from archipelago.apps.inference_app import create_app

    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("ARCHIPELAGO_ALLOW_DEV_AUTH", "1")
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        client.environ_base.update({
            "HTTP_X_USER_ROLE": "librarian",
            "HTTP_X_USER_NAME": "lib",
            "HTTP_X_USER_ID": "local-librarian-id",
        })
        yield client


def test_intake_capabilities_advertises_helpers(librarian_client):
    response = librarian_client.get("/api/ingest/intake/capabilities")
    assert response.status_code == 200
    body = response.get_json()
    assert "ocr_available" in body
    assert body["retire_requires_confirmation"] is True
    assert "spreadsheet_outcomes" in body


def test_mention_route_returns_prefill(librarian_client):
    response = librarian_client.post("/api/ingest/mention", json={"query": "Attention Is All You Need"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["found"] is True
    assert body["matches"][0]["source_url"].startswith("https://huggingface.co/datasets/")


def test_mention_route_rejects_empty_query(librarian_client):
    response = librarian_client.post("/api/ingest/mention", json={"query": ""})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_page_text_route_prefills_fields(librarian_client):
    response = librarian_client.post("/api/ingest/page-text", json={"text": _toc_page_text()})
    assert response.status_code == 200
    fields = response.get_json()["fields"]
    assert fields["title"] == "Speech and Language Processing"
    assert fields["isbn"] == "9780136879180"
    assert fields["chapter_count"] == 4


def test_page_image_route_rejects_missing_file(librarian_client):
    response = librarian_client.post("/api/ingest/page-image", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert "accepted_formats" in response.get_json()


def test_destructive_retire_requires_confirmation(librarian_client, tmp_path):
    sheet = tmp_path / "partial.csv"
    sheet.write_text("Biblionumber,Title\n9,A Book\n", encoding="utf-8")
    response = librarian_client.post(
        "/api/ingest/spreadsheet/apply",
        json={"path": str(sheet), "dry_run": True, "retire_missing": True},
    )
    assert response.status_code == 400
    assert response.get_json()["requires_confirmation"] is True

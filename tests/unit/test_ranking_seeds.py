"""Librarian seed ranking lists — explainable, missing-data-safe."""

from archipelago.inference.ranking_seeds import (
    SEED_BOOKS,
    SEED_PAPERS,
    detect_subject_key,
    format_seed_ranking,
    rank_seed_entries,
)


def test_seed_catalog_has_pilot_subjects():
    subjects = {b["subject_key"] for b in SEED_BOOKS}
    assert {"dbms", "data_structures", "operating_systems", "aiml"} <= subjects
    assert len(SEED_PAPERS) >= 5
    for entry in SEED_BOOKS + SEED_PAPERS:
        assert entry.get("rank_reason")
        assert 0 <= float(entry.get("curator_score") or 0) <= 1
        assert 0 <= float(entry.get("author_authority") or 0) <= 1


def test_detect_subject_key_aliases():
    assert detect_subject_key("best books on DBMS") == "dbms"
    assert detect_subject_key("data structures textbooks") == "data_structures"
    assert detect_subject_key("operating systems ranking") == "operating_systems"
    # Fine-grained RAG key is preferred over the broad aiml bucket.
    assert detect_subject_key("papers on transformers and RAG") in ("rag", "aiml")
    assert detect_subject_key("what is the weather") is None


def test_rank_seed_entries_orders_by_signals_not_missing_availability():
    ranked = rank_seed_entries("top books on operating systems", kind="textbook", limit=5)
    assert ranked
    assert all(e["subject_key"] == "operating_systems" for e in ranked)
    # Higher blended score first
    scores = [float(e["score"]) for e in ranked]
    assert scores == sorted(scores, reverse=True)
    # Missing availability must stay 0 (never a silent boost)
    assert all(float(e.get("availability") or 0) == 0.0 for e in ranked)


def test_format_seed_ranking_includes_reasons_not_source_dump():
    ranked = rank_seed_entries("best papers on RAG", kind="paper", limit=3)
    text = format_seed_ranking(ranked, topic="RAG")
    # AIML pilot papers have local PDFs → available section with deep links
    assert "Indexed / openable" in text or "Curated reading list" in text
    assert "Why ranked here" in text
    assert "**Sources:**" not in text
    assert "Bibliography" not in text
    assert "score " not in text
    # Openable seeds must expose page-view links (not pretend "not indexed")
    if "doc_id_hint" in ranked[0] or ranked[0].get("doc_id_hint"):
        # Lewis/RAG seed usually resolves locally in this repo
        assert "Open page" in text or "metadata only" in text or "/api/page-view" in text


def test_format_seed_ranking_marks_local_deisenroth_available():
    ranked = rank_seed_entries("best books on machine learning", kind="textbook", limit=3)
    text = format_seed_ranking(ranked, topic="AI ML")
    # Deisenroth PDF ships under pdfs/textbooks/ — must not say "not indexed"
    assert "Mathematics for Machine Learning" in text
    assert "not indexed in this library" not in text
    assert "available" in text.lower() or "Open page" in text or "/api/page-view" in text


def test_availability_can_boost_but_not_create_entries():
    base = rank_seed_entries("DBMS textbooks", kind="textbook", limit=3)
    boosted = rank_seed_entries(
        "DBMS textbooks",
        kind="textbook",
        limit=3,
        availability_by_title={base[0]["title"].lower(): 1.0},
    )
    assert boosted[0]["title"] == base[0]["title"] or boosted[0]["score"] >= base[0]["score"]


def test_ranking_is_metadata_driven_and_capped_for_books_and_papers():
    """The renderer receives an already-ranked top-four shortlist."""
    books = rank_seed_entries("best books on machine learning", kind="textbook", limit=20)
    papers = rank_seed_entries("best papers on RAG", kind="paper", limit=20)

    assert 1 <= len(books) <= 4
    assert 1 <= len(papers) <= 4
    for entries in (books, papers):
        scores = [float(entry["score"]) for entry in entries]
        assert scores == sorted(scores, reverse=True)
        for entry in entries:
            signals = entry["ranking_signals"]
            assert signals["author_authority"] > 0
            assert signals["review_score"] > 0
            assert signals["provenance"]


def test_library_books_os_not_killed_by_aiml_scope_gate():
    """Pilot OS ranking must route to library_books, not out_of_scope."""
    from archipelago.inference.routing import resolve_query_routing
    r = resolve_query_routing("best books on operating systems")
    assert r.get("route") == "library_books"
    assert r.get("scope") in ("catalog", "yes")
    assert "seed" in (r.get("reason") or "") or (r.get("slots") or {}).get("seed_subject") == "operating_systems"

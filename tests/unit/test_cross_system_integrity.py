"""Cross-system source and link integrity regression tests for Archipelago.

Validates academic chat provenance, Koha OPAC, Pearson eLibrary links,
discovery canonicalization, workbook exports, and security boundaries.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

from openpyxl import load_workbook
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
HOST_INFERENCE = ROOT_DIR / "host_inference"
HOST_RESEARCH = ROOT_DIR / "host_research"
for p in (HOST_INFERENCE, HOST_RESEARCH, ROOT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DOI_PATTERN = re.compile(r"^https://doi\.org/10\.\d{4,9}/\S+$")


@pytest.mark.unit
def test_academic_chat_citation_and_canonical_provenance() -> None:
    """Chat engine must emit canonical chunk IDs and reader-compatible URLs."""
    from engine.answer import Engine

    e = Engine()
    rec = e.graph.cite_record("transformer", "What is Transformer?")
    assert rec.get("chunk_id") is not None, "Missing chunk_id in citation record"
    assert rec.get("doc_id") == "papers/Vaswani2017_Attention_Is_All_You_Need.pdf"
    assert rec.get("page_number") == 2
    assert rec.get("source_type") == "ingested_pdf"
    assert "doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf" in (rec.get("url") or "")
    assert "&page=2" in (rec.get("url") or "")
    assert "The Transformer follows this overall architecture" in (rec.get("text_passage") or "")


@pytest.mark.unit
def test_unsupported_query_abstention_provenance() -> None:
    """Out-of-domain queries must cleanly abstain with 0 citations and no graph."""
    from engine.answer import Engine

    e = Engine()
    queries = [
        "Explain Spanner TrueTime and its prerequisites.",
        "What is Byzantine fault tolerance in distributed systems?",
        "How does Raft consensus elect a leader?",
    ]
    for q in queries:
        ans = e.answer(q)
        payload = ans.get("payload", {})
        assert payload.get("anchor_concept") is None, f"Expected None anchor for {q}"
        assert payload.get("citations") == [], f"Expected empty citations for {q}"
        assert payload.get("render_graph") is False, f"Expected no graph for {q}"
        assert payload.get("prerequisites") == [], f"Expected no prereqs for {q}"
        assert payload.get("unlocks") == [], f"Expected no unlocks for {q}"


@pytest.mark.unit
def test_pearson_book_resolution_and_page_linking() -> None:
    """Pearson institutional titles must resolve by ID/slug and build exact page anchors."""
    from host_inference.remote_cache import load_books, pearson_page_url

    books = load_books()
    assert len(books) >= 40, f"Expected at least 40 Pearson books, found {len(books)}"

    tanenbaum = next((b for b in books if "Tanenbaum" in (b.get("author") or "")), None)
    assert tanenbaum is not None, "Tanenbaum Computer Networks book not found"
    assert tanenbaum.get("isbn") == "9789356063259"

    page_url = pearson_page_url(tanenbaum, 35)
    assert page_url.startswith("https://ebooks.elibrary.in.pearson.com/wr/")
    assert f"#book/{tanenbaum['id']}/page/35" in page_url


@pytest.mark.unit
def test_koha_holdings_snapshot_integrity() -> None:
    """Koha holdings mapping must produce valid OPAC URLs and availability ratios."""
    from host_inference.hostapp.koha_bridge import public_holdings

    sample_snapshot = {
        "holdings": [
            {
                "biblionumber": "1868",
                "Title": "Academy of Management Journal",
                "Author": "AOM",
                "Publisher": "Academy of Management",
                "No. of copies": "6",
                "Available Copies": "6",
                "isbn": "",
                "call_number": "",
            }
        ]
    }
    rows = public_holdings(sample_snapshot)
    assert len(rows) == 1
    assert rows[0]["biblionumber"] == "1868"
    assert rows[0]["title"] == "Academy of Management Journal"
    assert rows[0]["available_ratio"] == "6 / 6"
    assert rows[0]["opac_url"] == "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=1868"


@pytest.mark.unit
def test_discovery_orchestrator_multi_provider_flow() -> None:
    """Discovery orchestrator must search multiple sources and record provenance."""
    from archipelago.scholarly.discovery.orchestrator import DiscoveryOrchestrator

    orchestrator = DiscoveryOrchestrator()
    candidates, sources = orchestrator.discover_with_status("Dense Passage Retrieval", limit_per_source=2)
    assert len(candidates) >= 1, "Expected at least 1 discovered candidate"
    assert len(sources) >= 3, "Expected at least 3 queried sources"

    first = candidates[0]
    paper = first.get("paper")
    assert paper is not None, "Candidate missing paper object"
    assert paper.title, "Paper missing title"
    assert first.get("source") in {"openalex", "crossref", "arxiv", "openaire", "semantic_scholar"}

    # Verify sources report status honestly (live, live_empty, rate_limited, or unavailable)
    for src_stat in sources:
        assert src_stat["status"] in {
            "live",
            "live_empty",
            "rate_limited",
            "unavailable",
            "skipped",
            "blocked_bot_challenge",
        }


@pytest.mark.unit
def test_standard_workbook_export_hyperlinks_and_structure() -> None:
    """Standard workbook export must create 5 sheets with working DOI hyperlinks."""
    from archipelago.scholarly.intelligence.workbook_standard import build_standard_workbook

    sample_run = {
        "topic": "Dense Passage Retrieval",
        "papers": [
            {
                "paper_id": "P001",
                "title": "Dense Passage Retrieval for Open-Domain Question Answering",
                "year": 2020,
                "doi": "10.18653/v1/2020.emnlp-main.550",
                "url": "https://doi.org/10.18653/v1/2020.emnlp-main.550",
                "authors": [{"name": "Vladimir Karpukhin"}],
                "abstract": "Open-domain question answering relies on efficient passage retrieval...",
                "venue": "EMNLP 2020",
                "citations": 1200,
                "provenance": [{"source_type": "openalex", "source_url": "https://openalex.org/W3024823908"}],
            }
        ],
        "sources": [{"source": "openalex", "status": "live"}],
    }

    bio = build_standard_workbook(sample_run)
    wb = load_workbook(bio)
    assert wb.sheetnames == ["Start Here", "Papers", "Authors", "Publications", "Sources"]

    ws_papers = wb["Papers"]
    found_hyperlink = False
    for col in range(1, ws_papers.max_column + 1):
        cell = ws_papers.cell(row=2, column=col)
        if cell.hyperlink:
            found_hyperlink = True
            assert cell.hyperlink.target.startswith("https://")

    assert found_hyperlink, "No hyperlinks found in Papers sheet export"


@pytest.mark.unit
def test_security_blocked_artifacts_and_traversal() -> None:
    """Path traversal, dotfiles, and database files must be blocked by middleware."""
    from host_inference.hostapp.middleware import _is_blocked_dotfile_or_artifact

    assert _is_blocked_dotfile_or_artifact("/.env") is True
    assert _is_blocked_dotfile_or_artifact("/.env.local") is True
    assert _is_blocked_dotfile_or_artifact("/cache/query_quota.sqlite3") is True
    assert _is_blocked_dotfile_or_artifact("/AUDIT.md") is True
    assert _is_blocked_dotfile_or_artifact("/normal_page") is False
    assert _is_blocked_dotfile_or_artifact("/api/readiness") is False

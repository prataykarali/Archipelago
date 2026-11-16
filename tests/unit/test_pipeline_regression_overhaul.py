"""Regression tests for multi-provider discovery, pagination, relevance disambiguation, and XLSX export."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

from openpyxl import load_workbook

from archipelago.scholarly.discovery.live_sources import LiveResearchSources
from archipelago.scholarly.discovery.resilient_http import reliability_client
from archipelago.scholarly.intelligence.relevance_engine import disambiguate_query, evaluate_relevance
from archipelago.scholarly.intelligence.search import discover, validate_options
from archipelago.scholarly.intelligence.workbook import build_workbook


def _mock_resp(status_code: int, body: bytes, content_type: str = "application/json", headers: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.content = body
    resp.text = body.decode("utf-8", errors="replace")
    hdrs = {"content-type": content_type}
    if headers:
        hdrs.update(headers)
    resp.headers = hdrs
    resp.json = lambda: __import__("json").loads(body)
    return resp


def test_validate_options_supports_50_100_default_200_500() -> None:
    assert validate_options({"topic": "state space models"})["top_k"] == 100
    for k in (50, 100, 200, 500):
        assert validate_options({"topic": "state space models", "top_k": k})["top_k"] == k


def test_non_json_and_error_payload_and_429_handling() -> None:
    reliability_client().clear_cache()
    # 1. HTML instead of JSON -> parse_failed
    sess = MagicMock()
    sess.get.return_value = _mock_resp(200, b"<html><body>Gateway</body></html>", content_type="text/html")
    ls = LiveResearchSources(session=sess)
    res_html = ls.search("openalex", "state space models", 10)
    assert res_html.status == "parse_failed"
    assert res_html.records == []

    # 2. JSON error payload -> parse_failed
    reliability_client().clear_cache()
    sess.get.return_value = _mock_resp(200, b'{"error": "invalid_query"}', content_type="application/json")
    res_err = ls.search("openalex", "state space models", 10)
    assert res_err.status == "parse_failed"
    assert res_err.records == []

    # 3. 429 rate limited -> rate_limited
    reliability_client().clear_cache()
    sess.get.return_value = _mock_resp(429, b'{"error": "rate limit"}', headers={"Retry-After": "1"})
    res_rl = ls.search("openalex", "state space models", 10)
    assert res_rl.status == "rate_limited"
    assert res_rl.rate_limited is True


def test_openalex_pagination_and_malformed_record_resilience() -> None:
    reliability_client().clear_cache()
    page1_items = [
        {
            "id": f"https://openalex.org/W{i}",
            "doi": f"https://doi.org/10.1000/ssm.{i}",
            "title": f"Structured State Space Model {i}",
            "type": "article",
            "publication_date": "2024-01-01",
            "authorships": [{"author": {"display_name": f"Author {i}"}, "institutions": []}],
            "cited_by_count": i,
        }
        for i in range(100)
    ]
    # Include one malformed item (non-dict) and one missing title
    page1_items[5] = "malformed"  # type: ignore[assignment]
    page2_items = [
        {
            "id": f"https://openalex.org/W{100 + i}",
            "doi": f"https://doi.org/10.1000/ssm.{100 + i}",
            "title": f"Mamba State Space Sequence Model {100 + i}",
            "type": "article",
            "publication_date": "2024-06-01",
            "authorships": [{"author": {"display_name": f"Author {100 + i}"}, "institutions": []}],
            "cited_by_count": 10 + i,
        }
        for i in range(25)
    ]
    import json

    sess = MagicMock()
    sess.get.side_effect = [
        _mock_resp(200, json.dumps({"results": page1_items}).encode()),
        _mock_resp(200, json.dumps({"results": page2_items}).encode()),
    ]
    ls = LiveResearchSources(session=sess)
    res = ls.search("openalex", "state space model", 150)
    assert res.status == "live"
    assert res.pages_fetched == 2
    assert len(res.records) == 124


def test_space_state_model_disambiguation_and_off_domain_rejection() -> None:
    disambig = disambiguate_query("space state model")
    assert disambig["resolved_domain"] == "ai_cs"
    assert any("state space" in alt["interpretation"] for alt in disambig["alternative_interpretations"])

    # Irrelevant orbital/spacecraft paper should be rejected for AI/ML state-space query
    off = evaluate_relevance(
        "state-space models in machine learning",
        "Space State Model for Lunar Spacecraft Attitude Control",
        "We derive a nonlinear spacecraft attitude control law using orbital thruster dynamics.",
    )
    assert off["eligible"] is False

    # Relevant ML state-space paper should be accepted
    on = evaluate_relevance(
        "state-space models in machine learning",
        "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        "Structured state space models achieve strong perplexity on WikiText-103 and Long Range Arena.",
    )
    assert on["eligible"] is True


def test_standard_excludes_incomplete_papers_keeps_in_advanced_and_preserves_none() -> None:
    from tests.unit.test_standard_research_xlsx import _sample_run

    run = _sample_run()
    run["papers"][0]["citation_count"] = None
    run["papers"][0]["citations_per_year"] = None
    run["papers"][0]["citation_provider"] = None
    run["papers"][0]["methods"] = ["selective state space"]
    run["papers"][0]["datasets"] = ["wikitext-103"]
    run["papers"][0]["evaluation_metrics"] = ["perplexity"]
    run["papers"][0]["provenance"] = [
        {"source_type": "openalex", "source_url": "https://openalex.org/W1", "contribution_type": "discovery_primary", "source_record_id": "W1"},
        {"source_type": "crossref", "source_url": "https://doi.org/10.1000/mamba", "contribution_type": "stage2_enrichment", "source_record_id": "10.1000/mamba"},
    ]
    incomplete = dict(run["papers"][1])
    incomplete["paper_id"] = "p-incomplete"
    incomplete["title"] = "Untitled Fragment Without Authors"
    incomplete["authors"] = []
    incomplete["year"] = None
    incomplete["publication_date"] = None
    incomplete["doi"] = None
    incomplete["url"] = None
    incomplete["standard_eligible"] = False
    run["papers"].append(incomplete)

    std_wb = load_workbook(BytesIO(build_workbook(run, mode="standard").getvalue()))
    assert len(std_wb.sheetnames) == 5
    paper_rows = list(std_wb["Papers"].iter_rows(min_row=2, values_only=True))
    assert len(paper_rows) == 2
    assert paper_rows[0][5] is None  # missing citation stays None, never 0

    src_rows = list(std_wb["Sources"].iter_rows(min_row=2, values_only=True))
    assert ("OpenAlex", "Discovery") in {(r[1], r[3]) for r in src_rows}
    assert ("Crossref", "Enrichment") in {(r[1], r[3]) for r in src_rows}

    adv_wb = load_workbook(BytesIO(build_workbook(run, mode="advanced").getvalue()))
    assert len(adv_wb.sheetnames) == 14
    adv_paper_rows = list(adv_wb["Papers"].iter_rows(min_row=2, values_only=True))
    assert len(adv_paper_rows) == 3  # incomplete paper preserved in Advanced

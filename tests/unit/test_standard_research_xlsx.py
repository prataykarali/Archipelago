"""Unit tests for the 5-sheet Standard Research Export and dual-mode XLSX API."""

from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook
import pytest

from archipelago.scholarly.intelligence.ranking_preview import preview_run
from archipelago.scholarly.intelligence.run_dossier import build_run_dossier
from archipelago.scholarly.intelligence.workbook import build_workbook
from archipelago.scholarly.intelligence.workbook_standard import STANDARD_SHEETS

pytestmark = pytest.mark.unit

BANNED_CODES = (
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_FIELD_ABSENT",
    "LICENSE_RESTRICTED",
    "IDENTITY_UNRESOLVED",
    "NOT_AVAILABLE",
)


def _sample_run() -> dict:
    return {
        "schema": "archipelago.research_intelligence.v2",
        "export_format_version": "rich30.v1",
        "options": {"topic": "space state model", "top_k": 20, "sort": "relevance"},
        "retrieved_at": "2026-11-16T10:00:00Z",
        "ordering": "relevance",
        "sort_metadata": {"selected": "relevance", "label": "Query relevance"},
        "author_collisions": ["wei zhang"],
        "papers": [
            {
                "paper_id": "p1",
                "title": '=HYPERLINK("http://evil") State-Space Model',
                "year": 2024,
                "publication_date": "2024-03-01",
                "doi": "10.1000/ssm1",
                "url": "https://doi.org/10.1000/ssm1",
                "publication_type": "journal-article",
                "abstract": "A clean state-space model abstract.",
                "is_open_access": True,
                "evidence_status": "ABSTRACT_AVAILABLE",
                "references": [],
                "identity_review": [],
                "citation_count": 15,
                "citation_provider": "crossref",
                "citation_observations": [
                    {"provider": "openalex", "count": 12},
                    {"provider": "crossref", "count": 15},
                ],
                "identifiers": {"doi": "10.1000/ssm1", "openalex_id": "https://openalex.org/W1"},
                "authors": [
                    {
                        "name": "Zhi-Hong Han",
                        "orcid": "https://orcid.org/0000-0003-4007-3995",
                        "institutions": ["NWPU"],
                    },
                    {"name": "Wei Zhang", "institutions": ["Tsinghua"]},
                ],
                "venue": "Journal of Applied Models",
                "venue_details": {
                    "name": "Journal of Applied Models",
                    "venue_category": "peer_reviewed_journal",
                    "publisher": "Elsevier",
                    "url": "https://example.org/jam",
                    "provider": "openalex",
                },
                "topics": ["Control Theory", "State-Space Models"],
                "provenance": [
                    {"source_type": "openalex", "source_url": "https://openalex.org/W1"},
                    {"source_type": "crossref", "source_url": "https://doi.org/10.1000/ssm1"},
                ],
                "source_metadata": {
                    "author_openalex_ids": [
                        "https://openalex.org/A5119870128",
                        "https://openalex.org/A100",
                    ],
                    "author_s2_ids": ["2113962797", None],
                },
            },
            {
                "paper_id": "p2",
                "title": "Preprint State-Space Model",
                "year": 2025,
                "publication_date": "2025-01-10",
                "doi": None,
                "url": "https://arxiv.org/abs/2501.00001",
                "publication_type": "preprint",
                "abstract": None,
                "is_open_access": True,
                "evidence_status": "METADATA_ONLY",
                "references": [],
                "identity_review": [],
                "citation_count": None,
                "citation_provider": None,
                "citation_observations": [],
                "identifiers": {"arxiv_id": "2501.00001"},
                "authors": [{"name": "Wei Zhang", "institutions": ["Stanford"]}],
                "venue": "arXiv",
                "venue_details": {
                    "name": "arXiv",
                    "venue_category": "preprint_repository",
                    "publisher": None,
                    "url": "https://arxiv.org",
                    "provider": "arxiv",
                },
                "topics": ["Machine Learning"],
                "provenance": [
                    {"source_type": "arxiv", "source_url": "https://arxiv.org/abs/2501.00001"}
                ],
                "source_metadata": {"author_openalex_ids": ["https://openalex.org/A200"]},
            },
        ],
        "author_observations": [
            {
                "id": "A5119870128",
                "name": "Zhi-Hong Han",
                "orcid": "https://orcid.org/0000-0003-4007-3995",
                "provider": "openalex",
                "enrichment_status": "AVAILABLE",
                "source_url": "https://openalex.org/A5119870128",
                "metrics": {"publication_count": 40, "citation_count": 500, "h_index": 12},
                "current_affiliations": [
                    {"institution": "Northwestern Polytechnical University", "years": [2024]}
                ],
            },
            {
                "id": "s2:2113962797",
                "name": "Zhi-Hong Han",
                "provider": "semantic_scholar",
                "enrichment_status": "AVAILABLE",
                "source_url": "https://www.semanticscholar.org/author/2113962797",
                "metrics": {"publication_count": 38, "citation_count": 480, "h_index": 11},
            },
            {
                "id": "orcid:0000-0003-4007-3995",
                "name": "Zhen Han",
                "orcid": "https://orcid.org/0000-0003-4007-3995",
                "provider": "orcid",
                "enrichment_status": "AVAILABLE",
                "source_url": "https://orcid.org/0000-0003-4007-3995",
                "orcid_verified": True,
                "metrics": {"publication_count": 15, "citation_count": None, "h_index": None},
            },
            {
                "id": "A100",
                "name": "Wei Zhang",
                "provider": "openalex",
                "enrichment_status": "AVAILABLE",
                "source_url": "https://openalex.org/A100",
                "metrics": {"publication_count": 10, "citation_count": 50, "h_index": 4},
            },
            {
                "id": "A200",
                "name": "Wei Zhang",
                "provider": "openalex",
                "enrichment_status": "PROVIDER_UNAVAILABLE",
                "metrics": None,
            },
        ],
    }


def test_standard_export_has_5_sheets_no_codes_and_dedups_zhihong_han() -> None:
    wb = load_workbook(BytesIO(build_workbook(_sample_run(), mode="standard").getvalue()))
    assert tuple(wb.sheetnames) == STANDARD_SHEETS
    assert wb["Papers"].max_column == 19
    assert wb["Authors"].max_column == 20
    assert wb["Publications"].max_column == 19

    # Check no banned internal codes or JSON blobs anywhere
    for sname in wb.sheetnames:
        for row in wb[sname].iter_rows(values_only=True):
            for val in row:
                if isinstance(val, str):
                    for code in BANNED_CODES:
                        assert code not in val
                    assert not val.strip().startswith('{"')

    # Papers: 2 rows, formula neutralized, missing citation is blank (never 0)
    paper_rows = list(wb["Papers"].iter_rows(min_row=2, values_only=True))
    paper_headers = [cell.value for cell in wb["Papers"][1]]
    assert len(paper_rows) == 2
    assert str(paper_rows[0][0]).startswith("'=HYPERLINK")
    assert paper_rows[0][paper_headers.index("Citation Count")] == 15
    assert paper_rows[0][paper_headers.index("Citation Provider")] == "Crossref"
    assert paper_rows[1][paper_headers.index("Citation Count")] is None

    # Authors: Zhi-Hong Han / Zhen Han deduplicated to 1 row; Wei Zhang kept as 2 distinct rows!
    author_rows = list(wb["Authors"].iter_rows(min_row=2, values_only=True))
    assert len(author_rows) == 3
    han_rows = [r for r in author_rows if "Han" in str(r[0])]
    assert len(han_rows) == 1
    author_headers = [cell.value for cell in wb["Authors"][1]]
    assert han_rows[0][author_headers.index("Total Publications")] == 40
    assert "Semantic Scholar" in str(han_rows[0][author_headers.index("Verified Sources")])

    wei_rows = [r for r in author_rows if r[0] == "Wei Zhang"]
    assert len(wei_rows) == 2
    assert wei_rows[1][author_headers.index("Total Publications")] is None

    # Publications: 2 rows, no JIF/CiteScore/SJR/CORE, preprint not marked peer-reviewed
    pub_rows = list(wb["Publications"].iter_rows(min_row=2, values_only=True))
    assert len(pub_rows) == 2
    pub_headers = [cell.value for cell in wb["Publications"][1]]
    assert pub_rows[0][pub_headers.index("Category")] == "Peer-reviewed journal"
    assert pub_rows[1][pub_headers.index("Category")] == "Preprint repository"

    # Sources: readable per-(paper, provider) provenance rows with Discovery vs Enrichment
    src_rows = list(wb["Sources"].iter_rows(min_row=2, values_only=True))
    assert len(src_rows) == 3
    src_pairs = {(r[1], r[2], r[3]) for r in src_rows}
    assert ("OpenAlex", "View on OpenAlex", "Discovery") in src_pairs
    assert ("Crossref", "View on Crossref", "Discovery") in src_pairs
    assert ("arXiv", "View on arXiv", "Discovery") in src_pairs


def test_advanced_export_still_returns_14_sheets() -> None:
    wb = load_workbook(BytesIO(build_workbook(_sample_run(), mode="advanced").getvalue()))
    assert len(wb.sheetnames) == 14
    with pytest.raises(ValueError):
        build_workbook(_sample_run(), mode="unknown")


def test_ranking_parameters_are_individual_typed_columns() -> None:
    run = _sample_run()
    paper = run["papers"][0]
    paper.update(
        {
            "fwci": 2.5,
            "citation_normalized_percentile": {"value": 0.92},
            "influential_citations": 4,
            "references": ["https://openalex.org/W2"],
            "methods": ["State-space model"],
            "code_repo_urls": ["https://github.com/example/code"],
            "relevance_classification": {"label": "RELEVANT", "confidence": 0.87},
        }
    )
    run["author_observations"][0]["metrics"].update(
        {
            "i10_index": 8,
            "earliest_year": 2018,
            "counts_by_year": [{"year": 2026, "cited_by_count": 9}],
        }
    )
    paper["venue_details"].update(
        {
            "id": "https://openalex.org/S1",
            "works_count": 100,
            "cited_by_count": 500,
            "h_index": 12,
            "i10_index": 15,
            "openalex_2yr_mean_citedness": 2.75,
        }
    )
    run["papers"][1]["venue_details"].update(
        {"id": "https://openalex.org/S2", "works_count": 200, "h_index": 30}
    )
    book = load_workbook(BytesIO(build_workbook(run, mode="standard").getvalue()))

    def value(sheet: str, row: int, header: str):
        headings = [cell.value for cell in book[sheet][1]]
        return book[sheet].cell(row, headings.index(header) + 1).value

    assert value("Papers", 2, "Topic Relevance Score") == 0.87
    assert value("Papers", 2, "Field-Weighted Citation Impact (FWCI)") == 2.5
    assert value("Papers", 2, "Citation Percentile") == 0.92
    assert value("Papers", 2, "Influential Citation Count") == 4
    assert value("Papers", 2, "Reference Count") == 1
    assert value("Papers", 2, "Reproducibility Indicators") == "Code"
    assert value("Authors", 2, "i10-index") == 8
    assert value("Authors", 2, "Average Citations per Paper") == 12.5
    assert value("Authors", 2, "Recent Citations") == 9
    assert value("Authors", 2, "Metric Provider") == "OpenAlex"
    assert value("Publications", 2, "Venue h-index") == 12
    assert value("Publications", 2, "Mean Citedness") == 2.75
    assert "Journal Impact Factor (JIF)" in [cell.value for cell in book["Publications"][1]]
    assert "CiteScore" in [cell.value for cell in book["Publications"][1]]
    assert value("Publications", 3, "Venue h-index") is None


def test_standard_export_revalidates_old_runs_and_deduplicates_works() -> None:
    run = _sample_run()
    duplicate = {**run["papers"][0], "paper_id": "duplicate-provider-record"}
    reordered_author = {
        **run["papers"][1],
        "paper_id": "reordered-author",
        "authors": [{"name": "Zhang, Wei"}],
    }
    invalid = {
        **run["papers"][0],
        "paper_id": "invalid",
        "title": "Irrelevant record",
        "relevance_classification": {"eligible": False},
    }
    run["papers"].extend([duplicate, reordered_author, invalid])
    book = load_workbook(BytesIO(build_workbook(run, mode="standard").getvalue()))
    assert book["Papers"].max_row == 3
    assert book["Sources"].max_row == 4
    assert book["Start Here"]["B9"].value == 2


def test_standard_export_deduplicates_matching_titles_with_different_provider_ids() -> None:
    run = _sample_run()
    duplicate = {
        **run["papers"][0],
        "paper_id": "another-provider-id",
        "doi": "10.5555/alternate-record",
        "authors": [{"name": "Different, Indexing"}],
    }
    run["papers"].append(duplicate)
    book = load_workbook(BytesIO(build_workbook(run, mode="standard").getvalue()))
    assert book["Papers"].max_row == 3


def test_title_only_does_not_claim_methods_datasets_or_metrics() -> None:
    from archipelago.scholarly.intelligence.extraction import extract_evidence

    found = extract_evidence("Transformer on MNIST with accuracy", None)
    assert found["methods"] == []
    assert found["datasets"] == []
    assert found["evaluation_metrics"] == []


def test_state_space_query_rejects_incidental_state_space_mentions() -> None:
    from archipelago.scholarly.intelligence.search import assess_topic_eligibility

    irrelevant, reason = assess_topic_eligibility(
        "state-space models in machine learning",
        "Dynamic resource allocation using machine learning",
        "The agent explores a state space and action space using reinforcement learning.",
    )
    relevant, _ = assess_topic_eligibility(
        "state-space models in machine learning",
        "Selective State Space Models for Sequence Learning",
        "We train a Mamba model on sequence data.",
    )
    assert not irrelevant
    assert reason == "missing_central_concepts:state_space_model"
    assert relevant
    incidental, _ = assess_topic_eligibility(
        "state-space models in machine learning",
        "Machine Learning Techniques in Optical Communication",
        "State-space models are mentioned as one of many possible approaches.",
    )
    assert not incidental


def test_authenticated_xlsx_route_supports_standard_and_advanced_modes(
    tmp_path, monkeypatch
) -> None:
    from pathlib import Path
    import sys

    from flask import Flask
    from flask import request as flask_request

    host_dir = str(Path(__file__).resolve().parents[2] / "host_inference")
    if host_dir not in sys.path:
        sys.path.insert(0, host_dir)
    monkeypatch.setenv("ARCHIPELAGO_SQLITE_PATH", str(tmp_path / "test_xlsx_routes.sqlite3"))
    from hostapp.routes.research_intelligence import register

    import archipelago.scholarly.intelligence.storage as storage_mod

    store = storage_mod.ResearchStore(tmp_path / "test_xlsx_routes.sqlite3")
    monkeypatch.setattr(storage_mod, "hosted_store", lambda: store)
    run_id = store.save_run("test-user", _sample_run())
    app = Flask(__name__)

    @app.before_request
    def _inject_principal() -> None:
        vars(flask_request)["archipelago_principal"] = {"id": "test-user", "role": "researcher"}

    register(app, None)  # type: ignore[arg-type]
    client = app.test_client()

    r_default = client.get(f"/api/research/intelligence/runs/{run_id}/xlsx")
    assert r_default.status_code == 200
    assert load_workbook(BytesIO(r_default.data)).sheetnames == list(STANDARD_SHEETS)

    r_adv = client.get(f"/api/research/intelligence/runs/{run_id}/xlsx?mode=advanced")
    assert r_adv.status_code == 200
    assert len(load_workbook(BytesIO(r_adv.data)).sheetnames) == 14

    r_bad = client.get(f"/api/research/intelligence/runs/{run_id}/xlsx?mode=bogus")
    assert r_bad.status_code == 400

    old_run = _sample_run()
    old_run.pop("export_format_version")
    old_run_id = store.save_run("test-user", old_run)
    assert client.get(f"/api/research/intelligence/runs/{old_run_id}").status_code == 410
    assert client.get(f"/api/research/intelligence/runs/{old_run_id}/xlsx").status_code == 410

    r_preview = client.get(f"/api/research/intelligence/runs/{run_id}/preview")
    assert r_preview.status_code == 200
    preview = r_preview.get_json()
    workbook = load_workbook(BytesIO(r_default.data))
    for name in ("Papers", "Authors", "Publications"):
        assert preview["sheets"][name]["headers"] == [cell.value for cell in workbook[name][1]]
        assert len(preview["sheets"][name]["rows"]) == workbook[name].max_row - 1
    assert preview["sheets"]["Papers"]["rows"][0]["values"][0].startswith("'=HYPERLINK")

    r_dossier = client.get(f"/api/research/intelligence/runs/{run_id}/dossier")
    assert r_dossier.status_code == 200
    assert r_dossier.get_json()["paper_count"] == len(preview["sheets"]["Papers"]["rows"])

    import uuid

    request_id = uuid.uuid4()
    pending = client.get(f"/api/research/intelligence/search-status/{request_id}")
    assert pending.get_json() == {"status": "pending"}
    recovered_run = {**_sample_run(), "client_request_id": str(request_id)}
    recovered_id = store.save_run("test-user", recovered_run)
    completed = client.get(f"/api/research/intelligence/search-status/{request_id}")
    assert completed.get_json() == {"status": "completed", "run_id": recovered_id}


def test_dossier_uses_cleaned_workbook_rows_and_source_evidence() -> None:
    run = _sample_run()
    run["papers"][0]["methods"] = [
        {"name": "state space model", "evidence": "A clean state-space model abstract."},
        {"name": "invented result", "evidence": "A claim absent from the source"},
    ]
    dossier = build_run_dossier(run)
    preview = preview_run(run)
    assert dossier["paper_count"] == len(preview["sheets"]["Papers"]["rows"])
    assert dossier["author_count"] == len(preview["sheets"]["Authors"]["rows"])
    assert (
        dossier["papers"][0]["rankable_values"] == preview["sheets"]["Papers"]["rows"][0]["values"]
    )
    assert dossier["papers"][0]["extracted"]["methods"] == [
        {
            "name": "state space model",
            "evidence": "A clean state-space model abstract.",
            "location": "",
        }
    ]
    assert dossier["extracted_counts"]["methods"] == {"state space model": 1}
    assert dossier["papers"][0]["sources"][0]["url"] == "https://openalex.org/W1"


def test_rankable_preview_contains_requested_columns_without_fabricating_metrics() -> None:
    preview = preview_run(_sample_run())
    paper_headers = preview["sheets"]["Papers"]["headers"]
    author_headers = preview["sheets"]["Authors"]["headers"]
    venue_headers = preview["sheets"]["Publications"]["headers"]
    assert "Citation Count" in paper_headers
    assert "Benchmark Performance" in paper_headers
    assert "Reproducibility Indicators" in paper_headers
    assert "g-index" in author_headers
    assert "Field-Normalized Impact" in author_headers
    assert "Journal Impact Factor (JIF)" in venue_headers
    assert "h5-index" in venue_headers
    assert (
        preview["sheets"]["Papers"]["rows"][0]["values"][
            paper_headers.index("Benchmark Performance")
        ]
        is None
    )
    assert {
        "Citation Count",
        "Citations per Year",
        "Field-Weighted Citation Impact (FWCI)",
        "Citation Percentile",
        "Topic Relevance Score",
        "Publication Year",
        "Benchmark Performance",
        "Methodological Evidence",
        "Reproducibility Indicators",
        "Reference Count",
        "Influential Citation Count",
        "Open-Access Status",
    }.issubset(paper_headers)
    assert {
        "h-index",
        "i10-index",
        "g-index",
        "m-quotient",
        "Total Citations",
        "Total Publications",
        "Average Citations per Paper",
        "Median Citations per Paper",
        "Recent Citations",
        "Field-Normalized Impact",
        "First-Author Publications",
        "Last-Author Publications",
        "Research Relevance",
        "Collaboration Network",
    }.issubset(author_headers)
    assert {
        "Journal Impact Factor (JIF)",
        "CiteScore",
        "SCImago Journal Rank (SJR)",
        "Source Normalized Impact per Paper (SNIP)",
        "Q1-Q4 Quartile",
        "CORE/ICORE Rank",
        "h5-index",
        "h5-median",
        "Venue h-index",
        "Venue i10-index",
        "Acceptance Rate",
        "Indexed Publication Count",
        "Mean Citedness",
        "Indexing Status",
    }.issubset(venue_headers)


def test_evidence_objects_export_as_readable_names() -> None:
    run = _sample_run()
    run["papers"][0]["methods"] = [
        {"name": "state space model", "evidence": "untrusted abstract snippet"},
        {"name": "transformer", "evidence": "more text"},
    ]
    preview = preview_run(run)
    headers = preview["sheets"]["Papers"]["headers"]
    row = preview["sheets"]["Papers"]["rows"][0]["values"]
    assert row[headers.index("Methodological Evidence")] == "state space model, transformer"


def test_venue_name_with_year_is_not_exported_as_an_author() -> None:
    run = _sample_run()
    run["papers"][0]["authors"].insert(
        0, {"name": "Association for Computational Linguistics 2025"}
    )
    preview = preview_run(run)
    authors = preview["sheets"]["Authors"]
    assert all(
        "Association for Computational Linguistics" not in row["values"][0]
        for row in authors["rows"]
    )
    paper_authors = preview["sheets"]["Papers"]["rows"][0]["values"][1]
    assert "Association for Computational Linguistics" not in paper_authors

"""Unit tests for the 5-sheet Standard Research Export and dual-mode XLSX API."""

from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook
import pytest

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
        "options": {"topic": "space state model", "top_k": 20, "sort": "relevance"},
        "retrieved_at": "2026-11-16T10:00:00Z",
        "ordering": "relevance",
        "sort_metadata": {"selected": "relevance", "label": "Query relevance"},
        "author_collisions": ["wei zhang"],
        "papers": [
            {
                "paper_id": "p1",
                "title": "=HYPERLINK(\"http://evil\") State-Space Model",
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
                "citation_observations": [{"provider": "openalex", "count": 12}, {"provider": "crossref", "count": 15}],
                "identifiers": {"doi": "10.1000/ssm1", "openalex_id": "https://openalex.org/W1"},
                "authors": [
                    {"name": "Zhi-Hong Han", "orcid": "https://orcid.org/0000-0003-4007-3995", "institutions": ["NWPU"]},
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
                    "author_openalex_ids": ["https://openalex.org/A5119870128", "https://openalex.org/A100"],
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
                "provenance": [{"source_type": "arxiv", "source_url": "https://arxiv.org/abs/2501.00001"}],
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
                "current_affiliations": [{"institution": "Northwestern Polytechnical University", "years": [2024]}],
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

    # Check no banned internal codes or JSON blobs anywhere
    for sname in wb.sheetnames:
        for row in wb[sname].iter_rows(values_only=True):
            for val in row:
                if isinstance(val, str):
                    for code in BANNED_CODES:
                        assert code not in val
                    assert not val.strip().startswith('{"')

    # Papers: 2 rows, formula neutralized, missing citation stays None (never 0)
    paper_rows = list(wb["Papers"].iter_rows(min_row=2, values_only=True))
    assert len(paper_rows) == 2
    assert str(paper_rows[0][0]).startswith("'=HYPERLINK")
    assert paper_rows[0][5] == 15
    assert paper_rows[0][7] == "Crossref"
    assert paper_rows[1][5] is None

    # Authors: Zhi-Hong Han / Zhen Han deduplicated to 1 row; Wei Zhang kept as 2 distinct rows!
    author_rows = list(wb["Authors"].iter_rows(min_row=2, values_only=True))
    assert len(author_rows) == 3
    han_rows = [r for r in author_rows if "Han" in str(r[0])]
    assert len(han_rows) == 1
    assert han_rows[0][3] == 40  # OpenAlex count, not blended
    assert "Semantic Scholar" in str(han_rows[0][8])

    wei_rows = [r for r in author_rows if r[0] == "Wei Zhang"]
    assert len(wei_rows) == 2
    assert wei_rows[1][3] is None  # missing stays None, not 0 or PROVIDER_UNAVAILABLE

    # Publications: 2 rows, no JIF/CiteScore/SJR/CORE, preprint not marked peer-reviewed
    pub_rows = list(wb["Publications"].iter_rows(min_row=2, values_only=True))
    assert len(pub_rows) == 2
    assert pub_rows[0][1] == "Peer-reviewed journal"
    assert pub_rows[0][4] == 1
    assert pub_rows[1][1] == "Preprint repository"
    assert pub_rows[1][4] == 1

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


def test_authenticated_xlsx_route_supports_standard_and_advanced_modes(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    import sys

    from flask import Flask, request as flask_request

    host_dir = str(Path(__file__).resolve().parents[2] / "host_inference")
    if host_dir not in sys.path:
        sys.path.insert(0, host_dir)
    monkeypatch.setenv("ARCHIPELAGO_SQLITE_PATH", str(tmp_path / "test_xlsx_routes.sqlite3"))
    import archipelago.scholarly.intelligence.storage as storage_mod
    from hostapp.routes.research_intelligence import register

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

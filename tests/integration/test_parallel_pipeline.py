"""Discovery pipeline contracts with deterministic source responses."""

from __future__ import annotations

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.pipeline.parallel_harvester import ParallelHarvester
from archipelago.scholarly.pipeline.scheduler import HarvestScheduler


def _candidate(source: str, title: str, mode: str) -> dict:
    provenance = ProvenancePointer(
        source_type=source,
        artifact_sha256="a" * 64,
        source_record_id=source + "_1",
        source_url="https://example.org/record",
    )
    return {
        "source": source,
        "paper": PaperRecord(
            title=title,
            identifiers=PaperIdentifiers(),
            authors=[PaperAuthor(name="Researcher")],
            oa_url="https://example.org/record",
        ),
        "provenance": provenance,
        "retrieval_mode": mode,
    }


def test_parallel_harvester_distinguishes_live_records_and_links(monkeypatch, tmp_path):
    """Blocked sources cannot count as live evidence or SLM training data."""
    import archipelago.scholarly.pipeline.parallel_harvester as module

    monkeypatch.setattr(module, "CATALOGS_DIR", tmp_path)
    harvester = ParallelHarvester(use_api_anything=False)
    monkeypatch.setattr(
        harvester, "fetch_arxiv", lambda *a, **k: [_candidate("arxiv", "Live arXiv paper", "live")]
    )
    monkeypatch.setattr(
        harvester,
        "fetch_opac",
        lambda *a, **k: [_candidate("pearson_bookshelf", "Pearson book", "catalog_fallback")],
    )
    monkeypatch.setattr(
        harvester,
        "fetch_iemcrp",
        lambda *a, **k: [_candidate("iemcrp_manifest", "Portal link", "link_manifest")],
    )
    monkeypatch.setattr(harvester, "fetch_scholar", lambda *a, **k: [])
    monkeypatch.setattr(
        harvester,
        "fetch_openalex",
        lambda *a, **k: [_candidate("openalex", "Live OpenAlex paper", "live")],
    )

    result = harvester.harvest_parallel("graph retrieval", persist=False)
    assert result["counts"] == {
        "arxiv": 1,
        "opac": 0,
        "iemcrp": 0,
        "google_scholar": 0,
        "openalex": 1,
    }
    assert result["source_status"]["opac"]["mode"] == "fallback"
    assert result["source_status"]["iemcrp"]["mode"] == "fallback"
    assert result["source_status"]["google_scholar"]["mode"] == "link_only"
    assert [item["source"] for item in result["manifest"]["items"]] == ["arxiv", "openalex"]
    assert {item["source"] for item in result["manifest"]["resources"]} == {
        "pearson_bookshelf",
        "iemcrp_manifest",
    }
    assert result["new_stacked_training_pairs"] == 0
    assert not list(tmp_path.glob("*.json"))


def test_scholar_never_fabricates_a_paper():
    """A search URL is a navigation link, not a publication."""
    from archipelago.scholarly.discovery.scholar_adapter import GoogleScholarAdapter

    adapter = GoogleScholarAdapter()
    assert adapter.search("graph retrieval") == []
    assert adapter.verification_url("graph retrieval").startswith(
        "https://scholar.google.com/scholar?"
    )


def test_scheduler_cron_uses_importable_module():
    """Cron launches the package module from the project root."""
    scheduler = HarvestScheduler(interval_hours=12.0)
    cron = scheduler.print_crontab_entry()
    assert "0 0,12 * * *" in cron
    assert "-m archipelago.scholarly.pipeline.scheduler --run-once" in cron

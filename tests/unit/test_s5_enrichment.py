"""S5 author identity and hosted packaging checks."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from archipelago.scholarly.intelligence.enrichment import enrich_authors, venue_observation
from archipelago.scholarly.intelligence.storage import hosted_store

pytestmark = pytest.mark.unit


class AuthorResponse:
    """One provider response for a linked identity."""

    def raise_for_status(self) -> None:
        """Represent a successful provider call."""

    def json(self) -> dict:
        """Supply metrics with explicit provider identity."""
        return {
            "id": "https://openalex.org/A123",
            "display_name": "J. Researcher",
            "works_count": 12,
            "cited_by_count": 34,
            "summary_stats": {"h_index": 4, "i10_index": 1},
            "affiliations": [],
        }


class AuthorSession:
    """Reject unexpected author lookups."""

    def get(self, url: str, timeout: int) -> AuthorResponse:
        """Allow only the validated OpenAlex ID."""
        assert url == "https://api.openalex.org/authors/A123"
        assert timeout > 0
        return AuthorResponse()


def test_same_name_does_not_merge_without_provider_id() -> None:
    papers = [
        {"authors": [{"name": "J. Researcher"}], "source_metadata": {}},
        {
            "authors": [{"name": "J. Researcher"}],
            "source_metadata": {"author_openalex_ids": ["https://openalex.org/A123"]},
        },
    ]
    observations = enrich_authors(papers, AuthorSession())
    assert len(observations) == 1
    assert observations[0]["id"] == "A123"
    assert observations[0]["metrics"]["h_index"] == 4
    assert observations[0]["metrics"]["i10_index"] == 1


def test_untrusted_author_id_cannot_be_used_as_url() -> None:
    paper = {
        "authors": [{"name": "An attacker"}],
        "source_metadata": {"author_openalex_ids": ["https://localhost/private"]},
    }
    assert enrich_authors([paper], AuthorSession()) == []


def test_venue_metrics_remain_unavailable_without_evidence() -> None:
    paper = {
        "venue": "Example Journal",
        "citation_provider": "openalex",
        "source_metadata": {"venue_id": "https://openalex.org/S123", "venue_issn": ["1234-5678"]},
    }
    venue = venue_observation(paper, "2026-11-12T00:00:00+00:00")
    assert venue is not None
    assert venue["id"] == "https://openalex.org/S123"
    assert venue["impact_factor"] is None
    assert venue["citescore"] is None


def test_hosted_store_fails_closed_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("ARCHIPELAGO_RESEARCH_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="research_storage_not_configured"):
        hosted_store()


def test_hosted_runtime_copy_matches_source() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["python3", "scripts/ops/sync_s5_host_runtime.py", "--check"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout

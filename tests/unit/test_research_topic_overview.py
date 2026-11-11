"""Topic dossier includes only active local papers and reported values."""

from __future__ import annotations

from pathlib import Path
import sys

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.research_topic_overview import build_topic_overview  # noqa: E402


def _paper(key: str, *, pipeline: str = "local_indra_v3", active: bool = True) -> dict:
    return {
        "kind": "paper",
        "record_key": key * 64,
        "title": f"Paper {key}",
        "topic": "Pedestrian Detection",
        "source_name": "OpenAlex",
        "source_url": "https://openalex.org/W123",
        "content": "We propose a method for pedestrian detection.",
        "published_at": "2024-01-01",
        "metadata": {
            "ingestion_pipeline": pipeline,
            "active": active,
            "access_state": "METADATA_ONLY",
            "citation_count": 0,
            "authors": [{"name": "A. Researcher"}],
        },
    }


def test_topic_overview_excludes_old_and_retired_papers() -> None:
    overview = build_topic_overview(
        "Pedestrian Detection",
        [_paper("a"), _paper("b", pipeline="legacy"), _paper("c", active=False)],
    )
    assert overview["paper_count"] == 1
    assert [paper["key"] for paper in overview["papers"]] == ["a" * 64]
    assert overview["papers"][0]["citation_count"] == 0
    assert overview["section_coverage"]["identity"] == 1
    assert overview["access_states"] == {"METADATA_ONLY": 1}
    assert overview["publication_years"] == {"2024": 1}


def test_topic_quote_count_excludes_unmatched_claims() -> None:
    row = _paper("d")
    row["metadata"]["verified_extractions"] = [
        {
            "group": "experiments",
            "field": "datasets",
            "value": "Imaginary Dataset",
            "evidence_text": "We used Imaginary Dataset.",
            "verification_status": "abstract_quote_matched",
        }
    ]
    overview = build_topic_overview("Pedestrian Detection", [row])
    assert overview["papers"][0]["quoted_facts"] == 0

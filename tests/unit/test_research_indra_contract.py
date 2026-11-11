"""Verify page evidence and complete OKF fields without external services."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from archipelago.scholarly.acquisition.indra_parser import parse_with_indra
from archipelago.scholarly.acquisition.pdf_parser import PDFParser
from archipelago.scholarly.contracts.research_contract import FIELDS
from archipelago.scholarly.extraction.structured_okf import build_paper_okf
from host_inference.hostapp.research_okf import build_paper_okf as build_host_okf

pytestmark = pytest.mark.unit


def test_host_and_worker_evidence_rules_stay_in_sync() -> None:
    """The Vercel bundle carries a local copy of the worker's evidence gate."""
    root = Path(__file__).resolve().parents[2]
    worker = root / "archipelago/scholarly/extraction/semantic_guard.py"
    hosted = root / "host_inference/hostapp/research_evidence_guard.py"
    assert worker.read_text(encoding="utf-8") == hosted.read_text(encoding="utf-8")


def test_indra_parser_keeps_page_and_section(monkeypatch: pytest.MonkeyPatch) -> None:
    """Indra text is usable as page-linked SLM evidence."""
    page = SimpleNamespace(
        text="Abstract. We evaluated on the MoleculeNet dataset.",
        source="ocr",
        blocks=[
            {"label": "Section-Header", "text": "Abstract", "bbox": [0, 0, 1, 1]},
            {
                "label": "Text",
                "text": "We evaluated on the MoleculeNet dataset.",
                "bbox": [0, 1, 2, 2],
            },
        ],
    )
    converter = SimpleNamespace(convert=lambda *_args, **_kwargs: iter([(0, page)]))
    monkeypatch.setitem(sys.modules, "indra_ocr", SimpleNamespace(load=lambda **_kwargs: converter))
    parsed = parse_with_indra(Path("paper.pdf"), "abc")
    assert parsed["ocr_engine"] == "indra"
    assert parsed["sections"]["abstract"][1]["page"] == 1
    assert parsed["sections"]["abstract"][1]["ocr_source"] == "ocr"


def test_indra_recognizes_plain_text_abstract_heading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Indra's ordinary-text label must not hide PDF abstract evidence."""
    page = SimpleNamespace(
        text="Abstract—We introduce the Bengali speech dataset. I. INTRODUCTION",
        source="text",
        blocks=[
            {"label": "Text", "text": "Abstract—We introduce the Bengali speech dataset."},
            {"label": "Text", "text": "I. INTRODUCTION"},
            {"label": "Text", "text": "Speech recognition research continues."},
        ],
    )
    converter = SimpleNamespace(convert=lambda *_args, **_kwargs: iter([(0, page)]))
    monkeypatch.setitem(sys.modules, "indra_ocr", SimpleNamespace(load=lambda **_kwargs: converter))
    parsed = parse_with_indra(Path("paper.pdf"), "abc")
    assert parsed["sections"]["abstract"][0]["page"] == 1
    assert parsed["sections"]["introduction"][1]["text"].startswith("Speech")
    assert PDFParser()._detect_section("III. METHODS") == "methods"
    assert PDFParser()._detect_section("III. DATASET PREPARATION") == "experiments"
    assert PDFParser()._detect_section("IV. CLASSIFICATION EXPERIMENTS") == "experiments"


@pytest.mark.parametrize("builder", [build_paper_okf, build_host_okf])
def test_complete_contract_preserves_unknowns_and_provenance(builder) -> None:
    """Both local and Vercel paths expose each field without invented values."""
    record = {
        "kind": "paper",
        "record_key": "a" * 64,
        "title": "Dataset evaluation",
        "source_name": "openalex",
        "source_url": "https://openalex.org/W1",
        "content": "We evaluated on the MoleculeNet dataset.",
        "metadata": {"citation_count": 12, "source_timestamp": "2026-10-26T00:00:00Z"},
    }
    okf = builder(record, "molecule data")
    assert okf["contract_version"] == "3.0.0"
    assert all(set(okf[group]) == set(names.split()) for group, names in FIELDS.items())
    assert okf["citation_metrics"]["citation_count"]["value"] == 12
    assert okf["venue_metrics"]["impact_factor"]["status"] == "unknown"
    assert okf["venue_metrics"]["impact_factor"]["value"] is None
    assert len(okf["feature_observations"]) == sum(len(names.split()) for names in FIELDS.values())
    assert okf["feature_observations"][0]["paper_id"] == "a" * 64


@pytest.mark.parametrize("builder", [build_paper_okf, build_host_okf])
def test_source_placeholders_do_not_become_reported_values(builder) -> None:
    """Sparse metadata keeps placeholders out of the visual contract."""
    record = {
        "kind": "paper",
        "record_key": "c" * 64,
        "title": "Sparse source",
        "source_name": "crossref",
        "source_url": "https://doi.org/10.1000/example",
        "metadata": {"publisher": "unknown", "authors": []},
    }
    okf = builder(record)
    assert okf["identity"]["publisher"]["value"] is None
    assert okf["identity"]["publisher"]["status"] == "unknown"
    assert okf["authors"]["author_name"]["value"] is None


@pytest.mark.parametrize("builder", [build_paper_okf, build_host_okf])
def test_new_contract_field_requires_pdf_quote_and_matching_hash(builder) -> None:
    """A new field can be populated only by a checked page-linked quote."""
    record = {
        "kind": "paper",
        "record_key": "b" * 64,
        "title": "Trial",
        "source_name": "arxiv",
        "source_url": "https://arxiv.org/abs/1",
        "metadata": {
            "pdf_sha256": "verified-hash",
            "verified_extractions": [
                {
                    "group": "methodology",
                    "field": "optimization_methods",
                    "value": "Adam",
                    "evidence_text": "We trained with Adam.",
                    "pdf_page": 2,
                    "pdf_sha256": "verified-hash",
                    "verification_status": "quote_matched",
                    "source_api": "indra_pdf_local_slm",
                }
            ],
        },
    }
    observation = builder(record)["methodology"]["optimization_methods"]
    assert observation["value"] == "Adam"
    assert observation["page_number"] == 2
    record["metadata"]["verified_extractions"][0]["pdf_sha256"] = "other"
    assert builder(record)["methodology"]["optimization_methods"]["status"] == "unknown"


@pytest.mark.parametrize("builder", [build_paper_okf, build_host_okf])
def test_dataset_name_without_dataset_evidence_is_rejected(builder) -> None:
    """A common noun in a quote cannot verify a named dataset."""
    record = {
        "kind": "paper",
        "record_key": "d" * 64,
        "title": "Pedestrian obstacles",
        "source_name": "arxiv",
        "source_url": "https://arxiv.org/abs/2",
        "content": "Pedestrian movement can be difficult.",
        "metadata": {
            "verified_extractions": [
                {
                    "group": "experiments",
                    "field": "datasets",
                    "value": "PEDESTRIAN",
                    "evidence_text": "Pedestrian movement can be difficult.",
                    "verification_status": "abstract_quote_matched",
                }
            ]
        },
    }
    okf = builder(record)
    assert okf["parameters"]["experiments"]["datasets"]["value"] is None
    assert okf["datasets"]["dataset_names"]["value"] is None

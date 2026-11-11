"""Local paper ingestion exports evidence-backed OKF v2 records."""

from __future__ import annotations

import json

from pytest import MonkeyPatch

from archipelago.scholarly.contracts.okf_models import (
    DatasetRecord,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.extraction.local_okf_v2 import export_local_paper_okf
from archipelago.scholarly.extraction.slm_paper_fields import (
    extract_slm_paper_fields,
    verify_candidates,
)


def test_local_okf_exports_verified_pdf_fields_only() -> None:
    paper = PaperRecord(
        title="A tested model",
        identifiers=PaperIdentifiers(doi="10.1000/test"),
        abstract="A model was tested.",
    )
    provenance = ProvenancePointer(
        source_type="pdf",
        artifact_sha256="a" * 64,
        page=3,
        section_id="experiments",
    )
    dataset = DatasetRecord(name="MNIST", provenance_ids=[provenance.provenance_id])
    item = {"paper": paper, "source": "OpenAlex", "citation_count": 5}
    parsed = {"sections": {"experiments": [{"page": 3, "text": "We evaluated on MNIST."}]}}
    extraction = {
        "verification_state": "validated",
        "datasets": [dataset],
        "provenance": [provenance],
    }
    result = export_local_paper_okf(item, "tested model", extraction, parsed)
    parameters = result["parameters"]
    assert parameters["paper_identity"]["doi"]["value"] == "10.1000/test"
    assert parameters["experiments"]["datasets"]["value"] == ["MNIST"]
    assert parameters["experiments"]["datasets"]["provenance"][0]["pdf_page"] == 3
    assert parameters["author_metrics"]["h_index"]["status"] == "unknown"
    parsed["sections"]["experiments"][0]["text"] = "No dataset reported."
    unverified = export_local_paper_okf(item, "tested model", extraction, parsed)
    assert unverified["parameters"]["experiments"]["datasets"]["status"] == "not_reported"


def test_slm_candidates_need_literal_value_and_exact_page_quote() -> None:
    spans = [{"pdf_page": 3, "section": "experiments", "text": "We evaluated on MNIST."}]
    candidates = [
        {
            "group": "experiments",
            "field": "datasets",
            "value": "MNIST",
            "evidence_text": "evaluated on MNIST",
            "pdf_page": 3,
            "section": "experiments",
        },
        {
            "group": "experiments",
            "field": "datasets",
            "value": "ImageNet",
            "evidence_text": "evaluated on MNIST",
            "pdf_page": 3,
            "section": "experiments",
        },
        {
            "group": "experiments",
            "field": "datasets",
            "value": "MNIST",
            "evidence_text": "evaluated on MNIST",
            "pdf_page": 4,
            "section": "experiments",
        },
    ]
    verified = verify_candidates(candidates, spans)
    assert len(verified) == 1
    assert verified[0]["verification_status"] == "quote_matched"


def test_slm_accepts_fenced_json_only_after_quote_check(monkeypatch: MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            candidate = {
                "group": "experiments",
                "field": "datasets",
                "value": "MNIST",
                "evidence_text": "We evaluated on MNIST.",
                "pdf_page": 3,
                "section": "experiments",
            }
            return {
                "message": {"content": "```json\n" + json.dumps({"fields": [candidate]}) + "\n```"}
            }

    monkeypatch.setattr(
        "archipelago.scholarly.extraction.slm_paper_fields.requests.post",
        lambda *_args, **_kwargs: Response(),
    )
    parsed = {"sections": {"experiments": [{"page": 3, "text": "We evaluated on MNIST."}]}}
    assert extract_slm_paper_fields(parsed)[0]["value"] == "MNIST"


def test_slm_extracts_separate_pages_without_truncating_other_results(
    monkeypatch: MonkeyPatch,
) -> None:
    """Each selected source span gets a bounded generation and its own quote check."""
    prompts: list[dict] = []

    class Response:
        def __init__(self, candidate: dict) -> None:
            self.candidate = candidate

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": json.dumps({"fields": [self.candidate]})}}

    def post(_url: str, **kwargs) -> Response:
        prompt = json.loads(kwargs["json"]["messages"][1]["content"])
        prompts.append(prompt)
        span = prompt["spans"][0]
        if span["section"] == "experiments":
            return Response(
                {
                    "group": "experiments",
                    "field": "datasets",
                    "value": "MNIST",
                    "evidence_text": "We evaluated on MNIST.",
                    "pdf_page": 3,
                    "section": "experiments",
                }
            )
        return Response(
            {
                "group": "methodology",
                "field": "techniques",
                "value": "LoRA",
                "evidence_text": "We introduce LoRA.",
                "pdf_page": 1,
                "section": "abstract",
            }
        )

    monkeypatch.setattr("archipelago.scholarly.extraction.slm_paper_fields.requests.post", post)
    parsed = {
        "sections": {
            "abstract": [{"page": 1, "text": "We introduce LoRA."}],
            "experiments": [{"page": 3, "text": "We evaluated on MNIST."}],
        }
    }
    result = extract_slm_paper_fields(parsed)
    assert {(field["field"], field["pdf_page"]) for field in result} == {
        ("datasets", 3),
        ("techniques", 1),
    }
    assert len(prompts) == 2
    assert all(len(prompt["spans"]) == 1 for prompt in prompts)


def test_new_contract_dataset_field_requires_pdf_quote() -> None:
    spans = [
        {
            "pdf_page": 2,
            "section": "experiments",
            "text": "We evaluate on the Bengali Speech Corpus.",
        }
    ]
    candidate = {
        "group": "datasets",
        "field": "dataset_names",
        "value": "Bengali Speech Corpus",
        "evidence_text": "We evaluate on the Bengali Speech Corpus.",
        "pdf_page": 2,
        "section": "experiments",
    }
    assert verify_candidates([candidate], spans)[0]["field"] == "dataset_names"
    assert verify_candidates([{**candidate, "value": "Imaginary Corpus"}], spans) == []

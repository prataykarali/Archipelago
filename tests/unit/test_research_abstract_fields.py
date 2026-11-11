"""Scientific abstract extraction must reject unsupported or invented values."""

from __future__ import annotations

from archipelago.scholarly.extraction import abstract_fields
from archipelago.scholarly.extraction.abstract_fields import verify_abstract_fields


def test_verified_abstract_field_requires_literal_value() -> None:
    abstract = "We evaluate GraphSAGE on Reddit datasets."
    candidates = [
        {"group": "experiments", "field": "datasets", "value": "Reddit"},
        {"group": "experiments", "field": "datasets", "value": "ImageNet"},
        {"group": "efficiency", "field": "flops", "value": "Reddit"},
    ]
    result = verify_abstract_fields(candidates, abstract)
    assert len(result) == 1
    assert result[0]["value"] == "Reddit"
    assert result[0]["evidence_text"] == abstract
    assert result[0]["verification_status"] == "abstract_quote_matched"


def test_dataset_followup_only_keeps_named_source_value(monkeypatch) -> None:
    def model_response(_abstract, prompt_path):
        if prompt_path == abstract_fields.PROMPT_PATH:
            return {"group": "methodology", "field": "techniques", "value": "Bayesian learning"}
        return [
            {"group": "experiments", "field": "datasets", "value": "QM9"},
            {"group": "experiments", "field": "datasets", "value": "ImageNet"},
        ]

    monkeypatch.setattr(abstract_fields, "_model_candidates", model_response)
    result = abstract_fields.extract_abstract_fields(
        "We use Bayesian learning on the QM9 regression dataset."
    )
    assert [(item["field"], item["value"]) for item in result] == [
        ("techniques", "Bayesian learning"),
        ("datasets", "QM9"),
    ]


def test_dataset_quote_must_name_a_dataset_in_that_sentence() -> None:
    abstract = (
        "Pedestrian movement can be difficult. "
        "We introduce the PEDESTRIAN dataset for pavement obstacle detection."
    )
    result = verify_abstract_fields(
        [{"group": "experiments", "field": "datasets", "value": "PEDESTRIAN"}],
        abstract,
    )
    assert len(result) == 1
    assert result[0]["evidence_text"].startswith("We introduce")
    assert verify_abstract_fields(
        [{"group": "experiments", "field": "datasets", "value": "PEDESTRIAN"}],
        "Pedestrian movement can be difficult.",
    ) == []


def test_ingestion_model_resolves_after_environment_load(monkeypatch) -> None:
    """The queue worker imports extraction code before loading its .env file."""
    monkeypatch.setenv("ARCHIPELAGO_INGESTION_MODEL", "dual-ingest:test")
    assert abstract_fields.ingestion_model_name() == "dual-ingest:test"

"""Literal quotes still need to describe the OKF role they claim."""

from __future__ import annotations

from archipelago.scholarly.extraction.research_abstract_fallback import (
    extract_fallback_abstract_fields,
)
from archipelago.scholarly.extraction.semantic_guard import field_role_supported
from archipelago.scholarly.extraction.slm_paper_fields import (
    anchor_model_quotes,
    verify_candidates,
)


def test_competition_context_is_not_a_contribution() -> None:
    text = "This paper is a part of the competition named BUET CSE Fest DL Sprint."
    assert not any(
        item["field"] == "contributions" for item in extract_fallback_abstract_fields(text)
    )
    assert not field_role_supported("methodology", "contributions", text, text)


def test_purpose_is_a_problem_and_presented_method_is_a_contribution() -> None:
    text = (
        "The purpose of this paper is to improve Bengali speech recognition. "
        "We present a transfer learning approach for Bengali speech recognition."
    )
    fields = extract_fallback_abstract_fields(text)
    assert any(
        item["field"] == "research_problem"
        and item["value"] == "improve Bengali speech recognition"
        for item in fields
    )
    assert any(
        item["field"] == "contributions" and "transfer learning approach" in item["value"]
        for item in fields
    )


def test_pdf_slm_ellipsis_recovers_only_a_literal_dataset_quote() -> None:
    span = {
        "pdf_page": 1,
        "section": "abstract",
        "text": "Audio recordings were used to create a Bengali speech digits dataset.",
    }
    candidates = [
        {
            "group": "datasets",
            "field": "dataset_names",
            "value": "Bengali speech digits dataset",
            "evidence_text": "...create a Bengali speech digits dataset...",
            "pdf_page": 1,
            "section": "abstract",
        },
        {
            "group": "datasets",
            "field": "sample_size",
            "value": "Bengali speech digits dataset",
            "evidence_text": "...dataset...",
            "pdf_page": 1,
            "section": "abstract",
        },
    ]
    verified = verify_candidates(anchor_model_quotes(candidates, span), [span])
    assert [(item["field"], item["value"]) for item in verified] == [
        ("dataset_names", "Bengali speech digits dataset")
    ]


def test_generic_dataset_descriptions_do_not_become_names() -> None:
    quote = (
        "Using the publicly available Large Bengali ASR Training data set, we benchmark results."
    )
    assert not field_role_supported("experiments", "datasets", "we benchmark", quote)
    assert not field_role_supported("experiments", "datasets", "training dataset", quote)
    assert not field_role_supported(
        "experiments", "datasets", "dermoscopic", "A dataset of dermoscopic images was used."
    )
    assert not field_role_supported(
        "experiments", "datasets", "Albanian", "We present a dataset of news in Albanian."
    )
    assert not field_role_supported(
        "experiments", "datasets", "Many dataset", "We reviewed many dataset sources."
    )
    assert field_role_supported(
        "experiments", "datasets", "KITTI benchmark", "We evaluated on the KITTI benchmark."
    )


def test_technique_requires_a_named_method_not_background_prose() -> None:
    assert not field_role_supported(
        "methodology",
        "techniques",
        "an overview of recent advances",
        "We present an overview of recent advances.",
    )
    assert not field_role_supported(
        "methodology",
        "techniques",
        "some important aspects regarding the use of these models",
        "We discuss some important aspects regarding the use of these models.",
    )
    assert not field_role_supported(
        "methodology", "techniques", "a complete framework", "We present a complete framework."
    )
    assert not field_role_supported(
        "methodology",
        "techniques",
        "various deep learning models",
        "We examine various deep learning models.",
    )
    assert not field_role_supported(
        "methodology",
        "techniques",
        "the diagnostic AI techniques and their evaluation metrics",
        "We review the diagnostic AI techniques and their evaluation metrics.",
    )
    assert field_role_supported(
        "methodology",
        "techniques",
        "a discovery radiomics framework",
        "We propose a discovery radiomics framework.",
    )
    assert field_role_supported(
        "methodology",
        "techniques",
        "a refined per-frame evaluation methodology",
        "We introduce a refined per-frame evaluation methodology.",
    )
    assert field_role_supported(
        "methodology", "techniques", "GraphSAGE", "We propose GraphSAGE for node embeddings."
    )


def test_claim_must_state_a_research_finding() -> None:
    assert not field_role_supported(
        "claims",
        "claim_text",
        "Social media for news consumption is a double-edged sword.",
        "Social media for news consumption is a double-edged sword.",
    )
    assert field_role_supported(
        "claims",
        "claim_text",
        "Our results show higher accuracy",
        "Our results show higher accuracy",
    )

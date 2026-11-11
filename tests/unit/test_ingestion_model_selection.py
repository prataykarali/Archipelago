"""Academic and research extraction keep separate configurable model tags."""

from __future__ import annotations

import pytest

from archipelago.ingestion.lib_qwen_extractor import LibQwenConceptExtractor
from archipelago.scholarly.extraction.abstract_fields import ingestion_model_name as abstract_model
from archipelago.scholarly.extraction.slm_paper_fields import ingestion_model_name as paper_model

pytestmark = pytest.mark.unit


def test_academic_and_research_models_can_be_selected_independently(monkeypatch) -> None:
    monkeypatch.setenv("ARCHIPELAGO_INGESTION_MODEL", "legacy-shared:test")
    monkeypatch.setenv("ARCHIPELAGO_ACADEMIC_MODEL", "lib-qwen:test")
    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_MODEL", "qwen3.5:test")

    assert LibQwenConceptExtractor().model_name == "lib-qwen:test"
    assert abstract_model() == "qwen3.5:test"
    assert paper_model() == "qwen3.5:test"

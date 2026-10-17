"""Vector projection readiness safeguards."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from archipelago.scholarly.pipeline.vector_projection import build_vector_projection

pytestmark = pytest.mark.unit


def test_vector_projection_only_claims_ready_after_real_encode(tmp_path, monkeypatch) -> None:
    import numpy as np

    inputs = tmp_path / "papers.vector-inputs.jsonl"
    inputs.write_text(json.dumps({"paper_id": "p1", "text": "Optical recognition"}) + "\n")
    monkeypatch.delenv("ARCHIPELAGO_RESEARCH_EMBEDDING_MODEL", raising=False)
    assert build_vector_projection(inputs)["state"] == "not_configured"

    class Encoder:
        def __init__(self, *_args, **_kwargs):
            pass

        def encode(self, texts, **_kwargs):
            assert texts == ["Optical recognition"]
            return np.array([[0.6, 0.8]], dtype=np.float32)

    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_EMBEDDING_MODEL", "local-model")
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder)
    )
    result = build_vector_projection(inputs)
    assert result["state"] == "ready" and result["dimensions"] == 2
    with np.load(result["path"], allow_pickle=False) as vectors:
        assert vectors["paper_ids"].tolist() == ["p1"]

"""Regression tests for first-response latency fast paths."""
from __future__ import annotations

import torch

from archipelago.inference import embeddings, intent_gate, synthesis


def test_intent_prototypes_are_embedded_in_one_batch(monkeypatch):
    calls: list[list[str]] = []
    total = sum(len(texts) for texts in intent_gate._PROTOTYPES.values())

    monkeypatch.setattr(intent_gate.st, "use_embeddings", True)
    monkeypatch.setattr(intent_gate.st, "embed_model", object())
    monkeypatch.setattr(intent_gate, "_PROTO_EMB", None)

    def fake_batch(texts: list[str]) -> torch.Tensor:
        calls.append(texts)
        return torch.ones((len(texts), 4), dtype=torch.float32)

    monkeypatch.setattr(
        "archipelago.inference.embeddings.get_snowflake_embedding",
        fake_batch,
    )

    result = intent_gate._ensure_proto_embeddings()

    assert result is not None
    assert len(calls) == 1
    assert len(calls[0]) == total


def test_embedder_stays_unavailable_until_concept_precompute_finishes(monkeypatch):
    observed_use_embeddings: list[bool] = []

    class _Model:
        def to(self, _device):
            return self

        def eval(self):
            return None

    monkeypatch.setattr(
        embeddings.AutoTokenizer,
        "from_pretrained",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        embeddings.AutoModel,
        "from_pretrained",
        lambda *_args, **_kwargs: _Model(),
    )
    monkeypatch.setattr(embeddings, "_embed_device_preference", lambda: "cpu")

    def fake_precompute(*, force: bool = False) -> None:
        assert force
        observed_use_embeddings.append(embeddings.st.use_embeddings)

    monkeypatch.setattr(embeddings, "build_concept_embeddings", fake_precompute)
    monkeypatch.setattr(embeddings.st, "use_embeddings", True)

    embeddings.load_embedding_model()

    assert observed_use_embeddings == [False]

"""Candidate graph corrections preserve suspect edges for human review."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HOST_DIR = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from engine.graph import LibraryGraph  # noqa: E402
from engine.graph_semantics import TRANSFORMER_CONFLATION  # noqa: E402


@pytest.mark.unit
def test_candidate_corrects_transformer_without_changing_source(tmp_path: Path) -> None:
    """The exported graph remains intact while the candidate uses a precise summary."""
    path = tmp_path / "graph.json"
    raw = {
        "nodes": [{"id": "transformer", "label": "Transformer", "summary": TRANSFORMER_CONFLATION}]
    }
    path.write_text(json.dumps(raw), encoding="utf-8")

    graph = LibraryGraph(path)

    assert "BERT's masked-language-model" in graph.nodes["transformer"]["summary"]
    assert (
        json.loads(path.read_text(encoding="utf-8"))["nodes"][0]["summary"]
        == TRANSFORMER_CONFLATION
    )


@pytest.mark.unit
def test_ambiguous_rag_edges_are_quarantined_with_provenance(tmp_path: Path) -> None:
    """Suspect directions cannot appear in learning paths or related concepts."""
    path = tmp_path / "graph.json"
    raw = {
        "nodes": [
            {"id": value, "label": value}
            for value in (
                "rag",
                "retrieval_augmented_generation",
                "gpt_2",
                "triviaqa",
                "vector_rag",
            )
        ],
        "edges": [
            {
                "from_id": "retrieval_augmented_generation",
                "to_id": "gpt_2",
                "edge_type": "UNLOCKS",
                "source": "Lewis:chunk_037",
            },
            {
                "from_id": "triviaqa",
                "to_id": "rag",
                "edge_type": "UNLOCKS",
                "source": "Lewis:chunk_019",
            },
            {
                "from_id": "retrieval_augmented_generation",
                "to_id": "gpt_2",
                "edge_type": "RELATED",
                "relation": "uses",
            },
            {
                "from_id": "vector_rag",
                "to_id": "retrieval_augmented_generation",
                "edge_type": "REQUIRES",
            },
        ],
    }
    path.write_text(json.dumps(raw), encoding="utf-8")

    graph = LibraryGraph(path)

    assert "gpt_2" not in graph.unlocks("retrieval_augmented_generation")
    assert "triviaqa" not in graph.prereqs("rag")
    assert "gpt_2" not in graph.related("retrieval_augmented_generation")
    assert "retrieval_augmented_generation" in graph.prereqs("vector_rag")
    assert len(graph.quarantined_edges) == 3
    assert graph.quarantined_edges[0]["source"] == "Lewis:chunk_037"
    assert all(edge["quarantine_reason"] for edge in graph.quarantined_edges)

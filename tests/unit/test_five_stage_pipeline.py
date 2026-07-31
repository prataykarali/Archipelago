"""Unit tests for the 5-stage local-retrieve → Gemini synthesis pipeline."""
from __future__ import annotations

from archipelago.inference import pipeline as pl


def test_stage1_rejects_overlong_query() -> None:
    long_q = "x" * 501
    result = pl._stage1_guardrails(long_q)
    assert result is not None
    assert result.get("reject") is True


def test_stage1_strips_polite_noise() -> None:
    result = pl._stage1_guardrails("Hey, can you explain LoRA?")
    assert result is not None
    assert result.get("reject") is False
    normalized = str(result.get("normalized_query") or "")
    assert "hey" not in normalized.lower()
    assert "lora" in normalized.lower()


def test_stage2_prefers_lora_over_machine_learning(monkeypatch) -> None:
    monkeypatch.setattr(
        pl.st,
        "CONCEPTS_DATA",
        {
            "low_rank_adaptation": {
                "id": "low_rank_adaptation",
                "label": "Low-Rank Adaptation",
                "name": "Low-Rank Adaptation",
                "summary": "PEFT method using low-rank adapters (LoRA).",
                "aliases": ["lora", "low-rank adaptation"],
            },
            "machine_learning": {
                "id": "machine_learning",
                "label": "Machine Learning",
                "name": "Machine Learning",
                "summary": "Broad ML field.",
                "aliases": ["ml"],
            },
        },
    )

    def fake_rank(query: str, top_k: int | None = None):
        return [
            {
                "id": "machine_learning",
                "label": "Machine Learning",
                "cos": 1.0,
                "lexical": 1.0,
                "alias_boost": 0.12,
                "core_boost": 0.0,
                "blended": 1.2,
            },
            {
                "id": "low_rank_adaptation",
                "label": "Low-Rank Adaptation",
                "cos": 0.3,
                "lexical": 0.85,
                "alias_boost": 0.55,
                "core_boost": 0.5,
                "blended": 1.5,
            },
        ][: top_k or 25]

    monkeypatch.setattr(
        "archipelago.inference.ranking.rank_concepts",
        fake_rank,
    )
    hit = pl._stage2_vector_search("What is LoRA in machine learning?")
    assert hit is not None
    assert hit["anchor_id"] == "low_rank_adaptation"


def test_stage2_kill_switch_rejects_weak_hits(monkeypatch) -> None:
    monkeypatch.setattr(pl.st, "CONCEPTS_DATA", {"c1": {"id": "c1", "label": "C1"}})

    def fake_rank(query: str, top_k: int | None = None):
        return [
            {
                "id": "c1",
                "label": "C1",
                "cos": 0.2,
                "lexical": 0.2,
                "alias_boost": 0.0,
                "core_boost": 0.0,
                "blended": 0.3,
            }
        ]

    monkeypatch.setattr("archipelago.inference.ranking.rank_concepts", fake_rank)
    assert pl._stage2_vector_search("chocolate cake frosting") is None


def test_run_pipeline_kill_switch_message(monkeypatch) -> None:
    monkeypatch.setattr(pl, "_stage1_guardrails", lambda q: {"reject": False, "normalized_query": q})
    monkeypatch.setattr(pl, "_stage2_vector_search", lambda q: None)
    result = pl.run_archipelago_inference("unrelated trivia about sports")
    assert result["routing"]["route"] == "kill_switch"
    assert "outside the current scope" in result["text"].lower()
    assert "database systems" in result["text"].lower() or "rag" in result["text"].lower()


def test_run_pipeline_passes_ollama_output_after_retrieval(monkeypatch) -> None:
    """Ollama output is used directly after successful graph retrieval."""
    monkeypatch.setattr(
        pl,
        "_stage1_guardrails",
        lambda q: {"reject": False, "normalized_query": q},
    )
    monkeypatch.setattr(
        pl,
        "_stage2_vector_search",
        lambda q: {
            "anchor_id": "vector_rag",
            "concept_name": "Vector RAG",
            "cosine_sim": 0.61,
        },
    )
    monkeypatch.setattr(
        pl,
        "_stage3_graph_traversal",
        lambda anchor: {
            "anchor_id": anchor,
            "prerequisites": [{"id": "retrieval", "name": "Retrieval", "summary": ""}],
            "unlocks": [{"id": "graph_rag", "name": "GraphRAG", "summary": ""}],
            "multi_hop_paths": [],
            "chunks": [
                {
                    "doc_id": "papers/Edge2024_GraphRAG.pdf",
                    "title": "GraphRAG",
                    "chunk_id": "chunk_006",
                    "page_number": 2,
                    "section_title": "",
                    "text_passage": (
                        "Vector RAG retrieves documents with a dense index and "
                        "augments the LLM context for generation."
                    ),
                }
            ],
        },
    )
    monkeypatch.setattr(
        pl,
        "_stage5_ollama_synthesis",
        lambda payload: "Vector RAG uses dense retrieval to find relevant documents [S1].",
    )
    monkeypatch.setattr(
        pl.st,
        "CONCEPTS_DATA",
        {
            "vector_rag": {
                "id": "vector_rag",
                "name": "Vector RAG",
                "label": "Vector RAG",
                "summary": (
                    "A retrieval-augmented generation approach using a vector "
                    "retriever over an index to find documents for generation."
                ),
            }
        },
    )
    result = pl.run_archipelago_inference(
        "How are Vector Indices integrated with Database Management Systems in RAG?"
    )
    text = (result.get("text") or "").lower()
    assert "vector rag" in text or "retrieval" in text
    assert result["generation"]["provider"] == "ollama"


def test_run_pipeline_calls_gemini_after_local_stages(monkeypatch) -> None:
    monkeypatch.setattr(
        pl,
        "_stage1_guardrails",
        lambda q: {"reject": False, "normalized_query": q},
    )
    monkeypatch.setattr(
        pl,
        "_stage2_vector_search",
        lambda q: {
            "anchor_id": "low_rank_adaptation",
            "concept_name": "Low-Rank Adaptation",
            "cosine_sim": 0.9,
        },
    )
    monkeypatch.setattr(
        pl,
        "_stage3_graph_traversal",
        lambda anchor: {
            "anchor_id": anchor,
            "prerequisites": [{"id": "p1", "name": "Matrix Decomposition", "summary": ""}],
            "unlocks": [{"id": "u1", "name": "QLoRA", "summary": ""}],
            "multi_hop_paths": [],
            "chunks": [
                {
                    "doc_id": "doc1",
                    "title": "PEFT Paper",
                    "chunk_id": "c1",
                    "page_number": 3,
                    "section_title": "LoRA",
                    "text_passage": "LoRA freezes base weights and trains low-rank adapters.",
                }
            ],
        },
    )
    monkeypatch.setattr(
        pl,
        "_stage5_ollama_synthesis",
        lambda payload: "LoRA is PEFT via low-rank adapters [S1].",
    )
    monkeypatch.setattr(
        pl.st,
        "CONCEPTS_DATA",
        {
            "low_rank_adaptation": {
                "id": "low_rank_adaptation",
                "name": "Low-Rank Adaptation",
                "label": "Low-Rank Adaptation",
            }
        },
    )

    result = pl.run_archipelago_inference("What is LoRA?")
    assert result["routing"]["reason"] == "5_stage_pipeline"
    assert result["anchor_concept"]["id"] == "low_rank_adaptation"
    assert result["citations"][0]["evidence_id"] == "S1"
    assert "[S1]" in result["text"]
    assert result["generation"]["provider"] == "ollama"
    assert result["generation"]["source"] == "ollama"

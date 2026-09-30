"""Unit tests for PromptPayloadAssembler and context boundary isolation."""
from __future__ import annotations

import pytest
from src.core.prompt_assembly import (
    MAX_CHUNKS,
    MAX_GRAPH_NODES,
    PromptPayloadAssembler,
)


@pytest.fixture
def assembler():
    return PromptPayloadAssembler()


def test_context_budget_chunks_capped(assembler):
    # Pass 10 chunks — must strictly bound to MAX_CHUNKS = 3
    large_chunks = [
        {"doc_id": f"doc_{i}.pdf", "page_number": i, "text_passage": f"Passage {i}"}
        for i in range(10)
    ]
    passages_text, lineage = assembler.format_evidence_passages(large_chunks)
    assert len(lineage) == MAX_CHUNKS
    assert "[S1]" in passages_text
    assert "[S2]" in passages_text
    assert "[S3]" in passages_text
    assert "[S4]" not in passages_text


def test_topological_map_budget_capped(assembler):
    # Pass 10 prereqs and 10 unlocks — must bound node count
    large_prereqs = [{"name": f"Prereq_{i}"} for i in range(10)]
    large_unlocks = [{"name": f"Unlock_{i}"} for i in range(10)]

    topo = assembler.format_topological_map(
        anchor_name="Target Concept",
        difficulty="advanced",
        prerequisites=large_prereqs,
        unlocks=large_unlocks,
    )
    assert "TARGET CONCEPT: Target Concept (ADVANCED)" in topo
    assert "Prereq_0" in topo
    assert "Prereq_1" in topo
    assert "Prereq_2" in topo
    # Prereqs capped at 3
    assert "Prereq_3" not in topo
    # Unlocks capped at 2
    assert "Unlock_0" in topo
    assert "Unlock_1" in topo
    assert "Unlock_2" not in topo


def test_full_payload_assembly(assembler):
    chunks = [
        {"doc_id": "Hu2021_LoRA.pdf", "page_number": 2, "section_title": "Method", "text_passage": "LoRA decomposes weights into low-rank matrices."},
    ]
    prereqs = [{"name": "Linear Algebra"}]
    unlocks = [{"name": "QLoRA"}]

    payload = assembler.assemble_payload(
        query="Explain LoRA weight decomposition",
        anchor_name="Low-Rank Adaptation",
        difficulty="intermediate",
        prerequisites=prereqs,
        unlocks=unlocks,
        chunks=chunks,
    )

    assert "system_prompt" in payload
    assert "user_prompt" in payload
    assert "citation_lineage" in payload
    assert len(payload["citation_lineage"]) == 1
    assert payload["citation_lineage"][0]["badge"] == "S1"
    assert payload["citation_lineage"][0]["page_number"] == 2
    assert "Base your answer STRICTLY on the evidence above" in payload["system_prompt"]
    assert "Every factual assertion MUST end with an inline source badge" in payload["system_prompt"]

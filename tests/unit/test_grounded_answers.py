"""Field-aware grounded layouts — not one AI template for every domain."""

from archipelago.inference.grounded_answers import (
    detect_answer_field,
    render_grounded_answer,
    select_layout_index,
)
from archipelago.inference.synthesis import format_natural_fallback


def _concept(cid, name, summary, ctype="definition", doc="papers/Lewis2020_RAG.pdf"):
    return {
        "id": cid,
        "label": name,
        "name": name,
        "summary": summary,
        "concept_type": ctype,
        "sources": [{"doc_id": doc}],
    }


def _cmap(cid, doc, page=1, topic="T"):
    return {
        cid: [{
            "evidence_id": "S1",
            "doc_id": doc,
            "page_number": page,
            "section_title": topic,
            "text": "evidence",
        }],
    }


def test_hundred_layouts_are_selectable():
    idxs = {select_layout_index(f"query number {i}", "aiml_paper") for i in range(500)}
    assert len(idxs) >= 40  # good spread across 100
    assert all(0 <= i < 100 for i in idxs)
    # Stable per query (not random each call)
    assert select_layout_index("What is LoRA?", "aiml_paper") == select_layout_index(
        "What is LoRA?", "aiml_paper"
    )
    # Different questions usually get different layouts
    a = select_layout_index("What is LoRA?", "aiml_paper")
    b = select_layout_index("What is self-attention?", "aiml_paper")
    c = select_layout_index("Explain B+ trees", "dbms")
    assert len({a, b, c}) >= 2


def test_curriculum_questions_keep_full_layout_catalog_and_study_depth():
    c = _concept(
        "lora",
        "Low-Rank Adaptation",
        "LoRA freezes pre-trained weights and learns low-rank update matrices.",
    )
    prereqs = [
        _concept("linear_algebra", "Linear Algebra", "Covers vectors and matrix products."),
        _concept("matrix_rank", "Matrix Rank", "Measures independent matrix directions."),
        _concept("fine_tuning", "Fine-Tuning", "Adapts model weights to a downstream task."),
    ]
    cmap = {
        **_cmap("lora", "papers/Hu2021_LoRA.pdf", 3, "LoRA"),
        **_cmap("linear_algebra", "textbooks/Math.pdf", 2, "Linear Algebra"),
        **_cmap("matrix_rank", "textbooks/Math.pdf", 7, "Matrix Rank"),
        **_cmap("fine_tuning", "papers/Hu2021_LoRA.pdf", 5, "Fine-Tuning"),
    }
    curriculum_paths = [{
        "hops": 2,
        "markdown": "Linear Algebra (p.2) → Fine-Tuning (p.5) → LoRA (p.3)",
    }]

    indices = {
        select_layout_index(f"Trace curriculum path for LoRA variant {i}", "aiml_paper")
        for i in range(500)
    }
    out = render_grounded_answer(
        "Trace the mathematical curriculum path for LoRA",
        c,
        prereqs=prereqs,
        citation_map=cmap,
        curriculum_paths=curriculum_paths,
    )

    assert len(indices) >= 40
    assert "LoRA freezes pre-trained weights" in out
    assert "**Build the foundation**" in out
    assert out.count("—") >= 2
    assert "Multi-hop curriculum path" in out


def test_field_detection_varies_by_domain():
    rag = _concept("rag", "RAG", "Retrieval-augmented generation.")
    assert detect_answer_field("What is RAG?", rag, _cmap("rag", "papers/Lewis2020_RAG.pdf")) in (
        "aiml_paper", "aiml_theory", "method", "general",
    )
    sql = _concept("sql", "SQL", "Structured query language.", doc="papers/foo.pdf")
    assert detect_answer_field("best books on DBMS", sql, {}) == "dbms"
    assert detect_answer_field("operating systems memory", sql, {}) == "operating_systems"


def test_different_queries_get_different_layouts_or_fields():
    c = _concept("rag", "RAG", "Retrieval-augmented generation combines retrieval and generation.")
    cm = _cmap("rag", "papers/Lewis2020_RAG.pdf", 4, "RAG")
    a = render_grounded_answer("What is RAG?", c, citation_map=cm)
    b = render_grounded_answer("Explain attention mechanism theory", c, citation_map=cm)
    # Not the old universal template
    assert "is the best match in this library for what you asked" not in a
    assert "attention, LoRA, RAG, BERT, agents" not in a
    # Source link present
    assert "/api/page-view" in a or "S1" in a
    # Variety: different query → often different text shape
    assert a != b or select_layout_index("What is RAG?", "aiml_paper") != select_layout_index(
        "Explain attention mechanism theory", "aiml_paper"
    )


def test_security_sql_node_does_not_sound_like_tutorial():
    c = _concept(
        "sql",
        "SQL",
        "A structured query language for querying relational databases.",
        doc="papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
    )
    cm = _cmap(
        "sql",
        "papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
        9,
        "SQL",
    )
    out = format_natural_fallback(
        "what is SQL in this corpus",
        c,
        prereqs=[],
        unlocks=[],
        related=[{"id": "sql_injection", "label": "SQL Injection"}],
        citation_map=cm,
    )
    assert "/api/page-view" in out
    assert "%20" in out or "doc_id=" in out
    assert "CREATE TABLE" not in out.upper()
    assert "is the best match in this library for what you asked" not in out


def test_format_natural_fallback_uses_grounded_renderer():
    c = _concept("lora", "LoRA", "Low-rank adaptation of large language models.")
    cm = _cmap("lora", "papers/Hu2021_LoRA.pdf", 3, "LoRA")
    out = format_natural_fallback("What is LoRA?", c, [], [], [], cm)
    assert "LoRA" in out or "Low-Rank" in out or "low-rank" in out.lower()
    assert "attention, LoRA, RAG, BERT, agents" not in out


def test_summary_does_not_cut_mid_word():
    """Hard slice used to end on 'wit'; sentence/word boundary must win."""
    from archipelago.inference.grounded_answers import _summary
    text = (
        "A method that retrieves relevant documents from an external knowledge source "
        "and uses them to augment an LLM, enabling answer generation without relying "
        "solely on parametric memory."
    )
    node = {"summary": text}
    short = _summary(node, 140)
    assert not short.endswith("wit")
    assert not short.endswith("generatio")
    # Either ellipsis on a word break or a full sentence.
    assert short.endswith(("…", ".", "!", "?")) or " " in short[-12:]
    full = _summary(node, 280)
    assert "answer generation" in full

"""Unit tests for ContextSerializer sanitization firewall and chunk serialization.

Verifies that internal DB metadata, internal routing endpoints, and leak-prone
tokens are 100% stripped before reaching model prompts.
"""

from archipelago.core.chunk import RetrievedChunk, ContextSerializer


def test_sanitize_text_strips_internal_endpoints():
    """Verify internal routing paths (/api/..., /internal/..., /admin/...) are stripped."""
    raw = (
        "The system accesses /api/v1/internal_nodes and /internal/debug_dump "
        "along with /admin/secret_endpoint to fetch weights."
    )
    clean = ContextSerializer.sanitize_text(raw)
    assert "/api/" not in clean
    assert "/internal/" not in clean
    assert "/admin/" not in clean
    assert "to fetch weights." in clean


def test_sanitize_text_strips_database_identifiers():
    """Verify database identifier keys (doc_id: ..., chunk_id: ...) are stripped."""
    raw = (
        "Relevant passage doc_id: papers/vaswani2017.pdf chunk_id: chunk_004 "
        "describes scaled dot-product attention."
    )
    clean = ContextSerializer.sanitize_text(raw)
    assert "doc_id:" not in clean
    assert "chunk_id:" not in clean
    assert "scaled dot-product attention" in clean


def test_sanitize_text_strips_ui_link_artifacts():
    """Verify page link artifacts like 'p.14 ↗' are removed."""
    raw = "Refer to the algorithm on p.14 ↗ for exact hyperparameter bounds."
    clean = ContextSerializer.sanitize_text(raw)
    assert "↗" not in clean
    assert "p.14" not in clean
    assert "for exact hyperparameter bounds." in clean


def test_serialize_single_chunk():
    """Verify clean rendering of a single RetrievedChunk into model context."""
    chunk = RetrievedChunk(
        source_id="SRC-001",
        document_title="Attention Is All You Need",
        page_number=4,
        text="The attention mechanism can be described as mapping a query and a set of key-value pairs.",
    )
    rendered = ContextSerializer.serialize_chunk(chunk)
    assert "[SRC-001]" in rendered
    assert "Document: Attention Is All You Need" in rendered
    assert "Page: 4" in rendered
    assert "mapping a query and a set of key-value pairs" in rendered


def test_serialize_chunk_with_leakage_in_text():
    """Verify serialization cleans contaminated chunk content automatically."""
    chunk = RetrievedChunk(
        source_id="SRC-002",
        document_title="LoRA Paper /admin/info",
        page_number=2,
        text="doc_id: lora.pdf chunk_id: chk_999 /api/leak We hypothesize that updates have low rank.",
    )
    rendered = ContextSerializer.serialize_chunk(chunk)
    assert "/admin/" not in rendered
    assert "doc_id:" not in rendered
    assert "chunk_id:" not in rendered
    assert "/api/leak" not in rendered
    assert "We hypothesize that updates have low rank." in rendered


def test_serialize_context_empty_and_multiple():
    """Verify multi-chunk context joining and empty handling."""
    assert ContextSerializer.serialize_context([]) == ""

    chunks = [
        RetrievedChunk(source_id="SRC-A", document_title="Doc A", page_number=1, text="Text A"),
        RetrievedChunk(source_id="SRC-B", document_title="Doc B", page_number=2, text="Text B"),
    ]
    combined = ContextSerializer.serialize_context(chunks)
    assert "---" in combined
    assert "[SRC-A]" in combined
    assert "[SRC-B]" in combined

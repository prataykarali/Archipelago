"""Unit tests for RequestContext thread safety and request isolation.

Verifies that concurrent requests executed across multiple threads maintain
strict isolation and prevent context leakage between users.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from archipelago.core.context import RequestContext
from archipelago.core.chunk import RetrievedChunk


def test_request_context_defaults():
    """Verify default initialization of RequestContext fields."""
    ctx = RequestContext(query="What is self-attention?")
    assert ctx.query == "What is self-attention?"
    assert ctx.user_id == "anonymous"
    assert ctx.request_id.startswith("req_")
    assert ctx.timestamp is not None
    assert ctx.retrieved_sources == []
    assert ctx.graph_nodes == []
    assert ctx.model_output is None
    assert ctx.verification_result == {}
    assert ctx.metadata == {}


def test_request_context_unique_ids():
    """Verify distinct instances receive globally unique request IDs."""
    contexts = [RequestContext(query=f"Query {i}") for i in range(100)]
    ids = {ctx.request_id for ctx in contexts}
    assert len(ids) == 100


def test_request_context_to_dict():
    """Verify dictionary serialization preserves isolation fields without leakage."""
    ctx = RequestContext(
        query="Explain B-Tree indexing",
        user_id="user_123",
        intent="theory",
    )
    ctx.set_graph_nodes(["node_btree", "node_index"])
    ctx.verification_result = {"status": "verified", "score": 0.98}

    d = ctx.to_dict()
    assert d["request_id"] == ctx.request_id
    assert d["user_id"] == "user_123"
    assert d["query"] == "Explain B-Tree indexing"
    assert d["intent"] == "theory"
    assert d["graph_nodes"] == ["node_btree", "node_index"]
    assert d["verification_result"] == {"status": "verified", "score": 0.98}


def test_concurrent_request_isolation():
    """Verify concurrent requests in multiple threads do not cross-contaminate state."""
    num_threads = 16
    results = []

    def worker(worker_id: int):
        user_name = f"user_{worker_id}"
        query_text = f"Query from thread {worker_id}"
        ctx = RequestContext(query=query_text, user_id=user_name)

        # Simulate work and mutation
        for chunk_idx in range(5):
            chunk = RetrievedChunk(
                source_id=f"src_{worker_id}_{chunk_idx}",
                document_title=f"Doc {worker_id}",
                page_number=chunk_idx + 1,
                text=f"Passage content for worker {worker_id}, chunk {chunk_idx}",
            )
            ctx.add_retrieved_source(chunk)
            time.sleep(0.001)

        ctx.set_graph_nodes([f"concept_{worker_id}_a", f"concept_{worker_id}_b"])
        return ctx

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in as_completed(futures):
            results.append(f.result())

    assert len(results) == num_threads

    # Verify each context maintained strict isolation
    for ctx in results:
        w_id = ctx.user_id.split("_")[1]
        assert ctx.query == f"Query from thread {w_id}"
        assert len(ctx.retrieved_sources) == 5
        for chunk in ctx.retrieved_sources:
            assert f"worker {w_id}" in chunk.text
            assert chunk.source_id.startswith(f"src_{w_id}_")
            assert chunk.document_title == f"Doc {w_id}"
        assert ctx.graph_nodes == [f"concept_{w_id}_a", f"concept_{w_id}_b"]

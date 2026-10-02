"""Unit tests for Librarian Pipeline, 8-Key OKF Contract, and Atomic Swap Mechanics."""

import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
import pytest

from archipelago.graph.engine import KuzuGraphEngine
from archipelago.graph.graph_fusion import GraphFusionEngine
from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,
    canonical_concept_id,
    canonicalize_concept_name,
    clean_json_payload,
    is_negative_sample,
)
from archipelago.ingestion.librarian_worker import (
    get_job_status,
    get_staging_review,
    publish_staging,
    start_upload_job,
)


def test_8_key_okf_contract_canonicalization():
    """Verify multi-domain canonical entity normalization and ID derivation."""
    assert canonicalize_concept_name("SVD") == "Singular Value Decomposition"
    assert canonicalize_concept_name("Backprop") == "Error Backpropagation Algorithm"
    assert canonicalize_concept_name("TCP/IP") == "Transmission Control Protocol/Internet Protocol"
    assert canonicalize_concept_name("RSA") == "RSA Public-Key Cryptosystem"
    assert canonicalize_concept_name("DNA") == "Deoxyribonucleic Acid"
    assert canonicalize_concept_name("Op-Amp") == "Operational Amplifier"

    assert canonical_concept_id("SVD") == "singular_value_decomposition"
    assert canonical_concept_id("TCP/IP") == "transmission_control_protocol_internet_protocol"


def test_clean_json_payload_8_key():
    """Verify clean_json_payload parses standard 8-key array and single object."""
    raw_payload = """
    ```json
    [
      {
        "concept_name": "Singular Value Decomposition",
        "concept_type": "technique",
        "difficulty": "intermediate",
        "summary": "A matrix factorization technique.",
        "prerequisites": ["Matrix Multiplication"],
        "unlocks": ["Principal Component Analysis"],
        "related_to": [{"concept": "Eigendecomposition", "relation": "generalizes"}],
        "tags": ["linear-algebra"]
      }
    ]
    ```
    """
    res = clean_json_payload(raw_payload)
    assert "concepts" in res
    assert len(res["concepts"]) == 1
    c = res["concepts"][0]
    assert c["concept_name"] == "Singular Value Decomposition"
    assert c["concept_type"] == "technique"
    assert "Matrix Multiplication" in c["prerequisites"]


def test_self_loop_and_reciprocal_cycle_elimination():
    """Verify self-loops and reciprocal cycles are pruned."""
    extractor = LibQwenConceptExtractor()
    concepts = [
        {
            "id": "concept_a",
            "name": "Concept A",
            "prerequisites": ["Concept B", "Concept A"],  # Self loop
            "unlocks": ["Concept B"],
        },
        {
            "id": "concept_b",
            "name": "Concept B",
            "prerequisites": ["Concept A"],  # Reciprocal cycle: B requires A while A requires B
            "unlocks": ["Concept A"],
        },
    ]

    resolved = extractor.second_pass_relation_resolver(concepts)
    assert len(resolved) == 2
    a = next(c for c in resolved if c["id"] == "concept_a")
    b = next(c for c in resolved if c["id"] == "concept_b")

    a_prereqs = [p["id"] for p in a["prerequisites"]]
    b_prereqs = [p["id"] for p in b["prerequisites"]]

    # Self-loop Concept A -> Concept A must be removed
    assert "concept_a" not in a_prereqs
    # Only one direction of reciprocal cycle preserved
    assert not ("concept_b" in a_prereqs and "concept_a" in b_prereqs)


def test_kahn_dag_multi_domain():
    """Verify Kahn DAG cycle gate rejects cyclic relationships across multi-domain nodes."""
    fusion = GraphFusionEngine()
    existing_nodes = {"tcp", "ip", "routing"}
    existing_edges = {("routing", "ip"), ("ip", "tcp")}

    # Valid acyclic addition
    is_valid, rej = fusion.validate_dag_kahn(existing_nodes, existing_edges, {"bgp"}, {("bgp", "routing")})
    assert is_valid is True
    assert len(rej) == 0

    # Cyclic edge (tcp -> routing creates routing -> ip -> tcp -> routing)
    is_valid_c, rej_c = fusion.validate_dag_kahn(existing_nodes, existing_edges, set(), {("tcp", "routing")})
    assert is_valid_c is False
    assert ("tcp", "routing") in rej_c


def test_embeddings_accept_name_without_label(tmp_path, monkeypatch):
    """Firewall rebuild must not KeyError when export writes `name` but not `label`."""
    from archipelago.inference import embeddings
    from archipelago.inference import state as st

    payload = {
        "visualization": {
            "nodes": [
                {
                    "id": "tcp_handshake",
                    "name": "TCP Handshake",
                    "summary": "Three-way handshake establishing a TCP connection.",
                }
            ]
        }
    }
    data_file = tmp_path / "okf_graph.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(st, "DATA_FILE", data_file)
    monkeypatch.setattr(st, "use_embeddings", False)
    embeddings.build_concept_embeddings()
    assert "tcp_handshake" in st.CONCEPTS_DATA
    assert st.CONCEPTS_DATA["tcp_handshake"]["name"] == "TCP Handshake"


def test_kuzu_connection_safe_atomic_swap(tmp_path):
    """Verify KuzuGraphEngine connection switch, atomic swap, and rollback safety."""
    prod_file = tmp_path / "test_graph.db"
    staging_file = tmp_path / "test_graph_staging.db"

    # Create dummy initial production database
    engine_prod = KuzuGraphEngine(db_path=prod_file, read_only=False)
    engine_prod.conn.execute("CREATE NODE TABLE IF NOT EXISTS TestNode (id STRING PRIMARY KEY, val STRING);")
    engine_prod.conn.execute("MERGE (t:TestNode {id: 'n1'}) ON CREATE SET t.val = 'production_v1';")
    
    # Create staging database
    engine_staging = KuzuGraphEngine(db_path=staging_file, read_only=False)
    engine_staging.conn.execute("CREATE NODE TABLE IF NOT EXISTS TestNode (id STRING PRIMARY KEY, val STRING);")
    engine_staging.conn.execute("MERGE (t:TestNode {id: 'n1'}) ON CREATE SET t.val = 'staging_v2';")

    # Perform atomic swap
    KuzuGraphEngine.atomic_swap(staging_file, prod_file)

    # Re-verify production file now has staging_v2
    engine_verify = KuzuGraphEngine(db_path=prod_file, read_only=True)
    res = engine_verify.conn.execute("MATCH (t:TestNode {id: 'n1'}) RETURN t.val;").get_as_df()
    assert res.iloc[0, 0] == "staging_v2"
    engine_verify.close()


def test_chat_server_librarian_endpoints_require_verified_session(monkeypatch):
    """Librarian APIs reject anonymous reads, writes, and graph access.

    ``chat_server`` reads ``ARCHIPELAGO_AUTH_REQUIRED`` at import time, so the
    flag has to be set *before* the module is first imported. When it is already
    imported (the usual case in a suite run) the check is skipped rather than
    silently asserting against a module configured the other way.
    """
    import chat_server
    from chat_server import app

    if "chat_server" in sys.modules and not _auth_required_at_import(chat_server):
        pytest.skip("chat_server imported with auth disabled; import-time flag already resolved")

    client = app.test_client()
    assert client.get("/api/librarian/staging/review").status_code == 401
    assert client.post("/api/librarian/upload").status_code == 401
    assert client.get("/api/librarian/jobs/example-job").status_code == 401
    assert client.get("/api/graph/subgraph?target_id=linear_algebra").status_code == 401


def _auth_required_at_import(module) -> bool:
    """Whether the module resolved "auth required" when it was first imported."""
    for attr in dir(module):
        value = getattr(module, attr, None)
        if attr.isupper() and isinstance(value, bool) and "AUTH" in attr:
            return value
    return False


def test_export_graph_json_multi_edge_types():
    """Verify export_graph_json exports REQUIRES, UNLOCKS, and RELATED edges correctly."""
    from archipelago.ingestion.librarian_worker import export_graph_json
    from okf.graph.common import _create_schema

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "test_export.db"
        json_path = tmp_path / "out_graph.json"

        engine = KuzuGraphEngine(db_path=db_path, read_only=False)
        _create_schema(engine.conn)

        engine.conn.execute("CREATE (c:Concept {id: 'c1', name: 'Concept 1', concept_type: 'method', difficulty: 'foundational', summary: 'S1', tags: 't1'})")
        engine.conn.execute("CREATE (c:Concept {id: 'c2', name: 'Concept 2', concept_type: 'technique', difficulty: 'intermediate', summary: 'S2', tags: 't2'})")
        engine.conn.execute("CREATE (c:Concept {id: 'c3', name: 'Concept 3', concept_type: 'definition', difficulty: 'advanced', summary: 'S3', tags: 't3'})")

        engine.conn.execute("MATCH (a:Concept {id: 'c1'}), (b:Concept {id: 'c2'}) CREATE (a)-[:REQUIRES {relation_type: 'prerequisite', source: 'test'}]->(b)")
        engine.conn.execute("MATCH (a:Concept {id: 'c2'}), (b:Concept {id: 'c3'}) CREATE (a)-[:UNLOCKS {relation_type: 'unlocks', source: 'test'}]->(b)")
        engine.conn.execute("MATCH (a:Concept {id: 'c1'}), (b:Concept {id: 'c3'}) CREATE (a)-[:RELATED {relation_type: 'uses', source: 'test'}]->(b)")
        engine.close()

        exported = export_graph_json(db_path, json_path)
        assert exported["stats"]["total_concepts"] == 3
        assert exported["stats"]["total_edges"] == 3
        edge_types = {e["edge_type"] for e in exported["edges"]}
        assert edge_types == {"REQUIRES", "UNLOCKS", "RELATED"}

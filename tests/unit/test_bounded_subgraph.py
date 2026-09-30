"""Unit tests for Bounded Subgraph Generator (5 to 10 nodes bound)."""

import pytest

from archipelago.inference.subgraph import (
    BoundedSubgraph,
    generate_bounded_subgraph,
)


@pytest.fixture
def mock_concepts_data():
    return {
        "transformer": {
            "id": "transformer",
            "name": "Transformer",
            "label": "Transformer",
            "difficulty": "intermediate",
            "domain": "deep_learning",
            "summary": "Attention-based sequence model.",
            "prerequisites": ["Attention Mechanism", "Neural Network"],
            "unlocks": ["BERT", "GPT", "Low-Rank Adaptation"],
            "related": [{"concept": "BERT", "relation": "variant_of"}],
        },
        "attention_mechanism": {
            "id": "attention_mechanism",
            "name": "Attention Mechanism",
            "label": "Attention Mechanism",
            "difficulty": "intermediate",
            "domain": "deep_learning",
            "summary": "Soft alignment mechanism.",
            "prerequisites": ["Linear Algebra", "Softmax"],
            "unlocks": ["Transformer"],
            "related": [],
        },
        "neural_network": {
            "id": "neural_network",
            "name": "Neural Network",
            "label": "Neural Network",
            "difficulty": "foundational",
            "domain": "deep_learning",
            "summary": "Composition of parameterized affine transformations and non-linearities.",
            "prerequisites": ["Linear Algebra", "Gradient Descent", "Loss Function"],
            "unlocks": ["Transformer", "CNN"],
            "related": [],
        },
        "linear_algebra": {
            "id": "linear_algebra",
            "name": "Linear Algebra",
            "label": "Linear Algebra",
            "difficulty": "foundational",
            "domain": "mathematics",
            "summary": "Study of vector spaces and linear mappings.",
            "prerequisites": [],
            "unlocks": ["Neural Network", "Attention Mechanism"],
            "related": [],
        },
        "softmax": {
            "id": "softmax",
            "name": "Softmax",
            "label": "Softmax",
            "difficulty": "foundational",
            "domain": "mathematics",
            "summary": "Normalized exponential function.",
            "prerequisites": [],
            "unlocks": ["Attention Mechanism"],
            "related": [],
        },
        "gradient_descent": {
            "id": "gradient_descent",
            "name": "Gradient Descent",
            "label": "Gradient Descent",
            "difficulty": "foundational",
            "domain": "optimization",
            "summary": "First-order iterative optimization algorithm.",
            "prerequisites": [],
            "unlocks": ["Neural Network"],
            "related": [],
        },
        "loss_function": {
            "id": "loss_function",
            "name": "Loss Function",
            "label": "Loss Function",
            "difficulty": "foundational",
            "domain": "deep_learning",
            "summary": "Quantifies difference between prediction and ground truth.",
            "prerequisites": [],
            "unlocks": ["Neural Network"],
            "related": [],
        },
        "low_rank_adaptation": {
            "id": "low_rank_adaptation",
            "name": "Low-Rank Adaptation",
            "label": "Low-Rank Adaptation",
            "difficulty": "intermediate",
            "domain": "deep_learning",
            "summary": "Parameter-efficient fine-tuning via low-rank decomposition.",
            "prerequisites": ["Transformer"],
            "unlocks": [],
            "related": [],
        },
        "bert": {
            "id": "bert",
            "name": "BERT",
            "label": "BERT",
            "difficulty": "intermediate",
            "domain": "deep_learning",
            "summary": "Bidirectional transformer encoder.",
            "prerequisites": ["Transformer"],
            "unlocks": [],
            "related": [],
        },
        "gpt": {
            "id": "gpt",
            "name": "GPT",
            "label": "GPT",
            "difficulty": "intermediate",
            "domain": "deep_learning",
            "summary": "Autoregressive transformer decoder.",
            "prerequisites": ["Transformer"],
            "unlocks": [],
            "related": [],
        },
        "isolated_concept": {
            "id": "isolated_concept",
            "name": "Isolated Concept",
            "label": "Isolated Concept",
            "difficulty": "intermediate",
            "domain": "deep_learning",
            "summary": "An isolated test concept with no explicit links.",
            "prerequisites": [],
            "unlocks": [],
            "related": [],
        },
    }


def test_mode_c_bounds_and_structure(mock_concepts_data):
    sub = generate_bounded_subgraph("low_rank_adaptation", mode="mode_c", concepts_data=mock_concepts_data)
    assert isinstance(sub, BoundedSubgraph)
    assert 5 <= sub.node_count <= 10, f"Mode C node count {sub.node_count} violates 5 <= N <= 10 bound"
    assert sub.edge_count >= 1, "Mode C subgraph must have edges"
    assert "low_rank_adaptation" in sub.target_ids

    # Verify target has role 'target'
    target_nodes = [n for n in sub.nodes if n["id"] == "low_rank_adaptation"]
    assert len(target_nodes) == 1
    assert target_nodes[0]["role"] == "target"


def test_mode_c_pruning(mock_concepts_data):
    # Transformer has many 1-hop and 2-hop neighbors (linear_algebra, softmax, neural_network, gradient_descent, loss_function, bert, gpt, lora)
    sub = generate_bounded_subgraph("transformer", mode="mode_c", max_nodes=6, concepts_data=mock_concepts_data)
    assert sub.node_count <= 6, f"Pruning failed: got {sub.node_count} nodes > 6"
    assert sub.node_count >= 5, f"Pruning over-pruned: got {sub.node_count} nodes < 5"


def test_mode_c_backfill_and_connectivity(mock_concepts_data):
    # isolated_concept has 0 prereqs and 0 unlocks in mock_concepts_data
    sub = generate_bounded_subgraph("isolated_concept", mode="mode_c", min_nodes=5, concepts_data=mock_concepts_data)
    assert sub.node_count >= 5, f"Backfill failed: got {sub.node_count} nodes < 5"
    assert sub.node_count <= 10, f"Backfill exceeded max: got {sub.node_count} > 10"

    # Weak connectivity check: every node must have degree >= 1 in induced edges
    connected_ids = set()
    for e in sub.edges:
        connected_ids.add(e["from_id"])
        connected_ids.add(e["to_id"])
    for n in sub.nodes:
        assert n["id"] in connected_ids, f"Node {n['id']} is an isolated orphan in subgraph"


def test_mode_b_shortest_path_and_bridges(mock_concepts_data):
    sub = generate_bounded_subgraph(
        "low_rank_adaptation",
        secondary_target_id="linear_algebra",
        mode="mode_b",
        concepts_data=mock_concepts_data,
    )
    assert 5 <= sub.node_count <= 10
    node_ids = {n["id"] for n in sub.nodes}
    assert "low_rank_adaptation" in node_ids
    assert "linear_algebra" in node_ids
    assert sub.query_mode == "mode_b"


def test_mode_a_minimal_neighborhood(mock_concepts_data):
    sub = generate_bounded_subgraph("low_rank_adaptation", mode="mode_a", concepts_data=mock_concepts_data)
    assert sub.node_count <= 3, f"Mode A node count {sub.node_count} exceeds 3"
    assert sub.query_mode == "mode_a"
    node_ids = {n["id"] for n in sub.nodes}
    assert "low_rank_adaptation" in node_ids


def test_subgraph_serialization(mock_concepts_data):
    sub = generate_bounded_subgraph("transformer", mode="mode_c", concepts_data=mock_concepts_data)
    d = sub.to_dict()
    assert isinstance(d, dict)
    assert "nodes" in d
    assert "edges" in d
    assert "target_ids" in d
    assert "query_mode" in d
    assert "node_count" in d
    assert "edge_count" in d
    assert d["node_count"] == len(d["nodes"])
    assert d["edge_count"] == len(d["edges"])

"""Unit tests for GraphIntegrityValidator and Kahn's DAG sorting.

Verifies structural graph integrity guarantees including acyclicity, self-loop
rejection, reciprocal cycle detection, and orphan node reporting.
"""

from archipelago.graph.integrity import GraphIntegrityValidator, GraphIntegrityReport


def test_valid_dag_kahn_sort():
    """Verify that a valid DAG passes Kahn's sort and produces a valid topological ordering."""
    nodes = ["matrix_mult", "dot_product", "attention", "transformer"]
    edges = [
        {"from": "matrix_mult", "to": "attention", "relation": "REQUIRES"},
        {"from": "dot_product", "to": "attention", "relation": "REQUIRES"},
        {"from": "attention", "to": "transformer", "relation": "REQUIRES"},
    ]

    is_dag, order = GraphIntegrityValidator.run_kahn_dag_sort(nodes, edges, edge_type="REQUIRES")
    assert is_dag is True
    assert len(order) == 4
    # matrix_mult and dot_product must precede attention
    assert order.index("matrix_mult") < order.index("attention")
    assert order.index("dot_product") < order.index("attention")
    assert order.index("attention") < order.index("transformer")


def test_cycle_detection():
    """Verify that directed cycles (A -> B -> C -> A) are detected and fail DAG validation."""
    nodes = ["A", "B", "C"]
    edges = [
        {"from": "A", "to": "B", "relation": "REQUIRES"},
        {"from": "B", "to": "C", "relation": "REQUIRES"},
        {"from": "C", "to": "A", "relation": "REQUIRES"},
    ]

    is_dag, unvisited = GraphIntegrityValidator.run_kahn_dag_sort(nodes, edges, edge_type="REQUIRES")
    assert is_dag is False
    assert set(unvisited) == {"A", "B", "C"}


def test_self_loop_detection():
    """Verify that self-referencing edges (A -> A) are caught."""
    edges = [
        {"from": "A", "to": "A", "relation": "REQUIRES"},
        {"from": "A", "to": "B", "relation": "REQUIRES"},
    ]
    loops = GraphIntegrityValidator.check_self_loops(edges)
    assert loops == ["A"]


def test_reciprocal_cycle_detection():
    """Verify that mutual reciprocal dependencies (A REQUIRES B, B REQUIRES A) are caught."""
    edges = [
        {"from": "A", "to": "B", "relation": "REQUIRES"},
        {"from": "B", "to": "A", "relation": "REQUIRES"},
        {"from": "C", "to": "A", "relation": "REQUIRES"},
    ]
    reciprocal = GraphIntegrityValidator.check_reciprocal_cycles(edges, edge_type="REQUIRES")
    assert len(reciprocal) == 1
    assert set(reciprocal[0]) == {"A", "B"}


def test_orphan_node_detection():
    """Verify that disconnected orphan nodes with 0 degree are correctly identified."""
    nodes = ["A", "B", "C", "orphan_1", "orphan_2"]
    edges = [
        {"from": "A", "to": "B", "relation": "REQUIRES"},
        {"from": "B", "to": "C", "relation": "REQUIRES"},
    ]
    orphans = GraphIntegrityValidator.find_orphans(nodes, edges)
    assert orphans == ["orphan_1", "orphan_2"]


def test_validate_graph_report_valid_and_invalid():
    """Verify complete GraphIntegrityReport creation and is_valid property."""
    # Valid graph
    valid_nodes = ["A", "B", "C"]
    valid_edges = [
        {"from": "A", "to": "B", "relation": "REQUIRES"},
        {"from": "B", "to": "C", "relation": "REQUIRES"},
    ]
    report_valid = GraphIntegrityValidator.validate_graph(valid_nodes, valid_edges)
    assert report_valid.is_dag is True
    assert len(report_valid.self_loops) == 0
    assert len(report_valid.reciprocal_cycles) == 0
    assert report_valid.is_valid is True

    # Invalid graph with cycle and self-loop
    invalid_nodes = ["X", "Y", "Z"]
    invalid_edges = [
        {"from": "X", "to": "X", "relation": "REQUIRES"},
        {"from": "X", "to": "Y", "relation": "REQUIRES"},
        {"from": "Y", "to": "Z", "relation": "REQUIRES"},
        {"from": "Z", "to": "X", "relation": "REQUIRES"},
    ]
    report_invalid = GraphIntegrityValidator.validate_graph(invalid_nodes, invalid_edges)
    assert report_invalid.is_dag is False
    assert "X" in report_invalid.self_loops
    assert report_invalid.is_valid is False

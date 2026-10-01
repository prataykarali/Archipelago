#!/usr/bin/env python3
"""Graph integrity validation script for CI/CD.

Usage:
    python scripts/validate_graph.py
    python scripts/validate_graph.py --json-report report.json
    GRAPH_FILE=path/to/graph.json python scripts/validate_graph.py

Validates the Archipelago knowledge graph against structural integrity rules:
- Baseline node count (~5151)
- Duplicate node IDs
- Orphan nodes (no edges)
- Self-referencing edges
- Duplicate edges
- Invalid relationship types
- Missing source attribution
- Broken references (edges to non-existent nodes)

Exits non-zero if critical errors are found.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

VALID_RELATIONS = {
    "REQUIRES", "UNLOCKS", "RELATED", "MENTIONED_IN", "AUTHORED_BY",
    "BELONGS_TO", "CATEGORIZES", "PROVIDES_TEXT", "HAS_CHUNK", "MENTIONS",
}

BASELINE_NODE_COUNT = int(os.environ.get("BASELINE_NODE_COUNT", "514"))
NODE_COUNT_MIN = int(os.environ.get("NODE_COUNT_MIN", "500"))
NODE_COUNT_MAX = int(os.environ.get("NODE_COUNT_MAX", "6500"))


def load_graph(graph_path: str) -> dict:
    """Load the graph JSON file."""
    path = Path(graph_path)
    if not path.exists():
        print(f"ERROR: Graph file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def validate_nodes(nodes: list[dict]) -> tuple[set[str], set[str]]:
    """Validate nodes and return (node_ids, duplicate_ids)."""
    node_ids: set[str] = set()
    duplicates: set[str] = set()

    for node in nodes:
        nid = node.get("id")
        if not nid:
            continue
        if nid in node_ids:
            duplicates.add(nid)
        node_ids.add(nid)

    return node_ids, duplicates


def get_edge_endpoints(edge: dict) -> tuple[str | None, str | None, str]:
    """Extract source, target, and relation from an edge."""
    source_node = edge.get("from_id") or edge.get("source")
    target_node = edge.get("to_id") or edge.get("target")
    rel = edge.get("edge_type") or edge.get("relation") or "UNKNOWN"
    return source_node, target_node, str(rel).upper()


def has_attribution(edge: dict) -> bool:
    """Check whether an edge has source attribution."""
    return bool(
        edge.get("source_ref")
        or ("source" in edge and "from_id" in edge)
        or edge.get("attribution")
    )


def validate_edges(
    edges: list[dict], node_ids: set[str]
) -> dict[str, int | set[str]]:
    """Validate edges and return error counts."""
    broken_refs = 0
    self_refs = 0
    missing_source = 0
    invalid_relations = 0
    duplicate_edges = 0
    connected_nodes: set[str] = set()
    edge_set: set[tuple[str | None, str | None, str]] = set()

    for edge in edges:
        source_node, target_node, rel = get_edge_endpoints(edge)
        connected_nodes.add(source_node)  # type: ignore[arg-type]
        connected_nodes.add(target_node)  # type: ignore[arg-type]

        if source_node == target_node:
            self_refs += 1
        if source_node not in node_ids or target_node not in node_ids:
            broken_refs += 1
        if rel not in VALID_RELATIONS:
            invalid_relations += 1
        if not has_attribution(edge):
            missing_source += 1

        edge_sig = (source_node, target_node, rel)
        if edge_sig in edge_set:
            duplicate_edges += 1
        edge_set.add(edge_sig)

    return {
        "broken_refs": broken_refs,
        "self_refs": self_refs,
        "missing_source": missing_source,
        "invalid_relations": invalid_relations,
        "duplicate_edges": duplicate_edges,
        "connected_nodes": connected_nodes,
    }


def build_report(data: dict) -> dict:
    """Build the full integrity report."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    node_ids, duplicates = validate_nodes(nodes)
    edge_results = validate_edges(edges, node_ids)

    connected_nodes = edge_results.pop("connected_nodes")
    orphans = len(node_ids - connected_nodes)
    node_count = len(nodes)

    report = {
        "node_count": node_count,
        "edge_count": len(edges),
        "baseline_expected": BASELINE_NODE_COUNT,
        "duplicate_nodes": len(duplicates),
        "orphan_nodes": orphans,
        "self_refs": edge_results["self_refs"],
        "duplicate_edges": edge_results["duplicate_edges"],
        "invalid_relations": edge_results["invalid_relations"],
        "missing_source_attribution": edge_results["missing_source"],
        "broken_refs": edge_results["broken_refs"],
    }

    # Determine critical errors
    critical = (
        report["duplicate_nodes"] > 0
        or report["broken_refs"] > 0
        or report["self_refs"] > 0
        or report["invalid_relations"] > 0
    )

    # Node count warnings (non-critical unless drastically wrong)
    if node_count < NODE_COUNT_MIN:
        report["node_count_warning"] = (
            f"Node count {node_count} is below minimum {NODE_COUNT_MIN}"
        )
        critical = True
    elif node_count > NODE_COUNT_MAX:
        report["node_count_warning"] = (
            f"Node count {node_count} exceeds maximum {NODE_COUNT_MAX}"
        )

    # Warnings (non-critical)
    if report["duplicate_edges"] > 0:
        report["duplicate_edges_warning"] = True
    if report["orphan_nodes"] > 100:
        report["orphan_nodes_warning"] = True

    report["status"] = "FAIL" if critical else "PASS"
    return report


def main() -> int:
    """Run graph integrity validation."""
    parser = argparse.ArgumentParser(description="Validate Archipelago graph integrity")
    parser.add_argument(
        "--json-report",
        help="Write JSON report to this file path",
    )
    parser.add_argument(
        "--graph-file",
        default=os.environ.get("GRAPH_FILE", "okf_graph.json"),
        help="Path to okf_graph.json (default: okf_graph.json or $GRAPH_FILE)",
    )
    args = parser.parse_args()

    print(f"Loading graph from: {args.graph_file}")
    data = load_graph(args.graph_file)
    report = build_report(data)

    # Print report
    print("\n" + "=" * 50)
    print("  GRAPH INTEGRITY REPORT")
    print("=" * 50)
    print(f"  Nodes:              {report['node_count']}")
    print(f"  Edges:              {report['edge_count']}")
    print(f"  Baseline expected:  {report['baseline_expected']}")
    print(f"  Duplicate nodes:    {report['duplicate_nodes']}")
    print(f"  Orphan nodes:       {report['orphan_nodes']}")
    print(f"  Self-references:    {report['self_refs']}")
    print(f"  Duplicate edges:    {report['duplicate_edges']}")
    print(f"  Invalid relations:  {report['invalid_relations']}")
    print(f"  Missing attribution:{report['missing_source_attribution']}")
    print(f"  Broken references:  {report['broken_refs']}")
    print(f"  Status:             {report['status']}")
    print("=" * 50)

    if report.get("node_count_warning"):
        print(f"\n  ⚠ {report['node_count_warning']}")

    # Write JSON report if requested
    if args.json_report:
        with open(args.json_report, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  Report written to: {args.json_report}")

    if report["status"] == "FAIL":
        print("\n  ✗ Critical integrity errors found.")
        return 1

    print("\n  ✓ Graph integrity check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

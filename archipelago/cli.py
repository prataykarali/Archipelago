#!/usr/bin/env python3
"""Archipelago CLI — ingestion, graph management, and model operations.

Commands:
    archipelago ingest   --source <file>
    archipelago graph    validate | stats | diff
    archipelago model    download --repo <org/model>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_FILE = ROOT / "okf_graph.json"
SUPPORTED_EXTENSIONS = {".csv", ".ods", ".pdf", ".md", ".txt"}


# ─── Graph helpers ────────────────────────────────────────────


def _load_graph(path: Path | None = None) -> dict:
    """Load and return the graph JSON."""
    p = path or GRAPH_FILE
    if not p.exists():
        print(f"ERROR: Graph file not found: {p}", file=sys.stderr)
        sys.exit(1)
    with open(p) as f:
        return json.load(f)


def _edge_key(edge: dict) -> tuple[str, str, str]:
    """Canonical (source, target, relation) key for an edge."""
    src = edge.get("from_id") or edge.get("source") or ""
    tgt = edge.get("to_id") or edge.get("target") or ""
    rel = (edge.get("edge_type") or edge.get("relation") or "UNKNOWN").upper()
    return (src, tgt, rel)


# ─── Subcommands ──────────────────────────────────────────────


def cmd_ingest(args: argparse.Namespace) -> int:
    """Trigger ingestion of a local file."""
    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: File not found: {source}", file=sys.stderr)
        return 1
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        print(
            f"ERROR: Unsupported file type '{source.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            file=sys.stderr,
        )
        return 1

    # Compute file hash for deduplication
    sha = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    print(f"Source:     {source}")
    print(f"Type:       {source.suffix}")
    print(f"Size:       {source.stat().st_size:,} bytes")
    print(f"Hash:       {sha}")

    # Attempt to enqueue via JobStore
    try:
        sys.path.insert(0, str(ROOT))
        from ingestion_jobs import JobStore

        store = JobStore(str(ROOT / "jobs"))
        job = store.create(
            filename=source.name,
            title=source.stem.replace("_", " ").title(),
        )
        # Copy file to quarantine
        import shutil

        dest = Path(store.jobs_dir) / job["id"]
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest / f"upload{source.suffix}")

        print(f"Job ID:     {job['id']}")
        print(f"Status:     {job['status']}")
        print("\nJob enqueued. Start the ingestion worker to process.")
    except ImportError:
        print("\nWARNING: JobStore not available. File validated but not enqueued.")
        print("Run the full ingestion worker to process this file.")

    return 0


def cmd_graph_validate(args: argparse.Namespace) -> int:
    """Run graph integrity validation."""
    graph_path = args.graph_file or GRAPH_FILE
    # Delegate to the standalone validation script
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from validate_graph import load_graph, build_report

        data = load_graph(str(graph_path))
        report = build_report(data)

        for key, val in report.items():
            if key == "status":
                continue
            print(f"  {key}: {val}")

        print(f"\n  Status: {report['status']}")
        return 0 if report["status"] == "PASS" else 1
    except ImportError:
        # Fallback: run as subprocess
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_graph.py")],
            cwd=str(ROOT),
        )
        return result.returncode


def cmd_graph_stats(args: argparse.Namespace) -> int:
    """Print graph statistics."""
    data = _load_graph()
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # Node type distribution
    type_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()
    for node in nodes:
        ntype = node.get("concept_type", node.get("type", "unknown"))
        type_counts[ntype] += 1
        diff = node.get("difficulty", "unknown")
        difficulty_counts[diff] += 1

    # Edge relation distribution
    rel_counts: Counter[str] = Counter()
    for edge in edges:
        _, _, rel = _edge_key(edge)
        rel_counts[rel] += 1

    # Connection stats
    node_ids = {n.get("id") for n in nodes if n.get("id")}
    connections: Counter[str] = Counter()
    for edge in edges:
        src = edge.get("from_id") or edge.get("source") or ""
        tgt = edge.get("to_id") or edge.get("target") or ""
        connections[src] += 1
        connections[tgt] += 1

    avg_conn = sum(connections.values()) / max(len(node_ids), 1)
    top_10 = connections.most_common(10)

    print("=" * 50)
    print("  ARCHIPELAGO GRAPH STATISTICS")
    print("=" * 50)
    print(f"\n  Total nodes: {len(nodes)}")
    print(f"  Total edges: {len(edges)}")
    print(f"  Avg connections/node: {avg_conn:.1f}")

    print("\n  Node types:")
    for ntype, count in type_counts.most_common():
        print(f"    {ntype:20s} {count:>5}")

    print("\n  Difficulty distribution:")
    for diff, count in difficulty_counts.most_common():
        print(f"    {diff:20s} {count:>5}")

    print("\n  Edge types:")
    for rel, count in rel_counts.most_common():
        print(f"    {rel:20s} {count:>5}")

    print("\n  Top 10 most connected:")
    for nid, count in top_10:
        # Find node name
        name = nid
        for n in nodes:
            if n.get("id") == nid:
                name = n.get("concept_name", nid)
                break
        print(f"    {name:30s} {count:>5} connections")

    print("=" * 50)
    return 0


def cmd_graph_diff(args: argparse.Namespace) -> int:
    """Compare current graph against a baseline."""
    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"ERROR: Baseline file not found: {baseline_path}", file=sys.stderr)
        return 1

    current = _load_graph()
    with open(baseline_path) as f:
        baseline = json.load(f)

    cur_ids = {n.get("id") for n in current.get("nodes", []) if n.get("id")}
    base_ids = {n.get("id") for n in baseline.get("nodes", []) if n.get("id")}

    added_nodes = cur_ids - base_ids
    removed_nodes = base_ids - cur_ids

    cur_edges = {_edge_key(e) for e in current.get("edges", [])}
    base_edges = {_edge_key(e) for e in baseline.get("edges", [])}

    added_edges = cur_edges - base_edges
    removed_edges = base_edges - cur_edges

    print("=" * 50)
    print("  GRAPH DIFF REPORT")
    print("=" * 50)
    print(f"  Baseline nodes:  {len(base_ids)}")
    print(f"  Current nodes:   {len(cur_ids)}")
    print(f"  Added nodes:     {len(added_nodes)}")
    print(f"  Removed nodes:   {len(removed_nodes)}")
    print(f"  Baseline edges:  {len(base_edges)}")
    print(f"  Current edges:   {len(cur_edges)}")
    print(f"  Added edges:     {len(added_edges)}")
    print(f"  Removed edges:   {len(removed_edges)}")

    if added_nodes and len(added_nodes) <= 20:
        print("\n  Added nodes:")
        for nid in sorted(added_nodes):
            print(f"    + {nid}")
    if removed_nodes and len(removed_nodes) <= 20:
        print("\n  Removed nodes:")
        for nid in sorted(removed_nodes):
            print(f"    - {nid}")

    print("=" * 50)
    return 0


def cmd_model_download(args: argparse.Namespace) -> int:
    """Download a versioned model from Hugging Face."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: huggingface_hub not installed. Run: pip install huggingface-hub")
        return 1

    repo = args.repo
    revision = args.revision or "main"
    dest = Path(args.dest or str(ROOT / "models"))
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Downloading model: {repo} (revision: {revision})")
    print(f"Destination: {dest}")

    try:
        path = snapshot_download(
            repo_id=repo,
            revision=revision,
            local_dir=str(dest / repo.split("/")[-1]),
            token=os.environ.get("HF_TOKEN"),
        )
        print(f"\n✓ Model downloaded to: {path}")
        return 0
    except Exception as e:
        print(f"\nERROR: Download failed: {e}", file=sys.stderr)
        return 1


# ─── Main parser ──────────────────────────────────────────────


def main() -> None:
    """Archipelago CLI main entry point."""
    parser = argparse.ArgumentParser(
        prog="archipelago",
        description="Archipelago Knowledge Platform CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ingest
    ingest_p = subparsers.add_parser("ingest", help="Ingest a document")
    ingest_p.add_argument("--source", required=True, help="Path to source file")

    # graph
    graph_p = subparsers.add_parser("graph", help="Graph operations")
    graph_sub = graph_p.add_subparsers(dest="graph_command", help="Graph subcommands")

    validate_p = graph_sub.add_parser("validate", help="Validate graph integrity")
    validate_p.add_argument("--graph-file", help="Path to graph JSON")

    graph_sub.add_parser("stats", help="Print graph statistics")

    diff_p = graph_sub.add_parser("diff", help="Compare graphs")
    diff_p.add_argument("--baseline", required=True, help="Baseline graph JSON")

    # model
    model_p = subparsers.add_parser("model", help="Model operations")
    model_sub = model_p.add_subparsers(dest="model_command", help="Model subcommands")

    dl_p = model_sub.add_parser("download", help="Download model from HF")
    dl_p.add_argument("--repo", required=True, help="HF repo ID (org/model)")
    dl_p.add_argument("--revision", help="Model revision/tag (default: main)")
    dl_p.add_argument("--dest", help="Download destination directory")

    args = parser.parse_args()

    if args.command == "ingest":
        sys.exit(cmd_ingest(args))
    elif args.command == "graph":
        if args.graph_command == "validate":
            sys.exit(cmd_graph_validate(args))
        elif args.graph_command == "stats":
            sys.exit(cmd_graph_stats(args))
        elif args.graph_command == "diff":
            sys.exit(cmd_graph_diff(args))
        else:
            graph_p.print_help()
    elif args.command == "model":
        if args.model_command == "download":
            sys.exit(cmd_model_download(args))
        else:
            model_p.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

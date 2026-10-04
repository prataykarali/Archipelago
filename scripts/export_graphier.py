"""Export a rights-reviewed, graph-only dataset; never copy PDFs or raw passages.

Offline by default. Each node requires every source document in a reviewed
manifest: {"approved_documents": ["papers/example.pdf"]}. Publication is an
explicit --publish operation to Prataykarali/graphier, never Library_books.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

DESTINATION = "Prataykarali/graphier"
NODE_FIELDS = ("id", "label", "name", "summary", "concept_type", "difficulty")
SOURCE_FIELDS = ("doc_id", "page_number", "section_title")
SENSITIVE = re.compile(r"(?i)(?:password|api[_ -]?key|secret|access[_ -]?token)\s*[:=]|[\w.+-]+@[\w.-]+\.[a-z]{2,}")
MAX_SUMMARY_CHARS = 1200


def export_graph(graph: dict, approved: set[str]) -> dict:
    """Filter to explicitly approved sources and idempotently deduplicate graph records."""
    nodes = {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict) or not node.get("id"):
            continue
        if node.get("private") or str(node.get("visibility", "")).lower() in {"private", "restricted", "confidential"}:
            continue
        sources = node.get("sources") or []
        if not sources or any(
            not isinstance(source, dict) or source.get("doc_id") not in approved
            for source in sources
        ):
            continue
        source_records = [
            {key: source.get(key) for key in SOURCE_FIELDS}
            for source in sources if isinstance(source.get("page_number"), int) and source["page_number"] > 0
        ]
        if not source_records:
            continue
        record = {key: node[key] for key in NODE_FIELDS if key in node}
        if SENSITIVE.search(json.dumps(record)):
            continue
        record["summary"] = str(record.get("summary", ""))[:MAX_SUMMARY_CHARS]
        record["sources"] = sorted(
            {json.dumps(source, sort_keys=True) for source in source_records}
        )
        record["sources"] = [json.loads(source) for source in record["sources"]]
        nodes[str(node["id"])] = record
    edges = set()
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = edge.get("from_id") or edge.get("source")
        target = edge.get("to_id") or edge.get("target")
        relation = edge.get("edge_type") or edge.get("relation")
        if source in nodes and target in nodes and isinstance(relation, str):
            edges.add((source, target, relation))
    return {
        "nodes": [nodes[key] for key in sorted(nodes)],
        "edges": [
            {"from_id": source, "to_id": target, "edge_type": relation}
            for source, target, relation in sorted(edges)
        ],
    }


def main() -> None:
    """Produce a reviewable export; publishing requires explicit rights and credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--rights-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.rights_manifest.read_text())
    approved = manifest.get("approved_documents")
    if not isinstance(approved, list) or not all(isinstance(doc, str) for doc in approved):
        parser.error("approved_documents must be an explicitly reviewed list of document IDs")
    output = export_graph(json.loads(args.graph.read_text()), set(approved))
    if not output["nodes"]:
        parser.error("No publishable nodes; no dataset was created or updated")
    args.output.mkdir(parents=True, exist_ok=True)
    graph_path = args.output / "okf_graph.json"
    graph_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    audit = {
        "destination": DESTINATION, "nodes": len(output["nodes"]), "edges": len(output["edges"]),
        "sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "raw_content_included": False, "source_dataset_modified": False,
    }
    audit_path = args.output / "export_manifest.json"
    audit_path.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))
    if args.publish:
        if not os.getenv("HF_TOKEN"):
            parser.error("HF_TOKEN is required; the local export is available for review")
        from huggingface_hub import HfApi

        api = HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(DESTINATION, repo_type="dataset", private=True, exist_ok=True)
        for path in (graph_path, audit_path):
            api.upload_file(
                path_or_fileobj=str(path), path_in_repo=path.name,
                repo_id=DESTINATION, repo_type="dataset",
                commit_message="Publish rights-reviewed graph metadata only",
            )
        print(f"Published graph metadata to {DESTINATION}; existing visibility retained.")


if __name__ == "__main__":
    main()

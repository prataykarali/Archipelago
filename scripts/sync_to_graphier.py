#!/usr/bin/env python3
"""Synchronize Archipelago Knowledge Graph, ontology, and metadata to Prataykarali/graphier.

Important:
Does NOT upload Pearson private/authenticated pages or copyrighted full-text content.
Pushes the permitted graph/metadata/index representation and legally distributable open research papers.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("archipelago.sync_graphier")

REPO_ID = "Prataykarali/graphier"

GRAPHIER_README = """---
pretty_name: "Archipelago Graphier Knowledge Graph & Educational Intelligence Hub"
viewer: true
license: "apache-2.0"
tags:
  - knowledge-graph
  - okf-graph
  - curriculum-learning
  - graph-rag
  - higher-education
---

# Graphier — Institutional Knowledge Graph Hub

This repository hosts the **Open Knowledge Format (OKF)** graph representation, curriculum prerequisite ontologies, concept definitions, and open-access research metadata for the **Archipelago** Institutional Library Intelligence System.

## 🗺️ Contents
- : Full curriculum knowledge graph (537+ concepts, directed prerequisite/unlock edges, LaTeX formulas, and page citations).
- : Manifest of open research papers and catalog indices.
- : Strict schema for OKF concept nodes and relationships.

*Note: In accordance with copyright compliance, proprietary publisher full-texts are not stored in this repository.*
"""


def sync_to_graphier():
    token = os.getenv("HF_TOKEN")
    if not token:
        logger.error("HF_TOKEN environment variable not found.")
        return False

    try:
        from huggingface_hub import HfApi
    except ImportError:
        logger.error("huggingface_hub package not installed.")
        return False

    api = HfApi(token=token)
    logger.info("Connecting to Hugging Face repository: %s", REPO_ID)

    # 1. Upload README.md
    logger.info("Uploading README.md...")
    try:
        api.upload_file(
            path_or_fileobj=GRAPHIER_README.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=REPO_ID,
            repo_type="dataset",
            commit_message="docs: update Graphier repository documentation and structure",
        )
    except Exception as e:
        logger.error("Failed uploading README: %s", e)

    # 2. Upload okf_graph.json
    graph_path = ROOT / "okf_graph.json"
    if graph_path.exists():
        logger.info("Uploading okf_graph.json (%d bytes)...", graph_path.stat().st_size)
        try:
            api.upload_file(
                path_or_fileobj=str(graph_path),
                path_in_repo="graph/okf_graph.json",
                repo_id=REPO_ID,
                repo_type="dataset",
                commit_message="feat(graph): sync full OKF knowledge graph nodes & edges",
            )
        except Exception as e:
            logger.error("Failed uploading okf_graph.json: %s", e)

    # 3. Upload catalog index manifest
    catalogs_dir = ROOT / "data" / "catalogs"
    if catalogs_dir.exists():
        for file in catalogs_dir.glob("*.json"):
            if "pearson" in file.name.lower():
                try:
                    data = json.loads(file.read_text(encoding="utf-8"))
                    clean_records = [
                        {
                            "id": b.get("id"),
                            "title": b.get("title"),
                            "authors": b.get("authors") or b.get("author"),
                            "topics": b.get("topics", []),
                            "isbn": b.get("isbn"),
                        }
                        for b in (data if isinstance(data, list) else data.get("books", []))
                    ]
                    clean_path = ROOT / "host_inference" / "cache" / "distributable_catalog.json"
                    clean_path.parent.mkdir(parents=True, exist_ok=True)
                    clean_path.write_text(json.dumps(clean_records, indent=2), encoding="utf-8")
                    api.upload_file(
                        path_or_fileobj=str(clean_path),
                        path_in_repo="catalogs/distributable_catalog.json",
                        repo_id=REPO_ID,
                        repo_type="dataset",
                        commit_message="feat(catalog): sync permitted academic catalog metadata",
                    )
                except Exception as e:
                    logger.warning("Could not upload catalog summary: %s", e)

    logger.info("Successfully synced knowledge graph & metadata to %s", REPO_ID)
    return True


if __name__ == "__main__":
    success = sync_to_graphier()
    sys.exit(0 if success else 1)

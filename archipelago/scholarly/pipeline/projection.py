"""Rebuild isolated research graph and vector-input projections from PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import uuid

import kuzu

from archipelago.scholarly.pipeline.postgres_store import PostgresResearchStore
from archipelago.scholarly.pipeline.vector_projection import build_vector_projection

GRAPH_SCHEMA = (
    "CREATE NODE TABLE Paper (id STRING PRIMARY KEY, title STRING, doi STRING)",
    "CREATE NODE TABLE Author (id STRING PRIMARY KEY, name STRING)",
    "CREATE NODE TABLE Venue (id STRING PRIMARY KEY, name STRING)",
    "CREATE NODE TABLE Dataset (id STRING PRIMARY KEY, name STRING)",
    "CREATE NODE TABLE Claim (id STRING PRIMARY KEY, text STRING)",
    "CREATE NODE TABLE Evidence (id STRING PRIMARY KEY, artifact_sha256 STRING, page INT64)",
    "CREATE REL TABLE AUTHORED_BY (FROM Paper TO Author)",
    "CREATE REL TABLE PUBLISHED_IN (FROM Paper TO Venue)",
    "CREATE REL TABLE USES_DATASET (FROM Paper TO Dataset)",
    "CREATE REL TABLE ASSERTS (FROM Paper TO Claim)",
    "CREATE REL TABLE SUPPORTED_BY (FROM Claim TO Evidence)",
)


def _name_id(name: str) -> str:
    return hashlib.sha256(name.casefold().strip().encode()).hexdigest()


def rebuild_projection(store: PostgresResearchStore, graph_path: Path) -> dict[str, int]:
    """Build a new Kùzu graph; refuse to overwrite an existing database."""
    if graph_path.exists():
        raise FileExistsError(graph_path)
    records = store.projection_records()
    evidence_rows = store.projection_evidence()
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    database = kuzu.Database(str(graph_path))
    conn = kuzu.Connection(database)
    for statement in GRAPH_SCHEMA:
        conn.execute(statement)
    known_authors: set[str] = set()
    known_venues: set[str] = set()
    known_datasets: set[str] = set()
    vector_inputs: list[dict[str, Any]] = []
    for row in records:
        paper = row["paper"]
        paper_id = str(row["paper_id"])
        title = paper["title"]
        ids = paper.get("identifiers") or {}
        conn.execute(
            "CREATE (p:Paper {id: $id, title: $title, doi: $doi})",
            {"id": paper_id, "title": title, "doi": ids.get("doi") or ""},
        )
        vector_inputs.append(
            {
                "paper_id": paper_id,
                "text": " ".join(text for text in (title, paper.get("abstract")) if text),
            }
        )
        for author in paper.get("authors") or []:
            name = author.get("name")
            if not name:
                continue
            author_id = _name_id(name)
            if author_id not in known_authors:
                conn.execute(
                    "CREATE (a:Author {id: $id, name: $name})", {"id": author_id, "name": name}
                )
                known_authors.add(author_id)
            conn.execute(
                "MATCH (p:Paper {id: $paper}), (a:Author {id: $author}) CREATE (p)-[:AUTHORED_BY]->(a)",
                {"paper": paper_id, "author": author_id},
            )
        venue = paper.get("venue")
        if venue:
            venue_id = _name_id(venue)
            if venue_id not in known_venues:
                conn.execute(
                    "CREATE (v:Venue {id: $id, name: $name})", {"id": venue_id, "name": venue}
                )
                known_venues.add(venue_id)
            conn.execute(
                "MATCH (p:Paper {id: $paper}), (v:Venue {id: $venue}) CREATE (p)-[:PUBLISHED_IN]->(v)",
                {"paper": paper_id, "venue": venue_id},
            )
    known_claims: set[str] = set()
    known_evidence: set[str] = set()
    for row in evidence_rows:
        paper_id = str(row["paper_id"])
        artifact = row["artifact_sha256"]
        extracted = row["evidence"]
        pointers = {p["provenance_id"]: p for p in extracted.get("provenance", [])}
        for dataset in extracted.get("datasets", []):
            name = dataset.get("name")
            if not name:
                continue
            dataset_id = _name_id(name)
            if dataset_id not in known_datasets:
                conn.execute(
                    "CREATE (d:Dataset {id: $id, name: $name})", {"id": dataset_id, "name": name}
                )
                known_datasets.add(dataset_id)
            conn.execute(
                "MATCH (p:Paper {id: $paper}), (d:Dataset {id: $dataset}) CREATE (p)-[:USES_DATASET]->(d)",
                {"paper": paper_id, "dataset": dataset_id},
            )
        for claim in extracted.get("claims", []):
            claim_id = claim["claim_id"]
            if claim_id not in known_claims:
                conn.execute(
                    "CREATE (c:Claim {id: $id, text: $text})",
                    {"id": claim_id, "text": claim["text"]},
                )
                known_claims.add(claim_id)
                conn.execute(
                    "MATCH (p:Paper {id: $paper}), (c:Claim {id: $claim}) CREATE (p)-[:ASSERTS]->(c)",
                    {"paper": paper_id, "claim": claim_id},
                )
            for pointer_id in claim.get("provenance_ids", []):
                pointer = pointers.get(pointer_id)
                if not pointer or pointer.get("artifact_sha256") != artifact:
                    continue
                if pointer_id not in known_evidence:
                    conn.execute(
                        "CREATE (e:Evidence {id: $id, artifact_sha256: $artifact, page: $page})",
                        {"id": pointer_id, "artifact": artifact, "page": pointer.get("page")},
                    )
                    known_evidence.add(pointer_id)
                conn.execute(
                    "MATCH (c:Claim {id: $claim}), (e:Evidence {id: $evidence}) CREATE (c)-[:SUPPORTED_BY]->(e)",
                    {"claim": claim_id, "evidence": pointer_id},
                )
    vector_path = graph_path.with_suffix(".vector-inputs.jsonl")
    vector_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in vector_inputs),
        encoding="utf-8",
    )
    return {
        "papers": len(records),
        "authors": len(known_authors),
        "venues": len(known_venues),
        "datasets": len(known_datasets),
        "claims": len(known_claims),
        "evidence": len(known_evidence),
    }


def refresh_pending_projection(
    store: PostgresResearchStore,
    root: Path,
) -> dict[str, Any] | None:
    """Build a new graph generation and atomically publish its pointer."""
    pending = store.pending_projection_events()
    if not pending:
        return None
    root.mkdir(parents=True, exist_ok=True)
    generation = f"research-{uuid.uuid4().hex}"
    graph_path = root / generation
    counts = rebuild_projection(store, graph_path)
    vector = build_vector_projection(graph_path.with_suffix(".vector-inputs.jsonl"))
    payload = {
        "generation": generation,
        "graph_path": str(graph_path),
        "vector_inputs_path": str(graph_path.with_suffix(".vector-inputs.jsonl")),
        "published_at": datetime.now(UTC).isoformat(),
        "counts": counts,
        "vector": vector,
    }
    temp_pointer = root / f"current-{generation}.tmp"
    temp_pointer.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temp_pointer, root / "current.json")
    store.complete_projection_events(pending, str(graph_path))
    return payload

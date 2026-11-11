"""Exact staged evidence and attributable librarian decisions."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

from .store import AcademicStore, now

HASH_BLOCK_BYTES = 1024 * 1024


def _hash_file(digest: Any, path: Path) -> None:
    with path.open("rb") as source:
        while block := source.read(HASH_BLOCK_BYTES):
            digest.update(block)


def review_digest(job: dict[str, Any], root: Path) -> str:
    """Bind a decision to the exact results, staging graph, and baseline."""
    job_id = str(UUID(str(job["job_id"])))
    directory = root / "data" / "academic_jobs" / job_id
    staging = Path(str(job["staging_path"])).resolve()
    if not staging.is_relative_to(directory.resolve()) or not staging.is_file():
        raise ValueError("Staged graph is unavailable")
    digest = sha256(str(job["baseline_version"]).encode())
    for path in (directory / "results.json", staging):
        _hash_file(digest, path)
    return digest.hexdigest()


def review_packet(store: AcademicStore, job_id: str, root: Path) -> dict[str, Any]:
    """Return every extracted row and every proposed typed relationship."""
    from okf.graph.safe_staging import extract_graph_inventory

    job_id = str(UUID(job_id))
    job = store.job(job_id)
    if job is None or job["status"] not in {"review_ready", "published"}:
        raise ValueError("Review-ready job not found")
    directory = root / "data" / "academic_jobs" / job_id
    rows = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Invalid extracted rows")
    for row in rows:
        chapter_url = str(row.get("source_url") or "")
        for source in row.get("sources") or []:
            title = str(source.get("section_title") or "")
            anchor = re.sub(r"[^a-z0-9 -]", "", title.lower()).strip().replace(" ", "-")
            source["section_url"] = f"{chapter_url}#{anchor}" if anchor else chapter_url
    canonical = root / "okf_graph.db"
    canonical_digest = sha256()
    _hash_file(canonical_digest, canonical)
    if canonical_digest.hexdigest() != job["baseline_version"]:
        raise ValueError("Canonical graph changed since staging")
    with TemporaryDirectory(prefix="academic-review-") as scratch:
        copy = Path(scratch) / "baseline.db"
        shutil.copy2(canonical, copy)
        baseline = extract_graph_inventory(copy)
    staged = extract_graph_inventory(Path(str(job["staging_path"])))
    existing = {(edge["from_id"], edge["to_id"], edge["type"]) for edge in baseline["edges"]}
    proposed = sorted(
        (edge["from_id"], edge["to_id"], edge["type"])
        for edge in staged["edges"]
        if (edge["from_id"], edge["to_id"], edge["type"]) not in existing
    )
    passages: dict[str, dict[str, Any]] = {}
    for row in rows:
        for source in row.get("sources") or []:
            key = str(source.get("chunk_id") or "")
            if key:
                passages[key] = source
    edges = []
    for source_id, target_id, relation in proposed:
        evidence = []
        relation_key = {"RELATED": "related", "UNLOCKS": "unlock", "REQUIRES": "prerequisite"}[
            relation
        ]
        for row in rows:
            if source_id != str(row.get("concept_name", "")).lower().replace(" ", "_"):
                continue
            provenance = row.get("relation_provenance") or {}
            key = f"{relation_key}:{target_id.replace('_', ' ')}"
            value = provenance.get(key)
            if value:
                chunk = str(value).split(":")[-1]
                if chunk in passages:
                    evidence.append({"chunk_id": chunk, **passages[chunk]})
        edges.append(
            {"from_id": source_id, "to_id": target_id, "type": relation, "evidence": evidence}
        )
    return {
        "job_id": job_id,
        "status": job["status"],
        "publication_status": (
            "APPROVED"
            if (store.review_decision(job_id) or {}).get("decision") == "approve"
            else "BLOCKED"
        ),
        "review_digest": review_digest(job, root),
        "baseline_version": job["baseline_version"],
        "rows": rows,
        "edges": edges,
        "decision": store.review_decision(job_id),
    }


def decide(
    store: AcademicStore,
    job_id: str,
    root: Path,
    *,
    decision: str,
    reviewer_id: str,
    reviewer_name: str,
    role: str,
    digest: str,
    note: str,
) -> dict[str, Any]:
    """Persist a staff decision; approval always covers the whole staged graph."""
    if role not in {"librarian", "administrator"} or not reviewer_id.strip():
        raise PermissionError("Independent librarian identity required")
    if decision not in {"approve", "reject"}:
        raise ValueError("Decision must be approve or reject")
    packet = review_packet(store, job_id, root)
    if packet["status"] != "review_ready" or digest != packet["review_digest"]:
        raise ValueError("Review changed; reload the exact staging evidence")
    if decision == "reject" and not note.strip():
        raise ValueError("A rejection needs a reason")
    result = {
        "decision": decision,
        "reviewer_id": reviewer_id,
        "reviewer_name": reviewer_name,
        "reviewer_role": role,
        "review_digest": digest,
        "at": now(),
        "note": note.strip(),
        "concept_count": len(packet["rows"]),
        "edge_count": len(packet["edges"]),
    }
    store.record_review(job_id, result)
    return result

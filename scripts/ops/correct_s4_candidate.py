"""Rebuild the D2L S4 review candidate from itemized scientific decisions."""

from __future__ import annotations

import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from archipelago.academic_automation import AcademicStore  # noqa: E402
from archipelago.academic_automation.review import review_digest  # noqa: E402
from okf.graph.ingest import ingest_to_kuzu  # noqa: E402
from okf.graph.safe_staging import (  # noqa: E402
    extract_graph_inventory,
    prepare_staging_database,
    validate_staging_against_production,
)
from okf.util import create_concept_id  # noqa: E402

JOB_ID = "bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe"
ORIGINAL_RESULTS_SHA = "564e3b6e423306eb9d51e4d734ddf885ac7b264cefd38cc58f86ec444135d47c"
CHAPTER_URL = "https://d2l.ai/chapter_linear-regression/linear-regression.html"
LICENSE = "CC-BY-SA-4.0"
NO_PRINTED_PAGE = 0
MAX_REVIEW_PROGRESS = 100

from s4_scientific_decisions import CONCEPT_DECISIONS, EDGE_DECISIONS  # noqa: E402


def file_sha(path: Path) -> str:
    """Hash a potentially large graph without loading it into memory."""
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def edge_key(edge: dict[str, str]) -> tuple[str, str, str]:
    """Use the typed graph identity, excluding incidental edge properties."""
    return edge["from_id"], edge["to_id"], edge["type"]


def source_for_edge(key: tuple[str, str, str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Locate the exact chunk that asserted a proposed edge."""
    source_id, target_id, relation = key
    key_prefix = {"RELATED": "related", "UNLOCKS": "unlock", "REQUIRES": "prereq"}[relation]
    target_name = target_id.replace("_", " ")
    chunks = {
        str(source.get("chunk_id")): source for row in rows for source in row.get("sources") or []
    }
    for row in rows:
        if create_concept_id(row["concept_name"]) != source_id:
            continue
        ref = (row.get("relation_provenance") or {}).get(f"{key_prefix}:{target_name}")
        if ref:
            chunk_id = str(ref).rsplit(":", 1)[-1]
            if chunk_id in chunks:
                return chunks[chunk_id]
    raise ValueError(f"No exact evidence chunk for {key}")


def correct() -> dict[str, Any]:
    """Audit every proposal, rebuild an isolated graph, and keep review pending."""
    job_dir = ROOT / "data" / "academic_jobs" / JOB_ID
    state = AcademicStore(ROOT / "data" / "academic_automation" / "state.sqlite3")
    job = state.job(JOB_ID)
    if job is None or job["status"] != "review_ready" or state.review_decision(JOB_ID):
        raise ValueError("Only an unreviewed review-ready candidate may be corrected")
    canonical = ROOT / "okf_graph.db"
    if file_sha(canonical) != job["baseline_version"]:
        raise ValueError("Canonical graph has changed")
    original = job_dir / "results.original.json"
    current = job_dir / "results.json"
    if not original.exists():
        if file_sha(current) != ORIGINAL_RESULTS_SHA:
            raise ValueError("Unrecognized source candidate")
        shutil.copy2(current, original)
    if file_sha(original) != ORIGINAL_RESULTS_SHA:
        raise ValueError("Original extraction changed")
    rows = json.loads(original.read_text(encoding="utf-8"))
    if {row["concept_name"] for row in rows} != set(CONCEPT_DECISIONS):
        raise ValueError("Concept decision coverage is incomplete")
    chapter = Path(str(job["content_path"])).read_text(encoding="utf-8")
    if file_sha(Path(str(job["content_path"]))) != job["content_sha256"]:
        raise ValueError("Approved chapter changed")
    for row in rows:
        if (
            row.get("source_url") != CHAPTER_URL
            or row.get("source_license") != LICENSE
            or row.get("page_number") != NO_PRINTED_PAGE
            or row.get("source_passage") not in chapter
        ):
            raise ValueError(f"Source provenance failed: {row['concept_name']}")
        for source in row.get("sources") or []:
            if (
                source.get("text_passage") not in chapter
                or source.get("page_number") != NO_PRINTED_PAGE
            ):
                raise ValueError(f"Chunk provenance failed: {row['concept_name']}")
    baseline_copy = job_dir / "review_baseline.db"
    try:
        shutil.copy2(canonical, baseline_copy)
        baseline = extract_graph_inventory(baseline_copy)
    finally:
        baseline_copy.unlink(missing_ok=True)
    old_stage = Path(str(job["staging_path"]))
    old_stage_backup = job_dir / "staging.pre-correction.db"
    old_inventory = extract_graph_inventory(
        old_stage_backup if old_stage_backup.exists() else old_stage
    )
    baseline_edges = {edge_key(edge) for edge in baseline["edges"]}
    old_edges = {edge_key(edge) for edge in old_inventory["edges"]} - baseline_edges
    if old_edges != set(EDGE_DECISIONS):
        raise ValueError("Edge decision coverage is incomplete")
    concept_audit = []
    corrected = []
    for row in rows:
        name = row["concept_name"]
        action, reason, summary = CONCEPT_DECISIONS[name]
        concept_audit.append(
            {
                "concept": name,
                "action": action,
                "reason": reason,
                "original_summary": row["summary"],
                "proposed_summary": summary or row["summary"],
                "source_excerpt": row["source_passage"],
                "section_title": row["section_title"],
                "section_url": CHAPTER_URL + "#" + row["section_title"].lower().replace(" ", "-"),
                "chunk_id": row["chunk_id"],
                "license": LICENSE,
            }
        )
        if action == "REJECT":
            continue
        clean = dict(row)
        if summary:
            clean["summary"] = summary
        clean["prerequisites"] = []
        clean["unlocks"] = []
        clean["related_to"] = []
        clean["relation_provenance"] = {}
        corrected.append(clean)
    by_id = {create_concept_id(row["concept_name"]): row for row in corrected}
    edge_audit = []
    for key in sorted(old_edges):
        action, reason, semantic_label = EDGE_DECISIONS[key]
        source = source_for_edge(key, rows)
        edge_audit.append(
            {
                "from_id": key[0],
                "to_id": key[1],
                "type": key[2],
                "action": action,
                "reason": reason,
                "proposed_relation": semantic_label,
                "source_excerpt": source["text_passage"],
                "section_title": source["section_title"],
                "section_url": CHAPTER_URL
                + "#"
                + source["section_title"].lower().replace(" ", "-"),
                "chunk_id": source["chunk_id"],
                "license": LICENSE,
            }
        )
        if action == "REJECT":
            continue
        if key[2] != "RELATED" or not semantic_label or key[0] not in by_id:
            raise ValueError(f"Kept edge is not representable: {key}")
        target = next(
            (
                row["concept_name"]
                for row in corrected
                if create_concept_id(row["concept_name"]) == key[1]
            ),
            None,
        )
        if target is None:
            raise ValueError(f"Kept edge target has no retained concept: {key}")
        by_id[key[0]]["related_to"].append({"concept": target, "relation": semantic_label})
        by_id[key[0]]["relation_provenance"][f"related:{target.lower()}"] = (
            f"{source['doc_id']}:{source['chunk_id']}"
        )
    temp_stage = job_dir / "staging.corrected.tmp.db"
    prepare_staging_database(temp_stage, canonical)
    connection, staged_db, _export = ingest_to_kuzu(
        corrected, db_path=str(temp_stage), incremental=True
    )
    connection.close()
    staged_db.close()
    del connection, staged_db
    gc.collect()
    validation = validate_staging_against_production(
        temp_stage, baseline["concept_ids"], baseline_edges
    )
    new_inventory = extract_graph_inventory(temp_stage)
    if (
        baseline["doc_ids"] - new_inventory["doc_ids"]
        or baseline["chunk_ids"] - new_inventory["chunk_ids"]
    ):
        raise ValueError("Existing document or chunk identity was lost")
    kept_edges = {key for key, decision in EDGE_DECISIONS.items() if decision[0] != "REJECT"}
    if {edge_key(edge) for edge in new_inventory["edges"]} - baseline_edges != kept_edges:
        raise ValueError("Corrected graph does not match the approved semantic edge set")
    if file_sha(canonical) != job["baseline_version"]:
        raise RuntimeError("Canonical changed while rebuilding stage")
    audit = {
        "job_id": JOB_ID,
        "chapter_url": CHAPTER_URL,
        "license": LICENSE,
        "concepts": concept_audit,
        "edges": edge_audit,
        "baseline_version": job["baseline_version"],
        "validation": validation,
        "source_sha256": job["content_sha256"],
    }
    audit_path = job_dir / "review_recommendations.json"
    corrected_path = job_dir / "results.corrected.tmp.json"
    corrected_path.write_text(json.dumps(corrected, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if not old_stage_backup.exists():
        shutil.copy2(old_stage, old_stage_backup)
    os.replace(temp_stage, old_stage)
    os.replace(corrected_path, current)
    (job_dir / "validation.json").write_text(
        json.dumps(validation, sort_keys=True, indent=2), encoding="utf-8"
    )
    state.update_job(
        JOB_ID,
        "review_ready",
        progress={
            "stage": "scientific_review",
            "percent": MAX_REVIEW_PROGRESS,
            "new_concepts": validation["added_concepts"],
            "new_edges": validation["added_edges"],
        },
    )
    state.audit(
        "s4_scientific_correction",
        "candidate_corrected",
        JOB_ID,
        {
            "concept_rows": len(corrected),
            "added_edges": validation["added_edges"],
            "staging_sha256": file_sha(old_stage),
        },
    )
    return {
        "rows": len(corrected),
        "added_concepts": validation["added_concepts"],
        "added_edges": validation["added_edges"],
        "staging_sha256": file_sha(old_stage),
        "review_digest": review_digest(state.job(JOB_ID), ROOT),
        "validation": validation,
    }


if __name__ == "__main__":
    print(json.dumps(correct(), sort_keys=True, indent=2))

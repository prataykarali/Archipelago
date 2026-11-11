"""Human-reviewed publication of a staged academic graph."""

from __future__ import annotations

from hashlib import sha256
import json
import logging
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Any

from .store import AcademicStore

LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def publish_reviewed(
    store: AcademicStore, job_id: str, root: Path, *, reviewer: str
) -> dict[str, Any]:
    """Revalidate preservation, back up production, and atomically publish."""
    from okf.graph.merge_document import (
        assert_merge_safe,
        doc_ids_in_results,
        load_okf_results,
        merge_okf_results,
        write_okf_results_atomic,
    )
    from okf.graph.safe_staging import (
        create_graph_backup,
        extract_graph_inventory,
        publish_staging_graph,
        rollback_from_backup,
        validate_staging_against_production,
    )

    job = store.job(job_id)
    if job is None or job["status"] != "review_ready":
        raise ValueError("Only a reviewed staging candidate can be published")
    if not reviewer.strip():
        raise ValueError("Named independent reviewer required")
    from .review import review_digest

    decision = store.review_decision(job_id)
    if (
        decision is None
        or decision["decision"] != "approve"
        or decision["reviewer_id"] != reviewer
        or decision["review_digest"] != review_digest(job, root)
    ):
        raise PermissionError("Exact staging graph lacks attributable human approval")
    canonical = root / "okf_graph.db"
    staging = Path(str(job["staging_path"])).resolve()
    job_dir = root / "data" / "academic_jobs" / job_id
    if not staging.is_relative_to(job_dir.resolve()) or not staging.exists():
        raise ValueError("Staged graph is unavailable")
    if _digest(canonical) != job["baseline_version"]:
        raise RuntimeError("Production graph changed after staging; restage the job")
    with TemporaryDirectory(prefix="academic-publication-") as scratch:
        snapshot = Path(scratch) / "baseline.db"
        shutil.copy2(canonical, snapshot)
        baseline = extract_graph_inventory(snapshot)
    edges = {(edge["from_id"], edge["to_id"], edge["type"]) for edge in baseline["edges"]}
    validation = validate_staging_against_production(staging, baseline["concept_ids"], edges)
    results_file = job_dir / "results.json"
    results = json.loads(results_file.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise ValueError("Staged OKF results are invalid")
    prior_results = root / "okf_results.json"
    prior_rows = load_okf_results(prior_results)
    incoming_doc_ids = doc_ids_in_results(results)
    if not incoming_doc_ids:
        raise ValueError("Staged OKF results have no source document")
    prior_other_documents = [
        row for row in prior_rows if str(row.get("doc_id") or "") not in incoming_doc_ids
    ]
    merged_results = merge_okf_results(prior_other_documents, results)
    for doc_id in incoming_doc_ids:
        assert_merge_safe(
            doc_ids_in_results(prior_rows), doc_ids_in_results(merged_results), doc_id
        )
    prior_copy = job_dir / "prior_results.json"
    if prior_results.exists():
        shutil.copy2(prior_results, prior_copy)
    backup = create_graph_backup(canonical)
    store.audit(
        reviewer, "publication_approved", job_id, {"backup": str(backup), "validation": validation}
    )
    try:
        publish_staging_graph(staging, canonical)
        write_okf_results_atomic(prior_results, merged_results)
    except Exception:
        LOGGER.exception("Academic graph publication failed; restoring backup")
        rollback_from_backup(backup, canonical)
        if prior_copy.exists():
            shutil.copy2(prior_copy, prior_results)
        store.update_job(
            job_id, "publication_failed", error="Publication failed; graph rollback attempted"
        )
        raise
    version = _digest(canonical)
    store.update_job(
        job_id,
        "published",
        published_version=version,
        publication_backup=str(backup),
        progress={"stage": "published", "validation": validation},
    )
    try:
        from archipelago.inference.inventory_ssot import clear_all_inventory_caches
        from archipelago.inference.state import reload_db

        clear_all_inventory_caches()
        reload_db()
    except (ImportError, RuntimeError, OSError) as exc:
        store.audit("publisher", "cache_refresh_deferred", job_id, {"error": type(exc).__name__})
    return {
        "job_id": job_id,
        "status": "published",
        "graph_version": version,
        "backup": str(backup),
        "validation": validation,
    }

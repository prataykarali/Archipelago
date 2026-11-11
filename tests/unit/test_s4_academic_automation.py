"""Academic reconciliation and GPU consent must fail closed."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from archipelago.academic_automation import gpu, publication, worker
from archipelago.academic_automation.candidate import enqueue_manifest
from archipelago.academic_automation.matching import match_repository
from archipelago.academic_automation.reconcile import reconcile
from archipelago.academic_automation.review import review_digest
from archipelago.academic_automation.scheduler import sync_sources
from archipelago.academic_automation.store import AcademicStore

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path: Path) -> AcademicStore:
    return AcademicStore(tmp_path / "academic.sqlite3")


def koha_record(**changes: str) -> dict[str, str]:
    row = {
        "biblionumber": "101",
        "Title": "Graph Algorithms, 2nd Edition",
        "Author": "A. Scholar",
        "isbn": "9780131103627",
        "No. of copies": "3",
        "Available Copies": "2",
    }
    row.update(changes)
    return row


def _candidate(store: AcademicStore, root: Path) -> str:
    reconcile(store, "koha_export", [koha_record()])
    folder = root / "data" / "academic_candidates"
    folder.mkdir(parents=True)
    content = folder / "open.md"
    content.write_text("Permitted academic text", encoding="utf-8")
    manifest = folder / "open.rights.json"
    manifest.write_text(
        json.dumps(
            {
                "record_key": "koha_export:101",
                "filename": content.name,
                "license": "CC-BY-4.0",
                "source_url": "https://example.edu/open.md",
                "rights_reviewed_by": "librarian",
                "sha256": sha256(content.read_bytes()).hexdigest(),
            }
        )
    )
    return enqueue_manifest(store, root, manifest)


def test_new_updated_edition_copy_count_and_idempotent_run(store: AcademicStore) -> None:
    first = reconcile(store, "koha_export", [koha_record()])
    again = reconcile(store, "koha_export", [koha_record()])
    copies = reconcile(store, "koha_export", [koha_record(**{"Available Copies": "1"})])
    edition = reconcile(store, "koha_export", [koha_record(Title="Graph Algorithms, 3rd Edition")])
    assert first["counts"] == {"new": 1}
    assert again["counts"] == {"unchanged": 1}
    assert copies["counts"] == {"changed": 1}
    assert edition["counts"] == {"changed": 1}
    with store._connect() as db:
        versions = db.execute("SELECT count(*) FROM record_versions").fetchone()[0]
        identity = db.execute("SELECT identity_key FROM records").fetchone()[0]
    assert versions == 3
    assert identity.endswith("edition:3")


def test_duplicate_isbn_and_missing_isbn_keep_provider_provenance(store: AcademicStore) -> None:
    reconcile(
        store,
        "koha_export",
        [koha_record(), koha_record(biblionumber="102", **{"Available Copies": "0"})],
    )
    reconcile(store, "koha_export", [koha_record(biblionumber="103", isbn="")])
    with store._connect() as db:
        rows = [
            tuple(row)
            for row in db.execute("SELECT record_key,identity_key FROM records ORDER BY record_key")
        ]
    assert rows[0][1] == rows[1][1]
    assert rows[2][1] == "koha:103"
    assert len({row[0] for row in rows}) == 3


def test_outage_and_missing_rows_never_withdraw(store: AcademicStore) -> None:
    reconcile(store, "koha_export", [koha_record()])
    result = sync_sources(store, {"koha_export": lambda: (_ for _ in ()).throw(OSError("offline"))})
    assert result[0]["status"] == "unavailable"
    assert reconcile(store, "koha_export", [koha_record(biblionumber="102")])["status"] == "partial"
    with store._connect() as db:
        assert db.execute("SELECT status FROM records WHERE source_id='101'").fetchone()[0] == "new"
    assert store.withdraw("koha_export:101", verified=False, actor="test") is False
    assert store.withdraw("koha_export:101", verified=True, actor="librarian") is True


def test_licensed_pearson_metadata_cannot_queue_content(store: AcademicStore) -> None:
    row = {
        "id": "pearson-1",
        "title": "Licensed Book",
        "isbn": "9780131103627",
        "subscription_id": "secret",
    }
    reconcile(store, "pearson_bookshelf", [row])
    with store._connect() as db:
        payload = json.loads(db.execute("SELECT payload FROM records").fetchone()[0])
    assert "subscription_id" not in payload
    with pytest.raises(ValueError):
        store.enqueue(
            record_key="pearson_bookshelf:pearson-1",
            rights="licensed_metadata_only",
            content_path="/tmp/book.pdf",
            content_sha256="abc",
        )


def test_open_content_manifest_is_idempotent_and_requires_rights(
    store: AcademicStore, tmp_path: Path
) -> None:
    job_id = _candidate(store, tmp_path)
    manifest = tmp_path / "data" / "academic_candidates" / "open.rights.json"
    assert enqueue_manifest(store, tmp_path, manifest) == job_id
    raw = json.loads(manifest.read_text())
    raw["license"] = "all-rights-reserved"
    manifest.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        enqueue_manifest(store, tmp_path, manifest)
    assert len(store.dashboard()["jobs"]) == 1


def test_gpu_denial_offline_defer_and_cancellation(
    store: AcademicStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _candidate(store, tmp_path)
    monkeypatch.setattr(worker, "gpu_snapshot", lambda: {"available": False})
    assert worker.run_once(store, tmp_path)["status"] == "awaiting_approval"
    assert store.job(job_id)["next_attempt_at"] is not None
    assert store.cancel(job_id, "librarian")
    assert worker.run_once(store, tmp_path) is None


def test_explicit_deny_never_starts_gpu(
    store: AcademicStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _candidate(store, tmp_path)
    monkeypatch.setattr(worker, "gpu_snapshot", lambda: {"available": True})
    monkeypatch.setattr(worker, "desktop_consent", lambda *_args, **_kwargs: "cancel")
    monkeypatch.setattr(worker, "exclusive_gpu", lambda *_args: pytest.fail("GPU started"))
    assert worker.run_once(store, tmp_path)["status"] == "cancelled"
    assert store.job(job_id)["status"] == "cancelled"


def test_cancellation_cannot_be_overwritten_by_late_progress(
    store: AcademicStore, tmp_path: Path
) -> None:
    job_id = _candidate(store, tmp_path)
    assert store.cancel(job_id, "librarian")
    with pytest.raises(RuntimeError, match="cancelled"):
        store.update_job(job_id, "running", progress={"percent": 99})
    with pytest.raises(RuntimeError, match="cancelled"):
        store.update_job(job_id, "review_ready")
    assert store.job(job_id)["status"] == "cancelled"


def test_grant_revocation_and_bounded_retry(
    store: AcademicStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _candidate(store, tmp_path)
    grant = store.grant(scope="job", job_id=job_id, actor="local_operator")
    assert store.has_grant(job_id)
    assert store.revoke(grant, "local_operator")
    assert not store.has_grant(job_id)
    assert store.retry(job_id, "first") == "awaiting_approval"
    assert store.retry(job_id, "second") == "awaiting_approval"
    assert store.retry(job_id, "third") == "dead_letter"


def test_failed_staging_is_retried_without_publication(
    store: AcademicStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _candidate(store, tmp_path)
    store.grant(scope="job", job_id=job_id, actor="local_operator")
    monkeypatch.setattr(worker, "gpu_snapshot", lambda: {"available": True})
    from contextlib import nullcontext

    monkeypatch.setattr(worker, "exclusive_gpu", lambda *_args: nullcontext())
    monkeypatch.setattr(
        worker, "stage_job", lambda *_args: (_ for _ in ()).throw(ValueError("invalid graph"))
    )
    assert worker.run_once(store, tmp_path)["status"] == "awaiting_approval"
    assert store.job(job_id)["published_version"] is None


def test_repository_match_is_metadata_only(store: AcademicStore) -> None:
    reconcile(store, "koha_export", [koha_record()])
    count = match_repository(
        store,
        [
            {
                "title": "Graph Algorithms, 2nd Edition",
                "source_url": "https://uemk.ndl.gov.in/handle/123",
            }
        ],
    )
    assert count == 1
    assert store.dashboard()["external_matches"] == 1
    with store._connect() as db:
        assert (
            db.execute("SELECT match_status FROM source_matches").fetchone()[0]
            == "metadata_only_requires_rights_review"
        )


def test_exclusive_gpu_refuses_other_models_and_shared_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "gpu.lock"
    monkeypatch.setattr(gpu, "active_model_names", lambda: {"another-model"})
    monkeypatch.setattr(gpu, "compute_processes", lambda: set())
    with pytest.raises(gpu.GPUUnavailable, match="Another Ollama model"):
        with gpu.exclusive_gpu("academic-model", lock_path=lock):
            pytest.fail("GPU started")
    monkeypatch.setattr(gpu, "active_model_names", lambda: set())
    from archipelago.ingestion.gpu_lease import shared_gpu_lease

    with shared_gpu_lease(lock):
        with pytest.raises(gpu.GPUUnavailable, match="Another Archipelago"):
            with gpu.exclusive_gpu("academic-model", lock_path=lock):
                pytest.fail("GPU started")


def _review_ready(store: AcademicStore, root: Path) -> tuple[str, Path]:
    job_id = _candidate(store, root)
    canonical = root / "okf_graph.db"
    canonical.write_bytes(b"old graph")
    job_dir = root / "data" / "academic_jobs" / job_id
    job_dir.mkdir(parents=True)
    staged = job_dir / "staging.db"
    staged.write_bytes(b"new graph")
    (job_dir / "results.json").write_text(
        json.dumps([{"doc_id": "new_doc", "chunk_id": "new_chunk", "concept_name": "New topic"}])
    )
    (root / "okf_results.json").write_text(
        json.dumps([{"doc_id": "old_doc", "chunk_id": "old_chunk", "concept_name": "Old topic"}])
    )
    store.update_job(
        job_id,
        "review_ready",
        staging_path=str(staged),
        baseline_version=sha256(canonical.read_bytes()).hexdigest(),
    )
    store.record_review(
        job_id,
        {
            "decision": "approve",
            "reviewer_id": "second_librarian",
            "reviewer_name": "second_librarian",
            "reviewer_role": "librarian",
            "review_digest": review_digest(store.job(job_id), root),
            "at": "2026-11-11T00:00:00+00:00",
            "note": "Test review",
            "concept_count": 1,
            "edge_count": 0,
        },
    )
    return job_id, canonical


def test_publication_requires_exact_human_approval(store: AcademicStore, tmp_path: Path) -> None:
    job_id, canonical = _review_ready(store, tmp_path)
    with store._connect() as db:
        db.execute("DELETE FROM human_reviews WHERE job_id=?", (job_id,))
    with pytest.raises(PermissionError, match="human approval"):
        publication.publish_reviewed(store, job_id, tmp_path, reviewer="second_librarian")
    assert canonical.read_bytes() == b"old graph"


def test_failed_publication_validation_keeps_graph(
    store: AcademicStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, canonical = _review_ready(store, tmp_path)
    import okf.graph.safe_staging as staging

    monkeypatch.setattr(
        staging, "extract_graph_inventory", lambda _path: {"concept_ids": {"old"}, "edges": []}
    )
    monkeypatch.setattr(
        staging,
        "validate_staging_against_production",
        lambda *_args: (_ for _ in ()).throw(ValueError("missing legacy node")),
    )
    with pytest.raises(ValueError, match="missing legacy"):
        publication.publish_reviewed(store, job_id, tmp_path, reviewer="second_librarian")
    assert canonical.read_bytes() == b"old graph"
    assert store.job(job_id)["status"] == "review_ready"


def test_reviewed_publication_records_backup_and_new_version(
    store: AcademicStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, canonical = _review_ready(store, tmp_path)
    import okf.graph.safe_staging as staging

    monkeypatch.setattr(
        staging, "extract_graph_inventory", lambda _path: {"concept_ids": {"old"}, "edges": []}
    )
    monkeypatch.setattr(
        staging,
        "validate_staging_against_production",
        lambda *_args: {"valid": True, "added_concepts": 1, "added_edges": 0},
    )
    backup = tmp_path / "backup.tar.gz"
    monkeypatch.setattr(staging, "create_graph_backup", lambda _path: backup)
    monkeypatch.setattr(
        staging,
        "publish_staging_graph",
        lambda _stage, production: Path(production).write_bytes(b"new graph"),
    )
    from archipelago.inference import inventory_ssot, state

    monkeypatch.setattr(inventory_ssot, "clear_all_inventory_caches", lambda: None)
    monkeypatch.setattr(state, "reload_db", lambda: None)
    result = publication.publish_reviewed(store, job_id, tmp_path, reviewer="second_librarian")
    assert result["status"] == "published"
    assert canonical.read_bytes() == b"new graph"
    assert store.job(job_id)["publication_backup"] == str(backup)
    assert {row["doc_id"] for row in json.loads((tmp_path / "okf_results.json").read_text())} == {
        "old_doc",
        "new_doc",
    }


def test_failed_result_write_rolls_back_graph_and_results(
    store: AcademicStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, canonical = _review_ready(store, tmp_path)
    import okf.graph.merge_document as merge_document
    import okf.graph.safe_staging as staging

    monkeypatch.setattr(
        staging, "extract_graph_inventory", lambda _path: {"concept_ids": {"old"}, "edges": []}
    )
    monkeypatch.setattr(staging, "validate_staging_against_production", lambda *_args: {})
    monkeypatch.setattr(staging, "create_graph_backup", lambda _path: tmp_path / "backup")
    monkeypatch.setattr(
        staging,
        "publish_staging_graph",
        lambda _stage, production: Path(production).write_bytes(b"new graph"),
    )
    monkeypatch.setattr(
        staging,
        "rollback_from_backup",
        lambda _backup, production: Path(production).write_bytes(b"old graph"),
    )
    monkeypatch.setattr(
        merge_document,
        "write_okf_results_atomic",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError, match="disk full"):
        publication.publish_reviewed(store, job_id, tmp_path, reviewer="second_librarian")
    assert canonical.read_bytes() == b"old graph"
    assert json.loads((tmp_path / "okf_results.json").read_text())[0]["doc_id"] == "old_doc"
    assert store.job(job_id)["status"] == "publication_failed"

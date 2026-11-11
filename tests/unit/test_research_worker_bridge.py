"""Queue handoff and staff result-access checks."""

from __future__ import annotations

from types import SimpleNamespace
import uuid

from flask import Flask, request
import pytest
import requests

from archipelago.scholarly.bridge import cli, processor, supabase_store
from archipelago.scholarly.contracts.okf_models import PaperIdentifiers, PaperRecord
from host_inference.hostapp.routes import research_jobs

pytestmark = pytest.mark.unit


def test_queue_request_retries_a_transient_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dropped HTTP connection must not fail an approved ingestion job."""
    attempts = 0

    class Response:
        status_code = 200
        content = b'[{"status":"ready"}]'

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, str]]:
            return [{"status": "ready"}]

    def request_once_dropped(*_args: object, **_kwargs: object) -> Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise requests.ConnectionError("temporary disconnect")
        return Response()

    monkeypatch.setattr(supabase_store.requests, "request", request_once_dropped)
    monkeypatch.setattr(supabase_store.time, "sleep", lambda _seconds: None)
    store = supabase_store.ResearchQueueStore("https://example.supabase.co", "test-key")
    assert store._request("GET", "research_processing_jobs") == [{"status": "ready"}]
    assert attempts == 2


def test_worker_claims_and_finishes_one_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful local run claims exactly one queued request."""
    monkeypatch.setenv("DISPLAY", ":1")
    events: list[str] = []

    class Store:
        def recover_stale_jobs(self) -> int:
            events.append("recover")
            return 0

        def heartbeat(self, *_args: object) -> None:
            events.append("heartbeat")

        def claim_next(self, _worker_id: str) -> dict[str, str]:
            events.append("claim")
            return {"job_id": "job-one", "topic": "graph retrieval"}

        def update_job(self, _job_id: str, **_fields: object) -> None:
            events.append("update")

    monkeypatch.setattr(
        cli,
        "process_job",
        lambda _store, _job, _worker: {"job_id": "job-one", "status": "completed"},
    )
    monkeypatch.setattr(cli, "_approve_gpu_request", lambda _topic: True)
    monkeypatch.setattr(cli, "_model_ready", lambda: True)
    result = cli.run_once(Store(), "worker-one")  # type: ignore[arg-type]
    assert result == {"job_id": "job-one", "status": "completed"}
    assert events == ["recover", "heartbeat", "claim", "update", "heartbeat", "heartbeat"]


def test_worker_decline_never_starts_gpu_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """A local cross click stops processing and records an honest failed status."""
    monkeypatch.setenv("DISPLAY", ":1")
    updates: list[dict[str, object]] = []

    class Store:
        def recover_stale_jobs(self) -> int:
            return 0

        def heartbeat(self, *_args: object) -> None:
            return None

        def claim_next(self, _worker_id: str) -> dict[str, str]:
            return {"job_id": "job-one", "topic": "graph retrieval"}

        def update_job(self, _job_id: str, **fields: object) -> None:
            updates.append(fields)

    monkeypatch.setattr(cli, "_approve_gpu_request", lambda _topic: False)
    monkeypatch.setattr(cli, "_model_ready", lambda: True)
    monkeypatch.setattr(
        cli, "process_job", lambda *_args: pytest.fail("Declined job must not use GPU")
    )
    assert cli.run_once(Store(), "worker-one") == {"job_id": "job-one", "status": "failed"}  # type: ignore[arg-type]
    assert updates[-1]["stage"] == "LOCAL_APPROVAL_DECLINED"


def test_worker_does_not_claim_job_without_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Ollama tags keep queued user work safe for a later retry."""
    monkeypatch.setenv("DISPLAY", ":1")
    states: list[str] = []

    class Store:
        def recover_stale_jobs(self) -> int:
            return 0

        def heartbeat(self, _worker_id: str, status: str, _count: int) -> None:
            states.append(status)

        def claim_next(self, _worker_id: str) -> None:
            pytest.fail("A missing model must not claim hosted work")

    monkeypatch.setattr(cli, "_model_ready", lambda: False)
    assert cli.run_once(Store(), "worker-one") is None  # type: ignore[arg-type]
    assert states == [f"model_unavailable:{cli.ingestion_model_name()}"]


def test_worker_does_not_claim_without_desktop(monkeypatch: pytest.MonkeyPatch) -> None:
    """A headless boot must leave queued work waiting for the approval prompt."""
    states: list[str] = []

    class Store:
        def recover_stale_jobs(self) -> int:
            return 0

        def heartbeat(self, _worker_id: str, status: str, _count: int) -> None:
            states.append(status)

        def claim_next(self, _worker_id: str) -> None:
            pytest.fail("Headless worker must not claim a job")

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert cli.run_once(Store(), "worker-one") is None  # type: ignore[arg-type]
    assert states == ["desktop_approval_unavailable"]


def test_desktop_approval_uses_explicit_tick_and_cross(monkeypatch: pytest.MonkeyPatch) -> None:
    """The local workstation must require an affirmative GUI response."""
    commands: list[list[str]] = []
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda args, **_kwargs: commands.append(args) or SimpleNamespace(returncode=1),
    )
    assert cli._approve_gpu_request("graph retrieval") is False
    assert commands[0][0:2] == ["zenity", "--question"]
    assert "--ok-label=✓ Approve ingestion" in commands[0]
    assert "--cancel-label=✕ Decline" in commands[0]


def test_research_job_rejects_unlicensed_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """A paper without verified reuse rights stays metadata only."""
    paper = PaperRecord(
        title="A verified research paper",
        abstract="A test abstract describing database consistency.",
        identifiers=PaperIdentifiers(doi="10.1000/research-test"),
        is_open_access=True,
    )
    item = {"paper": paper, "source": "crossref", "pdf_url": "https://example.org/paper.pdf"}
    monkeypatch.setattr(
        processor,
        "discover_ranked_papers",
        lambda _topic, _limit: (
            [item],
            [{"source": "crossref", "status": "live"}],
            "gpu_embeddings",
            {"peak_allocated_mib": 512},
        ),
    )
    monkeypatch.setattr(processor, "extract_abstract_fields", lambda _abstract: [])

    class Store:
        def __init__(self) -> None:
            self.records: list[dict] = []
            self.results: list[dict] = []
            self.updates: list[dict] = []

        def update_job(self, _job_id: str, **_fields: object) -> None:
            self.updates.append(_fields)

        def save_intake_record(self, row: dict) -> None:
            self.records.append(row)

        def save_result(self, row: dict) -> None:
            self.results.append(row)

        def heartbeat(self, *_args: object) -> None:
            pass

    store = Store()
    result = processor.process_job(
        store,  # type: ignore[arg-type]
        {
            "job_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "topic": "database consistency",
            "paper_limit": 20,
        },
        "worker-one",
    )
    assert result["fulltext"] == 0
    assert store.results[0]["access_state"] == "METADATA_ONLY"
    assert store.records[0]["source_url"] == "https://doi.org/10.1000/research-test"
    summary = store.updates[-1]["result_summary"]
    assert summary["ingestion_model"] == processor.ingestion_model_name()
    assert summary["abstracts_attempted"] == 1
    assert summary["abstract_extraction_errors"] == 0


def test_hosted_job_create_validates_and_enqueues(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only a bounded staff paper request reaches the database function."""
    app = Flask(__name__)
    job_id = str(uuid.uuid4())
    calls: list[tuple[str, str, str, int]] = []

    @app.before_request
    def principal() -> None:
        request.archipelago_principal = {  # type: ignore[attr-defined]
            "id": str(uuid.uuid4()),
            "role": "faculty",
        }

    monkeypatch.setattr(
        research_jobs,
        "enqueue_job",
        lambda user, role, topic, count: (
            calls.append((user, role, topic, count)) or {"job_id": job_id, "status": "queued"}
        ),
    )
    monkeypatch.setattr(research_jobs, "worker_status", lambda: {"online": False})
    monkeypatch.setattr(research_jobs, "audit_action", lambda **_kwargs: None)
    research_jobs.register(app, SimpleNamespace())  # type: ignore[arg-type]
    client = app.test_client()
    assert (
        client.post("/api/research/jobs", json={"topic": "AI", "paper_limit": 25}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/research/jobs",
            json={"topic": "graph retrieval", "paper_limit": research_jobs.MAX_PAPERS + 1},
        ).status_code
        == 400
    )
    response = client.post("/api/research/jobs", json={"topic": "graph retrieval"})
    assert response.status_code == 202
    assert response.json["job"]["job_id"] == job_id
    assert calls[0][1:] == ("faculty", "graph retrieval", 25)


def test_hosted_job_rejects_full_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Vercel endpoint exposes the database's global capacity gate."""
    app = Flask(__name__)

    @app.before_request
    def principal() -> None:
        request.archipelago_principal = {  # type: ignore[attr-defined]
            "id": str(uuid.uuid4()),
            "role": "librarian",
        }

    def full_queue(*_args: object) -> None:
        raise ValueError("research_queue_full")

    monkeypatch.setattr(research_jobs, "enqueue_job", full_queue)
    research_jobs.register(app, SimpleNamespace())  # type: ignore[arg-type]
    response = app.test_client().post(
        "/api/research/jobs", json={"topic": "pedestrian detection", "paper_limit": 25}
    )
    assert response.status_code == 503
    assert response.json["error"] == "research_queue_full"


def test_hosted_job_results_hide_another_faculty_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """Staff can read their own jobs; managers can inspect queue results."""
    app = Flask(__name__)
    job_id = str(uuid.uuid4())
    principal = {"id": str(uuid.uuid4()), "role": "faculty"}

    @app.before_request
    def attach_principal() -> None:
        request.archipelago_principal = principal  # type: ignore[attr-defined]

    monkeypatch.setattr(
        research_jobs, "get_job", lambda _job_id: {"job_id": job_id, "user_id": "other"}
    )
    monkeypatch.setattr(research_jobs, "worker_status", lambda: {"online": True})
    research_jobs.register(app, SimpleNamespace())  # type: ignore[arg-type]
    client = app.test_client()
    assert client.get(f"/api/research/jobs/{job_id}").status_code == 404
    principal["role"] = "librarian"
    assert client.get(f"/api/research/jobs/{job_id}").status_code == 200


def test_latest_job_is_library_wide_for_managers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Managers inspect the last ingestion session; faculty see only their own."""
    app = Flask(__name__)
    principal = {"id": str(uuid.uuid4()), "role": "faculty"}
    requested_users: list[str | None] = []

    @app.before_request
    def attach_principal() -> None:
        request.archipelago_principal = principal  # type: ignore[attr-defined]

    monkeypatch.setattr(
        research_jobs,
        "latest_job",
        lambda user_id: requested_users.append(user_id) or None,
    )
    monkeypatch.setattr(research_jobs, "worker_status", lambda: {"online": True})
    research_jobs.register(app, SimpleNamespace())  # type: ignore[arg-type]
    client = app.test_client()
    assert client.get("/api/research/jobs/latest").status_code == 200
    principal["role"] = "librarian"
    assert client.get("/api/research/jobs/latest").status_code == 200
    assert requested_users == [principal["id"], None]


def test_complete_session_export_respects_job_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """Full OKF export is available to managers and the job owner only."""
    app = Flask(__name__)
    job_id = str(uuid.uuid4())
    principal = {"id": str(uuid.uuid4()), "role": "faculty"}

    @app.before_request
    def attach_principal() -> None:
        request.archipelago_principal = principal  # type: ignore[attr-defined]

    monkeypatch.setattr(
        research_jobs, "get_job", lambda _id: {"job_id": job_id, "user_id": "other"}
    )
    monkeypatch.setattr(
        research_jobs,
        "list_job_okf",
        lambda _id: [{"title": "Verified paper", "okf": {"okf_version": "2.0.0"}}],
    )
    research_jobs.register(app, SimpleNamespace())  # type: ignore[arg-type]
    client = app.test_client()
    assert client.get(f"/api/research/jobs/{job_id}/export").status_code == 404
    principal["role"] = "librarian"
    response = client.get(f"/api/research/jobs/{job_id}/export")
    assert response.status_code == 200
    assert response.json["paper_count"] == 1
    assert response.json["papers"][0]["okf"]["okf_version"] == "2.0.0"

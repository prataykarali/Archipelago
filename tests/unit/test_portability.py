"""Feature regression — Docker portability, health probes, and config paths.

Covers the operational layer: that nothing depends on a developer's machine,
that health probes report honestly, and that the appliance's entrypoints are
real modules rather than inline shell.

The portability assertions here are the ones that actually bit: a hardcoded
`/home/<someone>/…` model path made the container fall back to a default model
whenever the real model was mounted elsewhere, and that is invisible until
ingestion quietly produces nothing.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(REPO_ROOT),):
    if _path not in sys.path:
        sys.path.insert(0, _path)

pytestmark = pytest.mark.unit

COMPOSE = REPO_ROOT / "deploy" / "library-computer" / "docker-compose.yml"


# ─── No developer-machine paths in production config ────────────────────────


@pytest.mark.parametrize(
    "relative",
    [
        "okf/config.py",
        "okf/graph/common.py",
        "archipelago/config.py",
        "ingestion_worker.py",
        "ingestion_worker_job_mixin.py",
        "scripts/worker_health.py",
        "scripts/run_ingestion_worker.py",
        "scripts/run_sync_service.py",
    ],
)
def test_no_hardcoded_home_paths(relative):
    """An absolute developer path silently breaks the Docker appliance."""
    source = (REPO_ROOT / relative).read_text(encoding="utf-8")
    for marker in ("/home/", "/Users/", "Desktop/libraryAI"):
        assert marker not in source, f"{relative} contains a machine-specific path: {marker}"


def test_model_resolution_prefers_the_explicit_env(monkeypatch, tmp_path):
    import importlib

    import okf.config as config

    monkeypatch.setenv("OKF_LOCAL_MODEL", str(tmp_path / "explicit"))
    reloaded = importlib.reload(config)
    assert reloaded.resolve_local_model_path() == tmp_path / "explicit"


def test_model_resolution_finds_the_in_repo_directory(monkeypatch):
    """The container layout: models/<name> under the repo, no host paths."""
    import importlib

    import okf.config as config

    monkeypatch.delenv("OKF_LOCAL_MODEL", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_MODEL_ROOTS", raising=False)
    reloaded = importlib.reload(config)
    resolved = reloaded.resolve_local_model_path()
    assert REPO_ROOT in resolved.parents
    assert resolved.name in reloaded.LOCAL_MODEL_NAMES


def test_model_resolution_honours_external_roots(monkeypatch, tmp_path):
    """An operator's model on a separate volume must be found."""
    from okf.config import resolve_local_model_path

    root = tmp_path / "elsewhere"
    (root / "aura-qwen").mkdir(parents=True)
    monkeypatch.delenv("OKF_LOCAL_MODEL", raising=False)
    # The in-repo model also exists and is searched first, so point the search
    # at a temp BASE_DIR to isolate the external-root branch.
    monkeypatch.setattr("okf.config.BASE_DIR", tmp_path)
    monkeypatch.setenv("ARCHIPELAGO_MODEL_ROOTS", str(root))
    assert resolve_local_model_path() == root / "aura-qwen"


def test_model_resolution_returns_a_repo_relative_path_when_absent(monkeypatch, tmp_path):
    """The fallback must name a real in-repo location, not a stale absolute one."""
    from okf.config import resolve_local_model_path

    monkeypatch.delenv("OKF_LOCAL_MODEL", raising=False)
    monkeypatch.setenv("ARCHIPELAGO_MODEL_ROOTS", str(tmp_path / "empty"))
    monkeypatch.setattr("okf.config.BASE_DIR", tmp_path)
    resolved = resolve_local_model_path()
    assert str(resolved).startswith(str(tmp_path))


def test_shipped_model_directory_is_discoverable():
    """The repo ships a fine-tune; the resolver must actually find it."""
    import importlib

    import okf.config as config

    importlib.reload(config)
    resolved = config.resolve_local_model_path()
    assert resolved.exists(), f"resolved model path does not exist: {resolved}"


# ─── Compose contract ───────────────────────────────────────────────────────


def _compose() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_compose_parses_and_declares_the_expected_services():
    services = _compose()["services"]
    assert set(services) == {
        "ollama",
        "archipelago-ingestion",
        "archipelago-graph",
        "archipelago-sync",
    }


def test_every_service_has_a_healthcheck():
    """Without one, `depends_on` degenerates to start-order and races resume."""
    for name, service in _compose()["services"].items():
        assert service.get("healthcheck"), f"{name} has no healthcheck"


def test_dependents_wait_on_health_not_just_start_order():
    services = _compose()["services"]
    ingestion = services["archipelago-ingestion"]["depends_on"]["ollama"]
    assert ingestion["condition"] == "service_healthy"
    graph = services["archipelago-graph"]["depends_on"]["archipelago-ingestion"]
    assert graph["condition"] == "service_healthy"


def test_no_inline_python_commands_in_compose():
    """Inline `python -c` cannot be linted, tested, or health-checked.

    Comments may still mention the pattern; only real service definitions are
    checked.
    """
    body = "\n".join(
        line for line in COMPOSE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "python -c" not in body


def test_ingestion_uses_a_real_entrypoint_module():
    service = _compose()["services"]["archipelago-ingestion"]
    entrypoint = " ".join(service.get("entrypoint") or [])
    assert entrypoint, "ingestion must use a script entrypoint"
    assert (REPO_ROOT / "scripts" / "run_ingestion_worker.py").is_file()


def test_sync_uses_a_real_entrypoint_module():
    service = _compose()["services"]["archipelago-sync"]
    entrypoint = " ".join(service.get("entrypoint") or [])
    assert entrypoint
    assert (REPO_ROOT / "scripts" / "run_sync_service.py").is_file()


def test_model_is_bind_mounted_not_a_named_volume():
    """A named volume starts empty, so the model mount would silently shadow."""
    volumes = _compose()["volumes"] or {}
    assert "models" not in volumes, "models must not be a named volume"
    mounts = " ".join(_compose()["services"]["archipelago-ingestion"]["volumes"])
    assert "ARCHIPELAGO_MODEL_DIR" in mounts


def test_state_directory_is_a_bind_mount():
    """Which sources were withdrawn must survive `docker compose down`."""
    volumes = _compose()["volumes"] or {}
    assert "state" not in volumes
    mounts = " ".join(_compose()["services"]["archipelago-ingestion"]["volumes"])
    assert "ARCHIPELAGO_STATE_DIR" in mounts


def test_state_dir_env_points_at_the_container_root():
    env = _compose()["services"]["archipelago-ingestion"]["environment"]
    assert env["ARCHIPELAGO_STATE_DIR"] == "/app"


def test_ollama_host_is_the_sibling_service():
    env = _compose()["services"]["archipelago-ingestion"]["environment"]
    assert env["ARCHIPELAGO_OLLAMA_HOST"] == "http://ollama:11434"


def test_fetch_allowlist_is_not_preconfigured_in_compose():
    """The gate is default-deny; compose must not smuggle hosts in."""
    text = COMPOSE.read_text(encoding="utf-8")
    assert "ARCHIPELAGO_FETCH_ALLOWLIST=" not in text


# ─── Health probes ──────────────────────────────────────────────────────────


def test_liveness_passes_for_a_writable_jobs_dir(tmp_path):
    from scripts.worker_health import liveness

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    payload = liveness(jobs)
    assert payload["healthy"] is True
    assert payload["status"] == "ok"


def test_liveness_fails_for_a_missing_jobs_dir(tmp_path):
    from scripts.worker_health import liveness

    payload = liveness(tmp_path / "absent")
    assert payload["healthy"] is False
    assert "missing" in payload["reason"]


def test_liveness_fails_when_the_jobs_path_is_a_file(tmp_path):
    from scripts.worker_health import liveness

    path = tmp_path / "jobs"
    path.write_text("not a directory", encoding="utf-8")
    assert liveness(path)["healthy"] is False


def test_liveness_probe_does_not_leave_a_file_behind(tmp_path):
    from scripts.worker_health import liveness

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    liveness(jobs)
    assert list(jobs.iterdir()) == []


def test_readiness_is_healthy_but_not_ready_without_a_model(tmp_path, monkeypatch):
    """A missing model must read as degraded, never crash or restart-loop."""
    from scripts import worker_health

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    monkeypatch.setattr(
        worker_health, "_model_reachable", lambda model: (False, "no client")
    )
    payload = worker_health.readiness(jobs)
    assert payload["healthy"] is True
    assert payload["ready"] is False
    assert payload["status"] == "degraded"


def test_readiness_is_ready_when_the_model_is_reachable(tmp_path, monkeypatch):
    from scripts import worker_health

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    monkeypatch.setattr(worker_health, "_model_reachable", lambda model: (True, "ok"))
    payload = worker_health.readiness(jobs)
    assert payload["ready"] is True
    assert payload["status"] == "ready"


def test_readiness_fails_when_liveness_fails(tmp_path, monkeypatch):
    from scripts import worker_health

    monkeypatch.setattr(
        worker_health, "_model_reachable", lambda model: (True, "ok")
    )
    assert worker_health.readiness(tmp_path / "absent")["healthy"] is False


def test_model_probe_never_raises():
    from scripts.worker_health import _model_reachable

    reachable, detail = _model_reachable("definitely-not-a-real-model")
    assert isinstance(reachable, bool)
    assert isinstance(detail, str)


def test_health_cli_exits_zero_when_healthy(tmp_path, capsys):
    from scripts.worker_health import main

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    assert main(["liveness", str(jobs)]) == 0
    assert json.loads(capsys.readouterr().out)["healthy"] is True


def test_health_cli_exits_nonzero_when_unhealthy(tmp_path):
    from scripts.worker_health import main

    assert main(["liveness", str(tmp_path / "absent")]) == 1


def test_health_cli_rejects_an_unknown_mode():
    from scripts.worker_health import main

    assert main(["sideways"]) == 2


def test_health_probe_imports_from_any_cwd(tmp_path):
    """The compose healthcheck runs with WORKDIR=/app, not the repo root."""
    import subprocess

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "worker_health.py"), "liveness", str(jobs)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["healthy"] is True


# ─── Sync service ───────────────────────────────────────────────────────────


def test_graph_stats_reads_the_export(tmp_path):
    from scripts.run_sync_service import graph_stats

    export = tmp_path / "okf_graph.json"
    export.write_text(
        json.dumps({"stats": {"total_concepts": 5, "total_edges": 3}}), encoding="utf-8"
    )
    assert graph_stats(export) == {
        "node_count": 5,
        "edge_count": 3,
        "document_count": 0,
    }


def test_graph_stats_falls_back_to_visualization_counts(tmp_path):
    from scripts.run_sync_service import graph_stats

    export = tmp_path / "okf_graph.json"
    export.write_text(
        json.dumps(
            {"visualization": {"nodes": [1, 2, 3], "edges": [1]}}
        ),
        encoding="utf-8",
    )
    assert graph_stats(export)["node_count"] == 3
    assert graph_stats(export)["edge_count"] == 1


def test_graph_stats_of_a_missing_file_is_zeros_not_an_error(tmp_path):
    from scripts.run_sync_service import graph_stats

    assert graph_stats(tmp_path / "absent.json")["node_count"] == 0


def test_graph_stats_of_a_corrupt_file_is_zeros(tmp_path):
    from scripts.run_sync_service import graph_stats

    export = tmp_path / "okf_graph.json"
    export.write_text("{ truncated", encoding="utf-8")
    assert graph_stats(export)["node_count"] == 0


def test_sync_refuses_a_non_http_api_url():
    from scripts.run_sync_service import push_once

    result = push_once("file:///etc/passwd")
    assert result["ok"] is False
    assert "scheme" in result["reason"]


def test_sync_without_an_api_is_a_clean_no_op():
    from scripts.run_sync_service import push_once

    result = push_once("")
    assert result["ok"] is False
    assert "ARCHIPELAGO_INFERENCE_URL" in result["reason"]


# ─── Entrypoint modules are importable ──────────────────────────────────────


@pytest.mark.parametrize(
    "relative",
    ["scripts/worker_health.py", "scripts/run_sync_service.py"],
)
def test_entrypoint_modules_import_cleanly(relative):
    import importlib.util

    path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    assert hasattr(module, "main")


def test_worker_entrypoint_defines_signal_handling():
    source = (REPO_ROOT / "scripts" / "run_ingestion_worker.py").read_text(
        encoding="utf-8"
    )
    assert "SIGTERM" in source, "the container must shut down cleanly"
    assert "install_log_redaction" in source, "worker logs must be redacted"


def test_worker_entrypoint_puts_the_repo_on_sys_path():
    source = (REPO_ROOT / "scripts" / "run_ingestion_worker.py").read_text(
        encoding="utf-8"
    )
    assert "sys.path.insert" in source

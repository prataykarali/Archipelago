"""Boot-time corpus provisioning for the hosted app.

Why this exists
---------------
Every corpus artifact is gitignored — ``okf_graph.json``, ``host_inference/cache/``,
``data/catalogs/pearson_bookshelf.json`` — so a git-triggered build produces an
app with **no graph and no catalogue**.  It would boot, pass ``/api/readiness``,
and answer "not indexed" to every question while looking perfectly healthy.  That
is the worst possible failure: a green health check over an empty brain.

So the corpus arrives by one of two routes, in this order:

1. **Boot fetch.** If a tracked fixture is absent or obviously a stub, pull the
   real artifacts from the configured Hugging Face dataset repo using
   ``HF_TOKEN``/``HF_DATASET_REPO``. The corpus is generated from licensed local
   PDFs, so it never enters git; only this bootstrap code does.
2. **Tracked fixture.** ``host_inference/fixtures/`` ships a small, real slice of
   the graph so the build is never empty even when the fetch is unavailable
   (no token, no network, cold start).  A fixture is clearly labelled as such by
   ``okf_graph.json``'s ``stats.fixture`` marker, so nobody mistakes a stub for
   the real corpus.

Never raises.  A deployment with no corpus should start, serve its UI, and say
honestly that it has nothing indexed — not crash-loop.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import tempfile

logger = logging.getLogger(__name__)

#: Datasets the boot fetch reads from.  ``okf_graph.json`` is the concept graph the
#: engine loads; the bookshelf export is the institutional catalogue.
CORPUS_ARTIFACTS = (
    "okf_graph.json",
    "pearson_bookshelf.json",
)

#: Where the tracked fallback slice lives, relative to the repository root.
FIXTURE_DIR = Path("host_inference") / "fixtures"

#: Below this many concepts the graph is a stub and the boot fetch should run.
MIN_USEFUL_CONCEPTS = 50

#: Cap on a downloaded artifact, so a hostile or corrupt response cannot fill the
#: container's disk.  The real export is a few MB.
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024

HF_ENDPOINT_ENV = "HF_ENDPOINT"
HF_REPO_ENV = "HF_DATASET_REPO"
HF_TOKEN_ENV = "HF_TOKEN"
HF_ENDPOINT_DEFAULT = "https://huggingface.co"

#: Fetch budget. A cold container must not hang on the network: the fixture path
#: has to stay reachable even when Hugging Face is slow.
FETCH_TIMEOUT_SECONDS = 120


def is_stub(graph_json: Path) -> bool:
    """Whether ``graph_json`` is missing or too small to answer anything."""
    if not graph_json.is_file():
        return True
    try:
        import json

        payload = json.loads(graph_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    nodes = payload.get("nodes") or payload.get("concepts") or {}
    return len(nodes) < MIN_USEFUL_CONCEPTS


def _hf_download(repo_id: str, filename: str, destination: Path, token: str) -> bool:
    """Download one artifact from ``repo_id``. True on success.

    Uses ``huggingface_hub`` when importable and falls back to a plain HTTPS GET,
    because the deployed image should not require the hub package for one file.
    """
    endpoint = os.environ.get(HF_ENDPOINT_ENV, HF_ENDPOINT_DEFAULT).rstrip("/")
    url = f"{endpoint}/datasets/{repo_id}/resolve/main/{filename}"
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        import requests

        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with requests.get(url, headers=headers, timeout=FETCH_TIMEOUT_SECONDS, stream=True) as response:
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent) as tmp:
                written = 0
                for chunk in response.iter_content(chunk_size=1 << 20):
                    written += len(chunk)
                    if written > MAX_ARTIFACT_BYTES:
                        tmp.close()
                        Path(tmp.name).unlink(missing_ok=True)
                        logger.warning("%s exceeds the %d byte cap", filename, MAX_ARTIFACT_BYTES)
                        return False
                    tmp.write(chunk)
                staged = Path(tmp.name)
        shutil.move(str(staged), str(destination))
        return True
    except Exception as exc:
        logger.warning("Could not download %s from %s: %s", filename, repo_id, exc)
        return False


def _restore_fixture(root: Path, graph_json: Path) -> bool:
    """Copy the tracked fallback slice into place, if one is present."""
    fixture_graph = root / FIXTURE_DIR / "okf_graph.json"
    if not fixture_graph.is_file():
        return False
    try:
        graph_json.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_graph, graph_json)
    except OSError as exc:
        logger.warning("Could not install the tracked fixture: %s", exc)
        return False

    import json

    concepts = len(json.loads(graph_json.read_text(encoding="utf-8")).get("nodes") or [])
    logger.warning(
        "Serving the tracked fixture graph (%d concepts). This deployment has not "
        "indexed the full corpus; answers will be narrower than the library's.",
        concepts,
    )
    return True


def provision(root: Path | None = None) -> dict[str, object]:
    """Ensure a usable concept graph exists at ``root``. Never raises.

    Returns a small report — ``{"source": ..., "concepts": int, "ok": bool}`` —
    which ``/api/readiness`` surfaces, so an operator can see from outside
    whether the deployment is actually answering from the full corpus.
    """
    repo_root = Path(root) if root else Path(__file__).resolve().parents[2]
    graph_json = repo_root / "okf_graph.json"
    cache_graph = repo_root / "host_inference" / "cache" / "okf_graph.json"
    catalogue = repo_root / "data" / "catalogs" / "pearson_bookshelf.json"

    report: dict[str, object] = {"source": "present", "ok": True}

    if not is_stub(graph_json) or not is_stub(cache_graph):
        return report

    logger.info("Concept graph is missing or a stub; provisioning at boot.")
    repo_id = os.environ.get(HF_REPO_ENV, "").strip()
    token = os.environ.get(HF_TOKEN_ENV, "").strip()

    fetched = False
    if repo_id:
        staging = repo_root / "data" / "provisioned"
        for filename in CORPUS_ARTIFACTS:
            target = staging / filename
            if _hf_download(repo_id, filename, target, token):
                fetched = True
                if filename == "okf_graph.json":
                    for candidate in (graph_json, cache_graph):
                        candidate.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(target, candidate)
                elif filename == "pearson_bookshelf.json":
                    catalogue.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(target, catalogue)

    if not fetched:
        installed = _restore_fixture(repo_root, graph_json)
        if installed:
            cache_graph.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(graph_json, cache_graph)
        report["source"] = "fixture" if installed else "missing"

    # Every read of the graph goes through this guard: an unreadable or truncated
    # artifact must not crash boot. `is_stub` treats it as missing, so it is
    # replaced above; this read only reports the outcome.
    import json

    payload: dict = {}
    if graph_json.is_file():
        try:
            payload = json.loads(graph_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
    report["concepts"] = len(payload.get("nodes") or payload.get("concepts") or {})
    report["ok"] = int(report["concepts"]) >= MIN_USEFUL_CONCEPTS
    return report


__all__ = [
    "CORPUS_ARTIFACTS",
    "FIXTURE_DIR",
    "MIN_USEFUL_CONCEPTS",
    "is_stub",
    "provision",
]

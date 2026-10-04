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

#: Where each corpus artifact lives inside the Hugging Face dataset repo, mapped
#: to where it has to land on disk.  ``okf_graph.json`` is the concept graph the
#: engine loads; the bookshelf export is the institutional catalogue.
#:
#: Paths are the real layout of Prataykarali/Library_books.  Guessing here is how
#: a deploy silently ends up on the 84-concept fixture while the log says the
#: fetch "succeeded".
CORPUS_ARTIFACTS: dict[str, str] = {
    "okf_graph.json": "okf_graph.json",
    "catalogs/pearson_bookshelf.json": "data/catalogs/pearson_bookshelf.json",
    "library_manifest.json": "library_manifest.json",
}

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
    if not isinstance(payload, dict):
        return True
    nodes = payload.get("nodes") or payload.get("concepts") or {}
    return bool(payload.get("stats", {}).get("fixture")) or len(nodes) < MIN_USEFUL_CONCEPTS


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

    report: dict[str, object] = {"source": "present", "ok": True, "restored": [], "missing": []}
    repo_id = os.environ.get(HF_REPO_ENV, "").strip()
    token = os.environ.get(HF_TOKEN_ENV, "").strip()
    staging = repo_root / "data" / "provisioned"
    graph_needs_restore = is_stub(graph_json) and is_stub(cache_graph)

    for remote_path, local_path in CORPUS_ARTIFACTS.items():
        destination = repo_root / local_path
        cache_copy = repo_root / "host_inference" / "cache" / destination.name
        needed = graph_needs_restore if local_path == "okf_graph.json" else not (
            _valid_artifact(destination, local_path) or _valid_artifact(cache_copy, local_path)
        )
        if not needed:
            continue
        target = staging / remote_path
        if repo_id and _hf_download(repo_id, remote_path, target, token) and _valid_artifact(target, local_path):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, destination)
            cache_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, cache_copy)
            report["restored"].append(local_path)
        else:
            report["missing"].append(local_path)

    # Never overwrite a real graph just because the catalogue failed to fetch.
    if (not _valid_artifact(graph_json, "okf_graph.json")
        and not _valid_artifact(cache_graph, "okf_graph.json")
        and _restore_fixture(repo_root, graph_json)):
        cache_graph.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(graph_json, cache_graph)

    import json

    payload: dict = {}
    for candidate in (cache_graph, graph_json):
        if _valid_artifact(candidate, "okf_graph.json"):
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            break
    report["concepts"] = len(payload.get("nodes") or payload.get("concepts") or {})
    report["source"] = "fixture" if payload.get("stats", {}).get("fixture") else (
        "downloaded" if report["restored"] else "present" if payload else "missing"
    )
    report["ok"] = bool(payload) and not bool(report["missing"]) and report["source"] != "fixture"
    return report


def _valid_artifact(path: Path, local_path: str) -> bool:
    """Reject HTML/error responses and malformed exports before replacing local data."""
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    if local_path == "okf_graph.json":
        return bool(payload.get("nodes") or payload.get("concepts"))
    if local_path.endswith("pearson_bookshelf.json"):
        books = payload.get("books")
        return isinstance(books, list) and bool(books) and all(
            isinstance(book, dict) and book.get("id") and book.get("title") for book in books
        )
    paths = payload.get("hf_paths")
    return isinstance(paths, list) and all(isinstance(item, str) and item.endswith(".pdf") for item in paths)


__all__ = [
    "CORPUS_ARTIFACTS",
    "FIXTURE_DIR",
    "MIN_USEFUL_CONCEPTS",
    "is_stub",
    "provision",
]

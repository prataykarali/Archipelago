"""Fail closed before replacing the live hosted app with a narrower corpus."""
from __future__ import annotations

import json
from pathlib import Path

from hostapp.factory import build_context, create_app
from hostapp.log_redaction import install_log_redaction

RELEASE_FILE = Path(__file__).resolve().parent / "release.json"
REQUIRED_ARTIFACTS = (
    "okf_graph.json", "pearson_bookshelf.json", "library_manifest.json",
)


def validate_release_context(context, release: dict) -> None:
    """Require the existing remote corpus and catalogue before accepting traffic."""
    if context.engine.cache_info.get("source") != "supabase":
        raise RuntimeError("Release blocked: the configured corpus source is unavailable.")
    graph = context.engine.graph
    if getattr(graph, "corpus_source", "") != "full":
        raise RuntimeError("Release blocked: fixture data cannot replace the live corpus.")
    if len(graph.nodes) < release["minimum_concepts"]:
        raise RuntimeError("Release blocked: the concept corpus is smaller than the live baseline.")
    if len(context.engine.books) < release["minimum_pearson_books"]:
        raise RuntimeError("Release blocked: the catalogue is smaller than the live baseline.")
    cache = Path(context.engine.cache_info["cache"])
    for name in REQUIRED_ARTIFACTS:
        payload = json.loads((cache / name).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload:
            raise RuntimeError("Release blocked: a required corpus artifact is invalid.")
    manifest = json.loads((cache / "library_manifest.json").read_text(encoding="utf-8"))
    paths = manifest.get("hf_paths")
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise RuntimeError("Release blocked: the library path manifest is invalid.")


def create_release_app():
    """Build once from the existing remote source; never ship a fallback fixture."""
    install_log_redaction()
    release = json.loads(RELEASE_FILE.read_text(encoding="utf-8"))
    context = build_context()
    validate_release_context(context, release)
    app = create_app(context)

    @app.after_request
    def release_headers(response):
        response.headers["X-Archipelago-Release"] = release["source_commit"]
        if response.mimetype in {"text/html", "text/javascript", "application/javascript", "text/css"}:
            response.headers["Cache-Control"] = "no-store"
        return response

    return app

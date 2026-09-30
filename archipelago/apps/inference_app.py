"""Gunicorn/CLI entrypoint for the Archipelago inference service."""
from __future__ import annotations

import os
import threading
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

from archipelago.inference.bootstrap import app, init_concepts_data  # noqa: E402
from archipelago.inference.embeddings import load_aura_model, load_embedding_model  # noqa: E402

_runtime_lock = threading.Lock()
_runtime_started = False


def create_app():
    """Initialize process-local state once and return the Flask WSGI app."""
    global _runtime_started
    with _runtime_lock:
        if not _runtime_started:
            init_concepts_data()
            if os.getenv("ARCHIPELAGO_LOAD_EMBEDDINGS", "0").strip().lower() in {"1", "true", "yes"}:
                threading.Thread(target=load_embedding_model, name="ArchipelagoEmbeddings", daemon=True).start()
            if os.getenv("ARCHIPELAGO_LOAD_AURA", "0").strip().lower() in {"1", "true", "yes"}:
                threading.Thread(target=load_aura_model, name="ArchipelagoAura", daemon=True).start()
            from ingestion_worker import get_worker
            get_worker()
            _runtime_started = True
    return app


def main() -> None:
    application = create_app()
    host = os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1")
    port = int(os.environ.get("ARCHIPELAGO_INFERENCE_PORT", os.environ.get("PORT", "5151")))
    print(f"\nArchipelago Inference — http://{host}:{port}\n")
    application.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

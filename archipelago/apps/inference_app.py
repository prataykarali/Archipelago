"""Archipelago Inference Server — WSGI entrypoint.

Run modes:
  Production (Gunicorn):  gunicorn "archipelago.apps.inference_app:app"
  Development:            python -m archipelago.apps.inference_app
"""
from __future__ import annotations

import os
import threading

from archipelago.inference.bootstrap import app, init_concepts_data
from archipelago.inference.embeddings import load_embedding_model, load_aura_model


def _startup():
    """Initialise data and kick off background model loaders."""
    init_concepts_data()
    threading.Thread(target=load_embedding_model, daemon=True).start()
    if os.getenv("ARCHIPELAGO_LOAD_AURA", "0") == "1":
        threading.Thread(target=load_aura_model, daemon=True).start()


# Run startup both when launched directly AND when imported by Gunicorn.
# Guard flag prevents double-init during test collection.
if not os.environ.get("_ARCHIPELAGO_INIT_DONE"):
    os.environ["_ARCHIPELAGO_INIT_DONE"] = "1"
    _startup()


def main():
    """Dev-mode entry: flask dev server."""
    port = int(os.environ.get("PORT", 5051))
    bind = os.environ.get("ARCHIPELAGO_BIND", "0.0.0.0")
    print(f"\nArchipelago Inference — http://{bind}:{port}\n")
    app.run(host=bind, port=port, debug=False)


if __name__ == "__main__":
    main()

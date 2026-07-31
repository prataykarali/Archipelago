"""Run inference server: python -m archipelago.apps.inference_app"""
from __future__ import annotations

import os
import threading

from archipelago.inference.bootstrap import app, init_concepts_data
from archipelago.inference.embeddings import load_embedding_model, load_aura_model


def main():
    init_concepts_data()
    threading.Thread(target=load_embedding_model, daemon=True).start()
    if os.getenv("ARCHIPELAGO_LOAD_AURA", "0") == "1":
        threading.Thread(target=load_aura_model, daemon=True).start()
    host = os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1")
    port = int(os.environ.get("ARCHIPELAGO_INFERENCE_PORT", "5051"))
    print(f"\nArchipelago Inference — http://localhost:{port}\n")
    # threaded=True: readiness polls must not block /api/chat streaming.
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

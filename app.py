"""
Archipelago Production REST & Streaming API Application Entrypoint.

Dockerized, production-grade backend powered by two local Ollama models:
- lib-qwen:latest (OKF graph extraction & ingestion)
- qwen3.5:0.8b (Grounded pedagogical synthesis)
"""

from __future__ import annotations

import os
from src.api.app import app

__all__ = ["app"]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("ARCHIPELAGO_INFERENCE_PORT", "5051")))
    bind = os.environ.get("ARCHIPELAGO_BIND", "0.0.0.0")
    print(f"\n🚀 Archipelago Production REST Engine listening on http://{bind}:{port}\n")
    app.run(host=bind, port=port, debug=False)

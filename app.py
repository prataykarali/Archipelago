"""
Archipelago Production REST & Streaming API Application Entrypoint.

Dockerized, production-grade backend powered by two local Ollama models:
- lib-qwen:latest (OKF graph extraction & ingestion)
- qwen3.5:0.8b (Grounded pedagogical synthesis)
"""

from __future__ import annotations

import os

if os.environ.get("VERCEL"):
    from pathlib import Path
    import sys

    _host_dir = Path(__file__).resolve().parent / "host_inference"
    if str(_host_dir) not in sys.path:
        sys.path.insert(0, str(_host_dir))
    from vercel_wsgi import create_vercel_app

    app = create_vercel_app()
else:
    from archipelago.api.app import app

__all__ = ["app"]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("ARCHIPELAGO_INFERENCE_PORT", "5051")))
    # Loopback by default; the container/Dockerfile sets ARCHIPELAGO_BIND=0.0.0.0.
    bind = os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1")
    print(f"\n🚀 Archipelago Production REST Engine listening on http://{bind}:{port}\n")
    app.run(host=bind, port=port, debug=False)

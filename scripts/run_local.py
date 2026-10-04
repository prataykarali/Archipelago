"""Run the self-contained Archipelago chat locally without touching deployment settings.

Usage: python scripts/run_local.py --port 5151
Install host_inference/requirements.txt first. Default binding is loopback only.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def main() -> None:
    """Start the same app used by the standalone image, with safe local defaults."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5151)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("This development runner is loopback-only; use authenticated production configuration for remote access.")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "host_inference"))
    os.environ.setdefault("ARCHIPELAGO_ENV", "development")
    os.environ.setdefault("ARCHIPELAGO_AUTH_REQUIRED", "0")
    from hostapp import create_app

    app = create_app()
    print(f"Archipelago: http://{args.host}:{args.port}/chat", flush=True)
    print("Local inference UI; run the existing ingestion workstation separately for uploads.", flush=True)
    app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()

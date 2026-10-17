"""A Vercel function boots from its read-only bundle with a labelled fixture."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

HOST = Path(__file__).resolve().parents[2] / "host_inference"
BOOT_CHECK = (
    "import json, server; "
    "response = server.app.test_client().get('/api/readiness'); "
    "print(json.dumps({'status': response.status_code, 'body': response.get_json()}))"
)


def test_vercel_runtime_uses_writable_cache_and_starts() -> None:
    """Cold functions can serve the packaged fixture without writing to /var/task."""
    environment = os.environ.copy()
    for key in (
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "HF_DATASET_REPO",
    ):
        environment.pop(key, None)
    environment.update({"VERCEL": "1", "VERCEL_ENV": "preview", "ARCHIPELAGO_ENV": "production"})
    result = subprocess.run(
        [sys.executable, "-c", BOOT_CHECK],
        cwd=HOST,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    output = json.loads(result.stdout.strip())
    assert output["status"] == 200
    assert output["body"]["corpus"]["source"] == "fixture"
    assert output["body"]["corpus"]["full"] is False

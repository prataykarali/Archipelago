"""Hosted and library API fixtures for response contract tests."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def hosted_engine():
    """The hosted engine, or skip when its graph cache is absent."""
    graph = HOST_DIR / "cache" / "okf_graph.json"
    if not graph.is_file():
        pytest.skip("hosted concept graph cache is not present")
    import engine as hosted

    return hosted.Engine()


@pytest.fixture(scope="module")
def library_client():
    """A Flask test client on the deployed API app."""
    try:
        from archipelago.api.app import app
    except Exception as exc:
        pytest.fail(f"library app failed to import: {exc}")
    app.config.update(TESTING=True)
    return app.test_client()

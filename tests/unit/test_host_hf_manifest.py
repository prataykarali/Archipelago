"""The hosted PDF shelf is derived from Hugging Face at runtime."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import remote_cache  # noqa: E402

pytestmark = pytest.mark.unit


def test_hf_manifest_uses_dataset_file_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Only PDF paths from the authenticated dataset tree enter the shelf."""
    monkeypatch.setattr(remote_cache, "CACHE", tmp_path)
    monkeypatch.setenv("HF_TOKEN", "test-token")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, str]]:
            return [
                {"path": "books/paper.pdf"},
                {"path": "books/paper.pdf"},
                {"path": "catalogs/books.json"},
            ]

    def fake_get(url: str, **kwargs: object) -> Response:
        assert url.endswith("/Prataykarali/Library_books/tree/main")
        assert kwargs["headers"] == {"Authorization": "Bearer test-token"}
        return Response()

    monkeypatch.setattr(remote_cache.requests, "get", fake_get)
    assert remote_cache._hydrate_hf_manifest()
    payload = json.loads((tmp_path / "library_manifest.json").read_text())
    assert payload == {"hf_paths": ["books/paper.pdf"]}

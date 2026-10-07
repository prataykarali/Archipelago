"""Source pages and provider failover use real routes and bounded fallback."""

from __future__ import annotations

from pathlib import Path
import sys

HOSTED = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOSTED) not in sys.path:
    sys.path.insert(0, str(HOSTED))


def test_legacy_hf_path_prefers_root_copy_when_manifest_has_duplicates(monkeypatch):
    import library_index

    monkeypatch.setattr(
        library_index,
        "load_hf_paths",
        lambda: ["Lewis2020_RAG.pdf", "books/papers/Lewis2020_RAG.pdf"],
    )
    assert library_index.resolve_hf_path("papers/Lewis2020_RAG.pdf") == "Lewis2020_RAG.pdf"


def test_rate_limited_xkiro_uses_nvidia_for_substantial_reply(monkeypatch):
    from engine import llm

    class Response:
        def __init__(self, status: int):
            self.status_code = status

        def json(self):
            paragraph = "The indexed source explains the mechanism and its role in retrieval. " * 4
            return {"choices": [{"message": {"content": paragraph + "\n\n" + paragraph}}]}

    calls = []

    def fake_post(url, **_kwargs):
        calls.append(url)
        return Response(429 if "xkiro" in url else 200)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_pace_provider_call", lambda: None)
    llm._provider_backoff_until.clear()
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("XKIRO_API_KEY", "test-key")
    config = llm._build_config("xkiro")
    assert config is not None

    reply, provider = llm.grounded_completion(config, "Indexed evidence")

    assert provider is not None and provider["provider"] == "nvidia"
    assert llm.substantial_reply(reply)
    assert len(calls) == 2
    llm._provider_backoff_until.clear()

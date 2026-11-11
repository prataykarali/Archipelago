"""The private paper archive can ground chat without exposing its HF token."""

from __future__ import annotations

import json
from types import SimpleNamespace

from flask import Flask
import pytest

from host_inference.hostapp import research_chat, research_library_evidence
from host_inference.hostapp.middleware import register_middleware
from host_inference.hostapp.routes import library
from scripts.ops.stage_wikibooks_algorithms import extract_academic_page

pytestmark = pytest.mark.unit

RECORD_KEY = "a" * 64
JOB_ID = "job-one"


def test_private_export_selects_exact_paper_without_leaking_token(monkeypatch) -> None:
    """A job file can hold many papers, but retrieval returns one safe row."""
    requests_seen = []
    payload = "\n".join(
        json.dumps(item)
        for item in (
            {"record_key": "b" * 64, "title": "Other"},
            {"record_key": RECORD_KEY, "title": "Target", "verified_facts": []},
        )
    ).encode()

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def iter_content(self, chunk_size):
            assert chunk_size > 0
            yield payload

    def fake_get(url, **kwargs):
        requests_seen.append((url, kwargs))
        return Response()

    monkeypatch.setenv("HF_TOKEN", "private-test-token")
    monkeypatch.delenv("HF_LIBRARY_REPO", raising=False)
    monkeypatch.setattr(research_library_evidence.requests, "get", fake_get)
    result = research_library_evidence.library_paper_evidence(
        {"record_key": RECORD_KEY, "metadata": {"ingestion_job_id": JOB_ID}}
    )
    assert result is not None and result["title"] == "Target"
    assert result["library_path"] == f"catalogs/research_papers/{JOB_ID}.jsonl"
    assert "private-test-token" not in json.dumps(result)
    assert requests_seen[0][1]["headers"]["Authorization"] == "Bearer private-test-token"
    other = research_library_evidence.library_paper_evidence(
        {"record_key": "b" * 64, "metadata": {"ingestion_job_id": JOB_ID}}
    )
    assert other is not None and other["title"] == "Other"
    assert len(requests_seen) == 1


def test_paper_evidence_route_requires_session(monkeypatch) -> None:
    """The reader gets the selected evidence; anonymous callers get 401."""

    class Auth:
        def required(self):
            return True

        def principal(self):
            from flask import request

            if request.headers.get("Authorization") == "Bearer test-session":
                return {"id": "reader-one", "role": "student"}, None
            return None, "missing session"

    class Limiter:
        def check_api(self):
            return False, 0

    ctx = SimpleNamespace(auth=Auth(), limiter=Limiter())
    app = Flask(__name__)
    register_middleware(app, ctx)
    library.register(app, ctx)
    monkeypatch.setattr(
        library,
        "get_record",
        lambda _key: {"record_key": RECORD_KEY, "kind": "paper", "metadata": {}},
    )
    monkeypatch.setattr(library, "library_paper_evidence", lambda _row: {"title": "Target"})
    client = app.test_client()
    assert client.get(f"/api/library/paper-evidence/{RECORD_KEY}").status_code == 401
    response = client.get(
        f"/api/library/paper-evidence/{RECORD_KEY}",
        headers={"Authorization": "Bearer test-session"},
    )
    assert response.status_code == 200
    assert response.json == {"title": "Target"}


def test_wikibooks_stage_keeps_attribution_and_prerequisites() -> None:
    """The source staging path keeps provenance and usable academic prose."""
    html = b'<div id="mw-content-text"><div class="mw-parser-output"><h2>Prerequisites</h2><p>Algorithms requires prior familiarity with arrays, stacks, and queues.</p></div></div>'
    staged = extract_academic_page(html, "https://en.wikibooks.org/wiki/Algorithms/Introduction")
    assert "CC BY-SA 4.0" in staged
    assert "Wikibooks contributors" in staged
    assert "Algorithms requires prior familiarity" in staged


def test_main_chat_uses_published_library_facts_with_source_link(monkeypatch) -> None:
    """A matching paper uses the HF evidence artifact when it is available."""
    monkeypatch.setattr(
        research_chat,
        "search_records",
        lambda *_args, **_kwargs: [
            {
                "record_key": RECORD_KEY,
                "title": "Attention retrieval study",
                "topic": "attention",
                "content": "Abstract fallback text",
                "kind": "paper",
                "source_url": "https://arxiv.org/abs/1234.5678",
            }
        ],
    )
    monkeypatch.setattr(
        research_chat,
        "library_paper_evidence",
        lambda _row: {"verified_facts": [{"field": "datasets", "value": "Research benchmark"}]},
    )
    answer = research_chat.enrich_with_research(
        {"route": "GRAPH_SYNTHESIS", "text": "Academic answer", "payload": {}},
        "attention papers",
    )
    assert "datasets: Research benchmark" in answer["text"]
    assert "https://arxiv.org/abs/1234.5678" in answer["text"]
    assert f"/api/library/paper-evidence/{RECORD_KEY}" in answer["text"]

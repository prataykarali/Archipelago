"""Unit and protocol tests for D11-A.2 F01 stream-completion and UI-state hotfix."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_UI = REPO_ROOT / "host_inference" / "ui"
CANONICAL_UI = REPO_ROOT / "ui" / "chat"


def _mock_sse_response(chunks: list[bytes], status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.iter_content.return_value = iter(chunks)
    resp.close.return_value = None
    return resp


def _cfg() -> dict[str, str]:
    return {
        "base_url": "https://example.invalid/v1",
        "key": "sk-test-redacted",
        "model": "cohere/command-a",
        "provider": "xkiro",
    }


@pytest.mark.unit
def test_normal_complete_stream_across_arbitrary_chunk_boundaries() -> None:
    from host_inference.engine import llm

    raw_sse = (
        b'data: {"choices":[{"delta":{"content":"Paging divides "},"finish_reason":null}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"memory into fixed pages."},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    # Split every 11 bytes (mid-JSON, mid-key, mid-marker)
    chunks = [raw_sse[i : i + 11] for i in range(0, len(raw_sse), 11)]

    with patch.object(llm.requests, "post", return_value=_mock_sse_response(chunks)):
        tokens = list(llm.stream_completion(_cfg(), "evidence", query="explain paging"))

    assert "".join(tokens) == "Paging divides memory into fixed pages."
    outcome = llm.last_stream_outcome()
    assert outcome is not None
    assert outcome["status"] == "complete"
    assert outcome["finish_reason"] == "stop"
    assert outcome["saw_done"] is True
    assert llm.last_provider_error() is None


@pytest.mark.unit
@pytest.mark.parametrize("reason", ["length", "max_tokens"])
def test_token_limit_truncation_detected_and_marked(reason: str) -> None:
    from host_inference.engine import answer, llm

    raw_sse = (
        'data: {"choices":[{"delta":{"content":"1. Page Tables: Each process"},"finish_reason":"'
        + reason
        + '"}]}\n\n'
        "data: [DONE]\n\n"
    ).encode("utf-8")

    with (
        patch.object(llm.requests, "post", return_value=_mock_sse_response([raw_sse])),
        patch.object(answer, "provider_config", return_value=_cfg()),
        patch.object(answer, "fallback_config", return_value=None),
    ):
        engine = answer.Engine.__new__(answer.Engine)
        engine.answer = lambda _q: {
            "route": "GRAPH_SYNTHESIS",
            "text": "Grounded paging draft.",
            "anchor": None,
            "payload": {"citations": [], "logs": [], "trace": {}},
        }
        engine.pearson_line = lambda _cid: ""
        out = "".join(engine.stream_chat("virtual memory paging"))

    outcome = llm.last_stream_outcome()
    assert outcome is not None
    assert outcome["status"] == "truncated_token_limit"
    assert f"[STREAM_TRUNCATED:{reason}]" in out
    assert "Response truncated (token limit reached)" in out
    assert "1. Page Tables: Each process" in out


@pytest.mark.unit
def test_premature_sse_eof_detected_and_marked_incomplete() -> None:
    from host_inference.engine import answer, llm

    # Closes mid-sentence with no finish_reason and no [DONE]
    raw_sse = (
        b'data: {"choices":[{"delta":{"content":"1. Page Tables: Each process"},"finish_reason":null}]}\n\n'
    )

    with (
        patch.object(llm.requests, "post", return_value=_mock_sse_response([raw_sse])),
        patch.object(answer, "provider_config", return_value=_cfg()),
        patch.object(answer, "fallback_config", return_value=None),
    ):
        engine = answer.Engine.__new__(answer.Engine)
        engine.answer = lambda _q: {
            "route": "GRAPH_SYNTHESIS",
            "text": "Grounded paging draft.",
            "anchor": None,
            "payload": {"citations": [], "logs": [], "trace": {}},
        }
        engine.pearson_line = lambda _cid: ""
        out = "".join(engine.stream_chat("virtual memory paging"))

    outcome = llm.last_stream_outcome()
    assert outcome is not None
    assert outcome["status"] == "incomplete_eof"
    assert "[STREAM_INCOMPLETE:incomplete_eof]" in out
    assert "Incomplete stream" in out


@pytest.mark.unit
def test_provider_timeout_and_http_error_followed_by_immediate_success() -> None:
    from host_inference.engine import llm

    # 1) Timeout
    with patch.object(llm.requests, "post", side_effect=requests.Timeout("read timeout")):
        assert list(llm.stream_completion(_cfg(), "ev", query="q1")) == []
    assert llm.last_stream_outcome()["status"] == "timeout"

    # 2) HTTP 429
    with patch.object(llm.requests, "post", return_value=_mock_sse_response([], status_code=429)):
        assert list(llm.stream_completion(_cfg(), "ev", query="q2")) == []
    assert llm.last_stream_outcome()["status"] == "http_429"

    # 3) Immediate subsequent success
    ok_sse = (
        b'data: {"choices":[{"delta":{"content":"Recovered answer."},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    with patch.object(llm.requests, "post", return_value=_mock_sse_response([ok_sse])):
        tokens = list(llm.stream_completion(_cfg(), "ev", query="q3"))
    assert "".join(tokens) == "Recovered answer."
    assert llm.last_stream_outcome()["status"] == "complete"
    assert llm.last_provider_error() is None


@pytest.mark.unit
def test_split_terminal_markers_reassembled_in_node() -> None:
    marker_js = HOST_UI / "js" / "stream-markers.js"
    node_script = f"""
import {{ splitSafeStreamChunk, extractStreamStatusMarkers }} from 'file://{marker_js}';
const pieces = ['Hello world\\n[STR', 'EAM_TRUNCATED:len', 'gth]\\nmore [STRE', 'AM_DONE]'];
let buf = '';
let out = '';
let status = null;
for (const p of pieces) {{
  buf += p;
  const {{ ready, remainder }} = splitSafeStreamChunk(buf, {{ finalFlush: false }});
  buf = remainder;
  const ex = extractStreamStatusMarkers(ready);
  if (ex.streamStatus) status = ex.streamStatus;
  out += ex.cleaned;
}}
const fin = splitSafeStreamChunk(buf, {{ finalFlush: true }});
const exFin = extractStreamStatusMarkers(fin.ready);
if (exFin.streamStatus) status = exFin.streamStatus;
out += exFin.cleaned;
console.log(JSON.stringify({{ out, status }}));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", node_script],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout.strip())
    assert data["status"] == "truncated_token_limit"
    assert "[STREAM_TRUNCATED:length]" not in data["out"]
    assert "[STREAM_DONE]" in data["out"]


@pytest.mark.unit
def test_frontend_stop_cancellation_and_sequence_guards_synced() -> None:
    for rel in (
        "js/00-state.js",
        "js/07-open-page-viewer-modal.js",
        "js/08-send-message.js",
        "js/08-stream-cleanup.js",
        "js/08-stream-error.js",
        "js/15-inspector.js",
        "js/stream-markers.js",
    ):
        assert (HOST_UI / rel).read_text(encoding="utf-8") == (CANONICAL_UI / rel).read_text(
            encoding="utf-8"
        ), f"UI drift detected in {rel}"

    stop_js = (HOST_UI / "js" / "07-open-page-viewer-modal.js").read_text(encoding="utf-8")
    assert "state.activeTypewriter.stop()" in stop_js
    assert "state.activeResponseTimeoutId" in stop_js
    assert "state.activeStreamIdleTimeoutId" in stop_js
    assert "USER_CANCELLED" in stop_js

    send_js = (HOST_UI / "js" / "08-send-message.js").read_text(encoding="utf-8")
    assert "if (thisQuerySequence !== state.currentQuerySequence) return;" in send_js
    assert "splitSafeStreamChunk" in send_js
    assert "extractStreamStatusMarkers" in send_js

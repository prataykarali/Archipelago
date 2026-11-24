"""D10-S6 remediation regression tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "host_inference" / "fixtures" / "okf_graph.json"
EXPECTED_GRAPH_SHA256 = "9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76"


def test_gpt_summary_corrected_and_frozen_graph_preserved():
    from engine.graph import LibraryGraph

    assert hashlib.sha256(GRAPH_PATH.read_bytes()).hexdigest() == EXPECTED_GRAPH_SHA256
    graph = LibraryGraph(GRAPH_PATH)
    gpt_summary = graph.nodes["gpt"]["summary"]
    assert "autoregressive" in gpt_summary.lower()
    assert "not masked language modeling" in gpt_summary.lower()
    assert "uses masked language modeling" not in gpt_summary.lower()

    # D10-S7 demo-critical semantic overrides
    assert "1,024" in graph.nodes["gpt_2"]["summary"]
    assert "1234" not in graph.nodes["gpt_2"]["summary"]
    assert "probabilistic" in graph.nodes["bm25"]["summary"].lower()
    assert "masked language modeling" not in graph.nodes["bm25"]["summary"].lower()
    assert "dual-encoder" in graph.nodes["dpr"]["summary"].lower()
    assert "masked language modeling" not in graph.nodes["dpr"]["summary"].lower()
    assert "self-attention" in graph.nodes["transformer_encoder"]["summary"].lower()
    assert "masked language modeling" not in graph.nodes["transformer_encoder"]["summary"].lower()


def test_durable_session_rpc_renamed_to_avoid_table_collision():
    from hostapp.session_store import SESSION_RPC_NAME

    assert SESSION_RPC_NAME == "archipelago_runtime_session_rpc"
    sql = (
        ROOT / "supabase" / "migrations" / "20261124000000_d10_s4_durable_sessions.sql"
    ).read_text(encoding="utf-8")
    assert "function public.archipelago_runtime_session_rpc(" in sql
    assert "function public.archipelago_runtime_session(" not in sql


def test_auth_bridge_synced_no_stale_cache_and_proactive_invalidation():
    hosted = (ROOT / "host_inference" / "ui" / "auth_bridge.js").read_text(encoding="utf-8")
    canonical = (ROOT / "ui" / "chat" / "auth_bridge.js").read_text(encoding="utf-8")
    assert hosted == canonical
    assert "readCachedMe" not in hosted
    assert "visibilitychange" in hosted
    assert "X-Session-Passive" in hosted
    assert "clearVisibleAuthenticatedUi" in hosted


def test_readiness_and_chat_trace_expose_release_sha_and_passage_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    monkeypatch.setenv("ARCHIPELAGO_ENV", "development")
    monkeypatch.setenv("SUPABASE_URL", "https://edokbtmhztkhndmxetpy.supabase.co")

    idx = tmp_path / "passages.jsonl"
    idx.write_text(
        json.dumps(
            {
                "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf",
                "page_number": 7,
                "passage_id": "38d81af0ae91:p7:c0",
                "text": "The hardware adds the base register and checks bounds.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ARCHIPELAGO_CANDIDATE_PASSAGES", str(idx))
    monkeypatch.setenv(
        "ARCHIPELAGO_CANDIDATE_PASSAGES_SHA256",
        hashlib.sha256(idx.read_bytes()).hexdigest(),
    )

    from hostapp import create_app

    app = create_app()
    client = app.test_client()

    readiness = client.get("/api/readiness")
    assert readiness.status_code == 200
    assert readiness.headers.get("X-Archipelago-Release") not in {None, "", "unknown"}
    assert "https://edokbtmhztkhndmxetpy.supabase.co" in readiness.headers.get(
        "Content-Security-Policy", ""
    )
    rdata = readiness.get_json()
    assert rdata["release_sha"] not in {None, "", "unknown"}
    assert rdata["candidate_passages"]["loaded"] is True
    assert rdata["candidate_passages"]["checksum_verified"] is True

    chat = client.post(
        "/api/chat",
        json={"query": "Explain base-and-bounds address translation in OSTEP", "synthesis": True},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert chat.status_code == 200
    raw = chat.get_data(as_text=True)
    meta = json.loads(raw.split("[STREAM_START]", 1)[0].strip())
    trace = meta["trace"]
    assert trace["release_sha"] not in {None, "", "unknown"}
    assert "38d81af0ae91:p7:c0" in trace["passage_ids"]
    assert "38d81af0ae91:p7:c0" in trace["cited_passage_ids"]
    assert "38d81af0ae91:p7:c0" in trace["retrieved_passage_ids"]

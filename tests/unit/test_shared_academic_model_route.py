"""The normal academic OKF worker can use the same scored SLM tag."""

from __future__ import annotations

import json
from types import SimpleNamespace

from okf.extraction.part02_is_local_mode import extract_okf_v15


def test_shared_model_uses_academic_contract(monkeypatch) -> None:
    """An explicit shared tag bypasses the older local-model prompt path."""
    requests: list[dict] = []
    monkeypatch.setenv("ARCHIPELAGO_INGESTION_MODEL", "dual-ingest:test")

    def chat(**kwargs):
        requests.append(kwargs)
        payload = [
            {
                "concept_name": "Attention Mechanism",
                "concept_type": "core",
                "difficulty": "intermediate",
                "summary": "Attention assigns weights to input positions when computing a representation.",
                "prerequisites": [],
                "unlocks": [],
                "related_to": [],
                "tags": [],
            }
        ]
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))

    monkeypatch.setattr("okf.extraction.part02_is_local_mode.ollama.chat", chat)
    result = extract_okf_v15(
        text="The Attention Mechanism assigns weights to input positions.",
        doc_id="attention-book",
        chunk_id="chunk-one",
        page_number=4,
        doc_title="Attention Book",
    )
    assert len(result) == 1
    assert result[0]["concept_name"] == "Attention Mechanism"
    assert result[0]["concept_type"] == "definition"
    assert result[0]["page_number"] == 4
    assert requests[0]["model"] == "dual-ingest:test"
    source = json.loads(requests[0]["messages"][1]["content"])
    assert source["title"] == "Attention Book"
    assert source["page"] == 4

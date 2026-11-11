"""Grounded response formatting for finished research jobs."""

from __future__ import annotations

import pytest

from archipelago.scholarly.pipeline.reply import build_research_reply

pytestmark = pytest.mark.unit


def test_research_reply_uses_only_stored_relevance_results() -> None:
    reply = build_research_reply(
        {
            "job_id": "job-one",
            "topic": "Bengali speech recognition",
            "status": "partial",
            "error": "semantic_scholar rate_limited",
            "shortlist": [
                {
                    "rank": 1,
                    "paper_id": "paper-one",
                    "title": "Bengali Speech Recognition",
                    "year": "2022",
                    "doi": "10.1000/bengali",
                    "topic_relevance_reason": ["title query coverage 1.00"],
                    "access_state": "METADATA_ONLY",
                }
            ],
        }
    )
    assert "10.1000/bengali" in reply["text"]
    assert "title query coverage 1.00" in reply["text"]
    assert "semantic_scholar rate_limited" in reply["text"]
    assert reply["papers"][0]["access_state"] == "METADATA_ONLY"

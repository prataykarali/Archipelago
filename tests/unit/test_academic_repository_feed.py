"""Public repository discovery produces review candidates, not ingested files."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import requests

HOST = Path(__file__).resolve().parents[2] / "host_research"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import repository_feed  # noqa: E402


@pytest.mark.unit
def test_feed_keeps_only_repository_item_links(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = b"""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Research Directory</title>
        <id>http://uemk.ndl.gov.in/handle/123456789/959</id>
        <updated>2026-08-11T10:00:00Z</updated></entry>
      <entry><title>Unexpected host</title>
        <id>https://example.invalid/handle/123456789/960</id></entry>
    </feed>"""
    response = requests.Response()
    response.status_code = 200
    response._content = feed
    monkeypatch.setattr(repository_feed.requests, "get", lambda *_args, **_kwargs: response)
    items, metadata = repository_feed.discover_repository_items()
    assert items == [
        {
            "title": "Research Directory",
            "source_url": "https://uemk.ndl.gov.in/handle/123456789/959",
            "updated_at": "2026-08-11T10:00:00Z",
            "ingestion_status": "not_started",
        }
    ]
    assert metadata["count"] == 1

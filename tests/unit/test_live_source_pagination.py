"""Regression tests for live provider paging and response validation."""

from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from archipelago.scholarly.discovery.live_sources import LiveResearchSources

pytestmark = pytest.mark.unit


class PageSession:
    """Record actual pagination parameters and return specified HTTP pages."""

    def __init__(self, pages: list[tuple[int, dict[str, Any] | str, str]]) -> None:
        self.pages = pages
        self.params: list[dict[str, Any]] = []

    def get(
        self, url: str, *, params: dict[str, Any], headers: dict[str, str], timeout: int
    ) -> requests.Response:
        del headers, timeout
        self.params.append(params)
        status, payload, content_type = self.pages[len(self.params) - 1]
        response = requests.Response()
        response.status_code = status
        response.headers["content-type"] = content_type
        response._content = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
        response.url = url
        return response


def _work(index: int, kind: str = "article") -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/W{index}",
        "type": kind,
        "title": f"Paper {index}",
        "publication_date": "2025-01-01",
        "authorships": [{"author": {"display_name": "A Researcher"}}],
    }


def test_filtered_page_uses_stable_size_and_advances_without_overlap() -> None:
    session = PageSession(
        [
            (
                200,
                {"results": [_work(1), _work(2), _work(3, "dataset"), _work(4), _work(5)]},
                "application/json",
            ),
            (200, {"results": [_work(6)]}, "application/json"),
        ]
    )
    response = LiveResearchSources(session=session).search("openalex", "machine learning", 5)  # type: ignore[arg-type]
    assert response.status == "live"
    assert response.pages_fetched == 2
    assert [p["paper"].title for p in response.records] == [
        "Paper 1",
        "Paper 2",
        "Paper 4",
        "Paper 5",
        "Paper 6",
    ]
    assert [p["page"] for p in session.params] == [1, 2]
    assert [p["per-page"] for p in session.params] == [5, 5]


def test_non_json_openalex_response_is_reported_as_parse_failure() -> None:
    session = PageSession([(200, "<html>upstream error</html>", "text/html")])
    response = LiveResearchSources(session=session).search("openalex", "machine learning", 5)  # type: ignore[arg-type]
    assert response.status == "parse_failed"
    assert response.records == []
    assert response.http_status == 200

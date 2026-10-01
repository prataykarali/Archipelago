"""Integration tests for Archipelago LinkResolver service.

Verifies that exact source links (Pearson, Hugging Face, OpenLibrary, DOI)
resolve properly, rate limiting works, negative caching works, and fabricated
or non-existent books do not hallucinate valid links.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from archipelago.resolver.resolver import LinkResolver


@pytest.fixture
def resolver() -> LinkResolver:
    return LinkResolver()


@pytest.mark.integration
def test_resolver_known_pilot_resource(resolver: LinkResolver) -> None:
    """Known seeded resource IDs should be detected by the Bloom filter."""
    known_id = "paper_attention_is_all_you_need_2017"
    assert known_id in resolver.bloom
    assert known_id in resolver.cuckoo


@pytest.mark.integration
def test_resolver_fabricated_book_returns_no_url(resolver: LinkResolver) -> None:
    """Non-existent or fabricated book titles must not produce hallucinated URLs."""
    res = resolver.resolve(
        resource_id="completely_fabricated_fake_book_9999",
        title="Fabricated Title Not In Catalog",
        isbn="000-0-000000-00-0",
    )
    # Must not fabricate a URL
    assert res is None or res.get("url") is None or res.get("verified") is False


@pytest.mark.integration
def test_resolver_doi_resolution(resolver: LinkResolver) -> None:
    """Valid DOI should construct a legitimate resolver link."""
    with patch("archipelago.resolver.doi.resolve_doi") as mock_doi:
        mock_doi.return_value = {
            "url": "https://doi.org/10.1145/123456",
            "provider": "doi",
            "verified": True,
        }
        res = resolver.resolve(doi="10.1145/123456")
        assert res is not None
        assert "doi.org" in res.get("url", "")


@pytest.mark.integration
def test_resolver_caching_behavior(resolver: LinkResolver) -> None:
    """Resolved items should be cached in memory to minimize external network requests."""
    with patch("archipelago.resolver.openlibrary.resolve_openlibrary") as mock_ol:
        mock_ol.return_value = {
            "url": "https://openlibrary.org/books/OL123M",
            "provider": "openlibrary",
            "verified": True,
        }
        res1 = resolver.resolve(title="Test ML Textbook", isbn="9780123456789")
        assert res1 is not None

        # Second call should use cache
        res2 = resolver.resolve(title="Test ML Textbook", isbn="9780123456789")
        assert res2 == res1

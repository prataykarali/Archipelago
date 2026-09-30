"""Unit tests for Resource Resolver, Resource Registry, and Dual-Mode Link Resolution."""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from archipelago.resolver.huggingface import resolve_huggingface_url, verify_hf_repo_file
from archipelago.resolver.pearson import resolve_pearson_url
from archipelago.resolver.resource_registry import get_registry, ResourceRegistry
from archipelago.resolver.resolver import LinkResolver

pytestmark = pytest.mark.unit


def test_registry_contains_46_unique_resources():
    """Verify registry enumerates exactly 46 resources without duplicates."""
    registry = get_registry()
    resources = registry.all_resources()
    assert len(resources) == 46

    report = registry.reconciliation_report()
    assert report["total_resources"] == 46
    assert report["sources"]["pearson"] == 40
    assert report["sources"]["local"] == 2
    assert report["sources"]["huggingface"] == 2
    assert report["sources"]["metadata_only"] == 2


def test_registry_lookup_by_id_and_alias():
    """Verify registry can look up by UUID, alias, and legacy prominent ID."""
    registry = get_registry()

    # Look up by Pearson UUID
    p_rec = registry.get_by_id("0fcd531f-3ba1-495e-9c9e-b43b034b88d9")
    assert p_rec is not None
    assert "Computer Networks" in p_rec.title
    assert p_rec.isbn == "9789356063259"

    # Look up by legacy alias
    alias_rec = registry.get_by_id("book_computer_networks_tanenbaum")
    assert alias_rec is not None
    assert alias_rec.resource_id == p_rec.resource_id

    # Look up by prominent ID
    ostep = registry.get_by_id("ostep_three_easy_pieces")
    assert ostep is not None
    assert "Three Easy Pieces" in ostep.title
    assert ostep.source == "local"


def test_title_normalization_and_deduplication():
    """Verify title normalization normalizes edition notation while keeping distinct editions separate."""
    norm = ResourceRegistry.normalize_title

    # Same edition variants normalize identically
    e1 = norm("Computer Networks, 6/e")
    e2 = norm("Computer Networks 6e")
    e3 = norm("Computer Networks 6th Edition")
    assert e1 == e2 == e3

    # Different editions normalize differently
    e5 = norm("Computer Networks, 5/e")
    assert e5 != e1


def test_hf_resolver_canonical_blob_and_resolve_urls():
    """Verify HF resolver returns browser-readable blob URL and resolve URL."""
    res = resolve_huggingface_url("textbooks/Deisenroth_Math_For_ML.pdf")
    assert res["working"] is True
    assert res["status"] == "resolved"
    assert "huggingface.co/datasets/Prataykarali/Library_books/blob/main/textbooks/Deisenroth_Math_For_ML.pdf" in res["blob_url"]
    assert "huggingface.co/datasets/Prataykarali/Library_books/resolve/main/textbooks/Deisenroth_Math_For_ML.pdf" in res["resolve_url"]
    assert res["target_blank"] is True


def test_hf_resolver_nonexistent_file_returns_missing():
    """Verify HF resolver accurately flags non-existent files as missing."""
    res = resolve_huggingface_url("textbooks/Totally_Fake_Nonexistent_Book_12345.pdf")
    assert res["working"] is False
    assert res["status"] == "missing"
    assert res["error"] is not None


def test_pearson_resolver_matches_catalog_book():
    """Verify Pearson resolver resolves known catalog books to viewer URLs."""
    res = resolve_pearson_url(book_id="0fcd531f-3ba1-495e-9c9e-b43b034b88d9")
    assert res["working"] is True
    assert "ebooks.elibrary.in.pearson.com" in res["url"]
    assert "0fcd531f-3ba1-495e-9c9e-b43b034b88d9" in res["url"]
    assert res["target_blank"] is True


def test_pearson_resolver_unknown_book_returns_not_found():
    """Verify Pearson resolver returns working=False and not_found status for unknown books."""
    res = resolve_pearson_url(book_id="nonexistent-uuid-99999", title="Fake Book That Does Not Exist", use_playwright=False)
    assert res["working"] is False
    assert res["status"] == "not_found"
    assert res["error_code"] == "PEARSON_NOT_FOUND"


def test_link_resolver_cascade_and_caching():
    """Verify LinkResolver cascades correctly and caches results."""
    resolver = LinkResolver()

    # Local resource resolution
    res_local = resolver.resolve("ostep_three_easy_pieces")
    assert res_local["working"] is True
    assert res_local["source"] == "local"
    assert "08_Paging.pdf" in res_local["url"]

    # Cached hit
    res_cached = resolver.resolve("ostep_three_easy_pieces")
    assert res_cached["working"] is True
    assert res_cached["url"] == res_local["url"]

    # Pearson aliased resolution
    res_pearson = resolver.resolve("book_computer_networks_tanenbaum")
    assert res_pearson["working"] is True
    assert "0fcd531f" in res_pearson["url"]

"""Unit tests for LinkResolver, HuggingFace, Pearson, DOI, Rate Limiter, Negative Cache, and Bloom Filter."""
from __future__ import annotations

import time
import pytest

from archipelago.resolver import LinkResolver, resolve_book, resolve_url
from archipelago.resolver.bloom_filter import BloomFilter, CuckooFilter
from archipelago.resolver.cache import RateLimiter, ResolverCache
from archipelago.resolver.doi import extract_doi, resolve_doi
from archipelago.resolver.huggingface import resolve_huggingface_url
from archipelago.resolver.pearson import resolve_pearson_url
from archipelago.resolver.validator import check_url_sync


def test_huggingface_resolver():
    res = resolve_huggingface_url("hf://datasets/Prataykarali/Library_books/papers/Vaswani2017_Attention_Is_All_You_Need.pdf")
    assert res["working"] is True
    assert "huggingface.co" in res["url"]

    res_file = resolve_huggingface_url("Vaswani2017_Attention_Is_All_You_Need.pdf")
    assert res_file["working"] is True
    assert "Prataykarali/Library_books" in res_file["url"]


def test_doi_resolver():
    doi_str = "10.1007/s11263-020-01387-w"
    extracted = extract_doi(f"https://doi.org/{doi_str}")
    assert extracted == doi_str

    res = resolve_doi(doi_str)
    assert res["working"] is True
    assert "doi.org" in res["doi_url"] or "doi" in res["source"]


def test_pearson_resolver():
    res = resolve_pearson_url(
        book_id="0fcd531f-3ba1-495e-9c9e-b43b034b88d9",
    )
    assert res["working"] is True
    assert "ebooks.elibrary.in.pearson.com" in res["url"]
    assert "subscriptionId=" in res["url"]
    assert "#book/0fcd531f-3ba1-495e-9c9e-b43b034b88d9" in res["url"]


def test_bloom_and_cuckoo_filter():
    bf = BloomFilter(capacity=100, error_rate=0.01)
    bf.add("book_deep_learning_2016")
    assert bf.contains("book_deep_learning_2016") is True
    assert bf.contains("non_existent_book_99999") is False

    cf = CuckooFilter(capacity=100)
    cf.add("paper_attention_2017")
    assert cf.contains("paper_attention_2017") is True
    assert cf.contains("non_existent_paper_88888") is False


def test_rate_limiter_and_negative_cache():
    limiter = RateLimiter(max_requests=3, window_seconds=10)
    client = "test_ip_1"
    assert limiter.is_allowed(client) is True
    assert limiter.is_allowed(client) is True
    assert limiter.is_allowed(client) is True
    assert limiter.is_allowed(client) is False  # 4th request blocked

    cache = ResolverCache(positive_ttl_sec=10, negative_ttl_sec=5)
    cache.set_negative("broken_key_123", "404 Not Found")
    cached = cache.get("broken_key_123")
    assert cached is not None
    assert cached["working"] is False
    assert cached["cached_negative"] is True


def test_ssrf_protection():
    from archipelago.resolver.validator import check_url_sync, is_safe_url

    safe, err = is_safe_url("http://127.0.0.1/admin")
    assert safe is False
    assert "Forbidden" in str(err)

    safe, err = is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert safe is False

    safe, err = is_safe_url("file:///etc/passwd")
    assert safe is False

    res = check_url_sync("http://127.0.0.1:5051/secret")
    assert res["working"] is False
    assert "SSRF Protection" in str(res["error"])


def test_link_resolver_integrated():

    resolver = LinkResolver()
    
    # HF resolution
    res_hf = resolver.resolve("paper_attention_is_all_you_need_2017")
    assert res_hf["working"] is True
    assert "url" in res_hf

    # Pearson resolution
    res_p = resolver.resolve(
        resource_id="pearson_book_1",
        title="Computer Networks",
        isbn="9789356063259",
        source="pearson",
    )
    assert res_p["working"] is True

    # Helper functions
    url_out = resolve_book("paper_attention_is_all_you_need_2017")
    assert isinstance(url_out, str)
    assert "http" in url_out

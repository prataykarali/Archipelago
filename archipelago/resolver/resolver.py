"""Main LinkResolver Service for Archipelago - Dual Mode HF + Pearson Engine."""
from __future__ import annotations

import logging
from typing import Any

from archipelago.resolver.bloom_filter import BloomFilter, CuckooFilter
from archipelago.resolver.cache import RateLimiter, ResolverCache
from archipelago.resolver.doi import extract_doi, resolve_doi
from archipelago.resolver.google_books import resolve_google_books
from archipelago.resolver.huggingface import resolve_huggingface_url
from archipelago.resolver.openlibrary import resolve_openlibrary
from archipelago.resolver.pearson import resolve_pearson_url

logger = logging.getLogger("archipelago.resolver")


class LinkResolver:
    """Integrated Link Resolver with Rate Limiting, Negative Caching, and Dual-Mode Resolvers."""

    def __init__(self):
        self.bloom = BloomFilter(capacity=50000, error_rate=0.005)
        self.cuckoo = CuckooFilter(capacity=10000)
        self.cache = ResolverCache(positive_ttl_sec=86400, negative_ttl_sec=600)
        self.rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
        self._init_known_catalog()

    def _init_known_catalog(self) -> None:
        """Seed Bloom & Cuckoo filters with known core pilot resources."""
        known_ids = [
            "corpus_book_artificial_intelligence_a_new_synthesis_1998",
            "paper_attention_is_all_you_need_2017",
            "book_math_for_machine_learning_2020",
            "book_deep_learning_goodfellow_2016",
            "book_speech_and_language_processing_jurafsky",
            "book_computer_networks_tanenbaum",
            "goodfellow2014_gan.pdf",
            "vaswani2017_attention_is_all_you_need.pdf",
            "hu2021_lora.pdf",
            "dettmers2023_qlora.pdf",
            "lewis2020_rag.pdf",
            "devlin2018_bert.pdf",
            "edge2024_graphrag.pdf",
            "bahdanau2014_attention.pdf",
            "kwon2023_vllm.pdf",
            "brown2020_gpt3.pdf",
            "deisenroth_math_for_ml.pdf",
        ]
        for kid in known_ids:
            self.bloom.add(kid)
            self.cuckoo.add(kid)

    def resolve(
        self,
        resource_id: str = "",
        title: str | None = None,
        author: str | None = None,
        isbn: str | None = None,
        doi: str | None = None,
        source: str | None = None,
        client_key: str = "default",
    ) -> dict[str, Any]:
        """Resolve a resource ID or query to a canonical working URL."""
        if not resource_id:
            resource_id = ""

        # 0. Rate limiting check
        if not self.rate_limiter.is_allowed(client_key):
            return {
                "id": resource_id,
                "working": False,
                "status": 429,
                "error": "Rate limit exceeded. Try again in a minute.",
            }

        cache_key = f"{resource_id}:{isbn}:{doi}:{source}"

        # 1. Check Cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            cached_copy = dict(cached)
            cached_copy["id"] = resource_id
            return cached_copy

        # 1.5 Check central ResourceRegistry
        from archipelago.resolver.resource_registry import get_registry
        reg_record = get_registry().get_by_id(resource_id)
        if reg_record:
            if reg_record.reader_url and reg_record.source in ("local", "open_access", "metadata_only", "huggingface"):
                res_url = reg_record.blob_url or reg_record.reader_url
                res_local = {
                    "id": resource_id,
                    "title": reg_record.title,
                    "working": True,
                    "status": "resolved",
                    "url": res_url,
                    "canonical_url": res_url,
                    "reader_url": reg_record.reader_url,
                    "blob_url": reg_record.blob_url,
                    "resolve_url": reg_record.resolve_url,
                    "source": reg_record.source,
                    "target_blank": reg_record.source in ("open_access", "metadata_only") or reg_record.reader_url.startswith("http"),
                }
                self.cache.set_positive(cache_key, res_local)
                return res_local
            elif reg_record.source == "pearson" and reg_record.pearson_book_id:
                if not resource_id or resource_id.startswith("book_") or resource_id.startswith("pearson_"):
                    resource_id = reg_record.pearson_book_id

        # 2. Pearson Strategy (Explicit source or Pearson URL/UUID patterns)
        if (source and "pearson" in source.lower()) or "pearson.com" in resource_id or (title and "pearson" in title.lower()):
            res_pearson = resolve_pearson_url(book_id=resource_id, isbn=isbn, title=title, existing_url=resource_id)
            if res_pearson.get("working"):
                self.cache.set_positive(cache_key, res_pearson)
                self.bloom.add(resource_id)
                res_pearson["id"] = resource_id
                return res_pearson

        # 3. Hugging Face Strategy
        if resource_id.startswith("hf://") or (source and source.lower() == "huggingface") or "huggingface.co" in resource_id:

            res_hf = resolve_huggingface_url(resource_id)
            if res_hf.get("working"):
                self.cache.set_positive(cache_key, res_hf)
                self.bloom.add(resource_id)
                res_hf["id"] = resource_id
                return res_hf

        # 4. Check Pearson catalog matching by ID / title / ISBN regardless of source flag
        res_pearson = resolve_pearson_url(book_id=resource_id, isbn=isbn, title=title, existing_url=resource_id)
        if res_pearson.get("working") and res_pearson.get("book_id"):
            self.cache.set_positive(cache_key, res_pearson)
            self.bloom.add(resource_id)
            res_pearson["id"] = resource_id
            return res_pearson

        # 5. Check Hugging Face resolution for PDF filenames or papers
        if resource_id.endswith(".pdf") or "paper_" in resource_id or "book_" in resource_id or "textbooks/" in resource_id or "papers/" in resource_id:
            res_hf = resolve_huggingface_url(resource_id, filename=resource_id)
            if res_hf.get("working"):
                self.cache.set_positive(cache_key, res_hf)
                self.bloom.add(resource_id)
                res_hf["id"] = resource_id
                return res_hf

        # 6. Strategy: DOI resolution
        target_doi = doi or extract_doi(resource_id)
        if target_doi:
            res_doi = resolve_doi(target_doi)
            if res_doi.get("working"):
                self.cache.set_positive(cache_key, res_doi)
                self.bloom.add(resource_id)
                res_doi["id"] = resource_id
                return res_doi

        # 7. Fallback Chain for Books (ISBN -> Google Books -> Open Library)
        if isbn or title:
            gb_res = resolve_google_books(isbn=isbn, title=title, author=author)
            if gb_res and gb_res.get("working"):
                self.cache.set_positive(cache_key, gb_res)
                self.bloom.add(resource_id)
                gb_res["id"] = resource_id
                return gb_res

            ol_res = resolve_openlibrary(isbn=isbn, title=title, author=author)
            if ol_res and ol_res.get("working"):
                self.cache.set_positive(cache_key, ol_res)
                self.bloom.add(resource_id)
                ol_res["id"] = resource_id
                return ol_res

        # 8. Final Fallback to Hugging Face dataset URL
        hf_fallback = resolve_huggingface_url(resource_id, filename=resource_id)
        if hf_fallback.get("working"):
            self.cache.set_positive(cache_key, hf_fallback)
            self.bloom.add(resource_id)
            hf_fallback["id"] = resource_id
            return hf_fallback

        # Failed resolution
        self.cache.set_negative(cache_key, "Resource link could not be resolved")
        return {
            "id": resource_id,
            "title": title or resource_id,
            "working": False,
            "status": 404,
            "error": "Resource link could not be resolved across catalog providers",
            "url": None,
        }


# Global singleton instance for quick module-level helper calls
_DEFAULT_RESOLVER = LinkResolver()


def resolve_book(book_id: str, title: str | None = None, isbn: str | None = None) -> str:
    """Module function to quickly resolve a book_id or ISBN to a URL."""
    res = _DEFAULT_RESOLVER.resolve(resource_id=book_id, title=title, isbn=isbn)
    if res.get("working") and res.get("url"):
        return str(res["url"])
    return f"https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/{book_id}"


def resolve_url(url_or_id: str) -> dict[str, Any]:
    """Module function to resolve metadata for a URL or resource ID."""
    return _DEFAULT_RESOLVER.resolve(resource_id=url_or_id)

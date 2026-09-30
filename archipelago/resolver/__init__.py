"""
LinkResolver Package for Archipelago.

Provides canonical URL resolution for Hugging Face, Pearson eLibrary, DOI,
Google Books, Open Library, and local PDFs, equipped with Rate Limiting,
Negative Caching, and Bloom/Cuckoo Filters.
"""
from archipelago.resolver.resolver import LinkResolver, resolve_book, resolve_url

__all__ = ["LinkResolver", "resolve_book", "resolve_url"]

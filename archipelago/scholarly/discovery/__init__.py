"""Discovery package."""

from archipelago.scholarly.discovery.anything_api_bridge import AnythingApiBridge
from archipelago.scholarly.discovery.arxiv_adapter import ArXivAdapter
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.crossref_adapter import CrossrefAdapter
from archipelago.scholarly.discovery.openalex_adapter import OpenAlexAdapter
from archipelago.scholarly.discovery.orchestrator import DiscoveryOrchestrator
from archipelago.scholarly.discovery.scholar_deeplink import generate_scholar_url

__all__ = [
    "AnythingApiBridge",
    "ArXivAdapter",
    "Canonicalizer",
    "CrossrefAdapter",
    "DiscoveryOrchestrator",
    "OpenAlexAdapter",
    "generate_scholar_url",
]

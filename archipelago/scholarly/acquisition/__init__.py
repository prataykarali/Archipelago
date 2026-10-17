"""Acquisition package."""

from archipelago.scholarly.acquisition.artifact_fetcher import ArtifactFetcher
from archipelago.scholarly.acquisition.pdf_parser import PDFParser
from archipelago.scholarly.acquisition.rights_resolver import RightsResolver

__all__ = ["ArtifactFetcher", "PDFParser", "RightsResolver"]

"""Shim: pdf_ingestion → archipelago.ingestion.*"""

from archipelago.ingestion.pdf_io import ingest_document as ingest_document
from archipelago.ingestion.pdf_io import ingest_folder as ingest_folder
from archipelago.ingestion.pdf_utils import *  # noqa: F403

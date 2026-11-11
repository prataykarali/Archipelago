#!/usr/bin/env python3
# ruff: noqa: RUF001
"""
Section-aware PDF ingestion with provenance tagging.
Splits PDFs by structural boundaries (headings, ToC) instead of arbitrary char counts.
Also supports Markdown and plain text files.
"""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

fitz: Any
try:
    import fitz as _fitz  # PyMuPDF

    fitz = _fitz
except ImportError:
    fitz = None

docx: Any
try:
    import docx  # python-docx (optional, for .docx support)
except ImportError:
    docx = None


# ---------------------------------------------------------------------------
# Chunk classification + section-title sanitation
#
# The single biggest ingestion-quality lever: only *prose* chunks should reach
# the SLM. Tables, reference lists, author/affiliation front-matter, and bare
# equation blocks produce hallucinated concept nodes, so we tag every chunk with
# a `chunk_kind` and let the pipeline drop the non-prose ones.
# ---------------------------------------------------------------------------
_CITATION_RE = re.compile(r"(\[\d+\]|\bet al\.?,?\s*\d{4}|\(\d{4}\))")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_ARXIV_HEADER_RE = re.compile(r"arxiv:\s*\d", re.IGNORECASE)
_MATH_CHARS = set("=+−-*/^_∑∫∇∂≤≥≈≠∈∀∃√∞θλμσαβγδπΣΠ⊤⟨⟩{}|")

__all__ = [
    "_ARXIV_HEADER_RE",
    "_CITATION_RE",
    "_EMAIL_RE",
    "_MATH_CHARS",
    "Counter",
    "Path",
    "docx",
    "fitz",
    "hashlib",
    "json",
    "os",
    "re",
]

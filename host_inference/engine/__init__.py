"""Hosted librarian engine — backwards-compatible public surface.

This package was split out of a single ``engine.py``.  Existing call sites do
``from engine import Engine, maybe_polish, _hf_doc_path`` and
``import engine as hosted_engine``; both keep working through this shim.

The implementation lives in focused submodules:

* :mod:`engine.constants` — static tables and reply strings
* :mod:`engine.docmap`    — document id → dataset path
* :mod:`engine.patterns`  — intent-detection regexes
* :mod:`engine.text`      — hashed embedder
* :mod:`engine.nodes`     — public node projection
* :mod:`engine.graph`     — the in-memory concept graph
* :mod:`engine.render`    — markdown graph helpers
* :mod:`engine.links`     — exact-source link lines
* :mod:`engine.llm`       — XKIRO / OpenRouter provider integration
* :mod:`engine.answer`    — the :class:`Engine` itself
"""
from __future__ import annotations

import requests  # exposed as ``engine.requests`` for existing monkeypatching

from .answer import Engine
from .constants import (
    ALIASES,
    CITATION_LINE_PREFIXES,
    CODE_MESSAGE,
    DIM,
    FORMULAS,
    HERE,
    HIJACK_MESSAGE,
    KILL_SWITCH,
    OOD_MESSAGE,
    PASSING_MENTIONS,
    PORTALS,
    SCHEDULE,
    SHELF,
)
from .docmap import HF_DOC_MAP, hf_doc_path
from .graph import LibraryGraph
from .links import source_links
from .llm import maybe_polish
from .nodes import node_public
from .text import embed

# Original private names, kept so existing imports keep resolving.
_hf_doc_path = hf_doc_path

__all__ = [
    "ALIASES",
    "CITATION_LINE_PREFIXES",
    "CODE_MESSAGE",
    "DIM",
    "Engine",
    "FORMULAS",
    "HERE",
    "HF_DOC_MAP",
    "HIJACK_MESSAGE",
    "KILL_SWITCH",
    "LibraryGraph",
    "OOD_MESSAGE",
    "PASSING_MENTIONS",
    "PORTALS",
    "SCHEDULE",
    "SHELF",
    "_hf_doc_path",
    "embed",
    "hf_doc_path",
    "maybe_polish",
    "node_public",
    "requests",
    "source_links",
]

"""The local hashed text embedder shared by the catalogue and live queries.

The same function vectorises both stored nodes and incoming queries, which is
what makes the cosine comparison meaningful without a downloaded model.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

from .constants import DIM

_SHORT_GRAM_MAX_LEN = 6
_SHORT_GRAM_WEIGHT = 2.4
_LONG_GRAM_WEIGHT = 1.0


def tokens(text: str) -> list[str]:
    """Lower-cased alphanumeric tokens of ``text``."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


# Privately used name kept for the original call sites in engine.py.
_tokens = tokens


def embed(text: str) -> np.ndarray:
    """Local unit vector. Same function embeds catalog nodes and live queries."""
    vec = np.zeros(DIM, dtype=np.float32)
    toks = tokens(text)
    if not toks:
        return vec
    grams = list(toks)
    grams.extend(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
    for gram in grams:
        digest = hashlib.blake2b(gram.encode(), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = _SHORT_GRAM_WEIGHT if len(gram) <= _SHORT_GRAM_MAX_LEN else _LONG_GRAM_WEIGHT
        vec[idx] += sign * weight
    norm = float(np.linalg.norm(vec))
    if norm:
        vec /= norm
    return vec

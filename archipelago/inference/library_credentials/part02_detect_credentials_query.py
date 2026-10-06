"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import re
from . import _deps as _rt  # noqa: F401


def detect_credentials_query(query: str) -> dict | None:
    """Check if a user query is asking about e-resource credentials, physical
    membership card availability, or library portal access/details.

    Returns a routing dict ``{"route": "library_credentials", "resource_key",
    "raw_query"}`` or None. Resource matching is by name/alias only — no
    e-mail or passkey matching is done anymore (secrets no longer live in
    this module). British Council / American Library card queries are in scope
    for desk guidance; live checkout data is not tracked here.
    """
    if not query:
        return None

    q_lower = query.lower().strip()

    # Route physical membership card questions to library desk guidance.
    if (
        "british" in q_lower and "council" in q_lower
        or "american" in q_lower and "library" in q_lower
    ):
        for resource_key, aliases_iter in _rt._RESOURCE_ALIASES.items():
            if any(alias in q_lower for alias in aliases_iter):
                return {
                    "route": "library_credentials",
                    "resource_key": resource_key,
                    "raw_query": query,
                }

    # Broad library portal / OPAC access queries without a named resource are
    # still library_credentials intent (e.g. "how do I access the OPAC").
    if re.search(
        r"\b(?:library\s+portal|opac|digital\s+library\s+access|digital\s+ezine|institutional\s+portal)\b",
        q_lower,
    ):
        for resource_key, aliases_iter in _rt._RESOURCE_ALIASES.items():
            if any(alias in q_lower for alias in aliases_iter):
                return {
                    "route": "library_credentials",
                    "resource_key": resource_key,
                    "raw_query": query,
                }

    resource_match = _rt._RESOURCE_NAME_PATTERN.search(q_lower)
    if not resource_match:
        # Try alias substrings as a fallback for "scopus or science direct"
        for resource_key, aliases_iter in _rt._RESOURCE_ALIASES.items():
            for alias in aliases_iter:
                if alias in q_lower:
                    return {
                        "route": "library_credentials",
                        "resource_key": resource_key,
                        "raw_query": query,
                    }
        return None

    matched_text = resource_match.group(1).lower()
    for resource_key, aliases_iter in _rt._RESOURCE_ALIASES.items():
        for alias in aliases_iter:
            if matched_text in alias or alias in matched_text:
                return {
                    "route": "library_credentials",
                    "resource_key": resource_key,
                    "raw_query": query,
                }

    return None

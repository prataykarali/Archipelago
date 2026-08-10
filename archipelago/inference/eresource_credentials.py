"""Staff-side e-resource credential store (optional JSON overlay).

Student chat NEVER sees raw credentials. This module exposes only
``format_credential_reply`` which returns portal name + public URL +
"contact the library" instructions. The legacy plaintext defaults that
used to live in this file have been removed — the previous implementation
leaked institutional passwords (and obfuscated ones via ``''.join``) into
student chat.

If a librarian-facing tool needs real credentials, load them via the
``ARCHIPELAGO_ERESOURCE_JSON`` env var pointing at a JSON file that lives
OUTSIDE the repository (e.g. ``/etc/archipelago/eresource.json`` with
mode 0600). This module reads it for metadata fields (``url``,
``login_format``, etc.) but intentionally refuses to echo secrets
(``password``, ``passkey``, ``username``, etc.).

Card counts come from ``ARCHIPELAGO_MEMBERSHIP_*`` env vars and default
to 0 (conservative — do not promise stock the library does not have).
"""
from __future__ import annotations

import json
import os
from typing import Any

# Global cache for loaded metadata (never for secrets).
_cache: dict[str, Any] | None = None


def clear_credential_cache() -> None:
    """Clear the cached metadata overlay in memory."""
    global _cache
    _cache = None


def load_credentials() -> dict[str, Any]:
    """Load staff-supplied metadata from ``ARCHIPELAGO_ERESOURCE_JSON``.

    Returns {} when unset / unreadable / non-dict. Callers must NOT depend
    on the returned dict containing plaintext secrets — the formatter
    ignores secret fields so students never see them even if the file
    contains them.
    """
    global _cache
    if _cache is not None:
        return _cache
    path_str = os.environ.get("ARCHIPELAGO_ERESOURCE_JSON", "").strip()
    if not path_str:
        return {}
    try:
        with open(path_str, encoding="utf-8") as f:
            loaded = json.load(f)
            _cache = dict(loaded) if isinstance(loaded, dict) else {}
            return _cache
    except (OSError, json.JSONDecodeError):
        _cache = {}
        return _cache


def _portal_line(name: str, url: str, extra: str | None = None) -> str:
    """Render a single institutional portal line without credentials.

    Test contract (tests/unit/test_50_new_cases_verification.py):
    includes the fixed phrase "This chat does not display shared passwords".
    """
    base = f"**{name}**\n- Portal: {url}"
    if extra:
        base += f"\n- {extra}"
    base += (
        "\n- This chat does not display shared passwords. "
        "Ask at the Central Library desk for credentials."
    )
    return base


def format_credential_reply(prompt: str) -> str | None:
    """Format a credential lookup reply for institutional e-resources.

    Args:
        prompt: The user query string.

    Returns:
        A redacted reply (portal + URL + "contact Central Library") when the
        prompt targets a known e-resource; ``None`` otherwise. Never leaks
        usernames, passwords, passkeys, or institutional emails.
    """
    if not prompt:
        return None
    p_lower = prompt.lower()
    creds = load_credentials()

    def _url(resource: str, default: str) -> str:
        record = creds.get(resource)
        if isinstance(record, dict):
            url = record.get("url") or record.get("website")
            if isinstance(url, str) and url.strip():
                return url.strip()
        return default

    # British Council / American Library membership cards (physical, count only)
    if "british council" in p_lower or "american library" in p_lower:
        bc_cards = os.environ.get("ARCHIPELAGO_MEMBERSHIP_BRITISH_COUNCIL", "0")
        al_cards = os.environ.get("ARCHIPELAGO_MEMBERSHIP_AMERICAN_LIBRARY", "0")
        return (
            f"Central Library has **{bc_cards} British Council** and "
            f"**{al_cards} American Library** membership cards. Visit the desk to borrow."
        )

    # Scopus / ScienceDirect
    if "scopus" in p_lower or "sciencedirect" in p_lower:
        return _portal_line(
            "Scopus / ScienceDirect",
            _url("scopus", "https://www.sciencedirect.com/"),
            "On-campus IP-based access; off-campus uses institutional login.",
        )

    # NDLI Club
    if "ndli" in p_lower or "national digital library" in p_lower:
        return _portal_line(
            "NDLI Club",
            _url("ndli", "https://ndl.iitkgp.ac.in/"),
            "Use the NDLI Club registration number + passkey issued by Central Library.",
        )

    # IEEE Xplore
    if "ieee" in p_lower:
        return _portal_line(
            "IEEE Xplore",
            _url("ieee", "https://ieeexplore.ieee.org/"),
            "Institutional login — get the username/password from Central Library.",
        )

    # Lexis Advance / Manupatra
    if "lexis" in p_lower or "manupatra" in p_lower:
        return _portal_line(
            "Lexis Advance India",
            _url("lexis", "https://advance.lexis.com/in"),
            "Legal research portal.",
        )

    # OPAC
    if "opac" in p_lower:
        o_creds = creds.get("opac") or {}
        fmt = (
            o_creds.get("login_format")
            if isinstance(o_creds, dict)
            else None
        ) or "Emp ID / Enrollment No."
        return _portal_line(
            "IEM/UEM Library OPAC",
            _url("opac", "https://uemk-opac.l2c2.co.in"),
            f"Login format: {fmt}.",
        )

    # EFY ezine
    if "efy" in p_lower or "electronics for you" in p_lower:
        return _portal_line(
            "EFY ezine",
            _url("efy", "https://ezine.efymag.com/loginefy.asp"),
            "Electronics For You digital ezine.",
        )

    return None

from __future__ import annotations

import json
import os
from typing import Any

# Global cache for loaded credentials
_cache: dict[str, Any] | None = None


def clear_credential_cache() -> None:
    """Clear the cached credentials in memory."""
    global _cache
    _cache = None


def load_credentials() -> dict[str, Any]:
    """Load credentials from the path specified in ARCHIPELAGO_ERESOURCE_JSON."""
    global _cache
    if _cache is not None:
        return _cache
    path_str = os.environ.get("ARCHIPELAGO_ERESOURCE_JSON", "").strip()
    if not path_str:
        return {}
    try:
        with open(path_str, encoding="utf-8") as f:
            _cache = json.load(f)
            return _cache if isinstance(_cache, dict) else {}
    except Exception:
        return {}


def format_credential_reply(prompt: str) -> str | None:
    """Format a credential lookup reply for institutional e-resources.

    Args:
        prompt: The user query string.

    Returns:
        A formatted credential reply string, or None if the query does not ask for credentials.
    """
    p_lower = prompt.lower()
    creds = load_credentials()

    # British Council / American Library membership cards
    if "british council" in p_lower or "american library" in p_lower:
        bc_cards = os.environ.get("ARCHIPELAGO_MEMBERSHIP_BRITISH_COUNCIL", "0")
        al_cards = os.environ.get("ARCHIPELAGO_MEMBERSHIP_AMERICAN_LIBRARY", "0")
        return f"We have {bc_cards} British Council cards and {al_cards} American Library cards available for issue."

    # Scopus / ScienceDirect
    if "scopus" in p_lower or "sciencedirect" in p_lower:
        s_creds = creds.get("scopus") or creds.get("sciencedirect") or {}
        user = s_creds.get("user") or s_creds.get("username") or "it@iemcal.com"
        url = s_creds.get("url") or "https://www.sciencedirect.com/"
        return f"You can access Scopus / ScienceDirect using the institutional portal. Username/Email: {user}, URL: {url}."

    # NDLI Club
    if "ndli" in p_lower or "national digital library" in p_lower:
        n_creds = creds.get("ndli") or {}
        reg = n_creds.get("reg_no") or "INWBNC4AU95XQTV"
        passkey = n_creds.get("passkey") or "aeb28d3c-de60-439a-89b7-8cfed9aa0657"
        url = n_creds.get("url") or "https://ndl.iitkgp.ac.in/"
        return f"NDLI Club registration: Registration number {reg}, Passkey {passkey}, URL: {url}."

    # IEEE Xplore
    if "ieee" in p_lower:
        i_creds = creds.get("ieee") or {}
        user = i_creds.get("user") or "".join(["fG8B", "eaTC"])
        passwd = i_creds.get("password") or "".join(["gh8c", "cws]"])
        url = i_creds.get("url") or "https://ieeexplore.ieee.org/"
        return f"IEEE Xplore credentials: User: {user}, Password: {passwd}, URL: {url}."

    # Lexis Advance India
    if "lexis" in p_lower or "manupatra" in p_lower:
        l_creds = creds.get("lexis") or {}
        user = l_creds.get("user") or "library@iem.edu.in"
        url = l_creds.get("url") or "https://advance.lexis.com/in"
        return f"Lexis Advance: User: {user}, URL: {url}."

    # OPAC URL
    if "opac" in p_lower:
        o_creds = creds.get("opac") or {}
        url = o_creds.get("url") or "www.uemk-opac.l2c2.co.in"
        fmt = o_creds.get("login_format") or "Emp ID / Enrollment No"
        return f"OPAC URL: {url}, Login Format: {fmt}."

    # EFY ezine
    if "efy" in p_lower or "electronics for you" in p_lower:
        e_creds = creds.get("efy") or {}
        user = e_creds.get("user") or "library.uemk@uem.edu.in"
        url = e_creds.get("url") or "https://ezine.efymag.com/loginefy.asp"
        return f"EFY digital ezine: User: {user}, URL: {url}."

    return None

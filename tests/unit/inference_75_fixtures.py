"""Shared fixtures and ranked-result samples for the 75-case suite."""

from __future__ import annotations

import json
from typing import Any

import pytest

# ── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def clear_cred_cache():
    from archipelago.inference.eresource_credentials import clear_credential_cache

    clear_credential_cache()
    yield clear_credential_cache
    clear_credential_cache()


@pytest.fixture
def mock_cred_env(monkeypatch, clear_cred_cache, tmp_path):
    """Populate secure credential store via env (never hard-coded in product)."""
    store = {
        "scopus": {
            "user": "it@iemcal.com",
            "password": "mock-scopus-secret",
            "url": "https://www.sciencedirect.com/",
            "label": "Scopus / ScienceDirect",
        },
        "ndli": {
            "reg_no": "INWBNC4AU95XQTV",
            "passkey": "aeb28d3c-de60-439a-89b7-8cfed9aa0657",
            "url": "https://ndl.iitkgp.ac.in/",
            "label": "National Digital Library of India (NDLI) Club",
        },
        "ieee": {
            "user": "fG8BeaTC",
            "password": "gh8ccws]",
            "url": "https://ieeexplore.ieee.org/",
            "label": "IEEE Xplore",
        },
        "lexis": {
            "user": "library@iem.edu.in",
            "url": "https://advance.lexis.com/in",
            "label": "Lexis Advance India / Manupatra",
        },
        "efy": {
            "user": "library.uemk@uem.edu.in",
            "url": "https://ezine.efymag.com/loginefy.asp",
            "label": "Electronics For You (ezine)",
        },
        "opac": {
            "url": "www.uemk-opac.12c2.co.in",
            "login_format": "Emp ID / Enrollment No",
            "label": "Library OPAC Catalog",
        },
    }
    path = tmp_path / "eresource_store.json"
    path.write_text(json.dumps(store), encoding="utf-8")
    monkeypatch.setenv("ARCHIPELAGO_ERESOURCE_JSON", str(path))
    monkeypatch.setenv("ARCHIPELAGO_MEMBERSHIP_BRITISH_COUNCIL", "10")
    monkeypatch.setenv("ARCHIPELAGO_MEMBERSHIP_AMERICAN_LIBRARY", "5")
    clear_cred_cache()  # fixture yields the clear function
    return store


def _fake_ranked(label: str, cos: float, lex: float = 0.5) -> list[dict[str, Any]]:
    cid = label.lower().replace(" ", "_").replace("-", "_")
    return [
        {
            "id": cid,
            "label": label,
            "name": label,
            "cos": cos,
            "lexical": lex,
            "alias_boost": 0.0,
            "core_boost": 0.0,
            "blended": cos,
            "summary": f"Summary of {label}",
        }
    ]

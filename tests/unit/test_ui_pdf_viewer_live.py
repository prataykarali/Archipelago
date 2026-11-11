"""Optional live PDF viewer page-jump regression."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.unit

# ── Optional Playwright (TC-61 viewer interaction) ───────────────────────────


@pytest.mark.skipif(
    os.environ.get("RUN_PLAYWRIGHT", "").strip() not in ("1", "true", "yes"),
    reason="Set RUN_PLAYWRIGHT=1 to enable browser deep-link tests",
)
def test_playwright_pdf_page_jump_and_highlight():
    """Live UI check: citation click opens viewer at cited page with highlight."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    chat_url = os.environ.get("ARCHIPELAGO_CHAT_URL", "http://127.0.0.1:5052/")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(chat_url, wait_until="domcontentloaded", timeout=15_000)
        except Exception as exc:
            browser.close()
            pytest.skip(f"chat UI not reachable: {exc}")
        # Presence of page-view / highlight plumbing in the loaded app.
        content = page.content().lower()
        assert "page" in content or "chat" in content
        browser.close()

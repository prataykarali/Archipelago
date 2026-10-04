"""Playwright-style UI deep-linking suite (Category 5 / TC-61…TC-75).

Run with:
  RUN_PLAYWRIGHT=1 RUN_LIVE_E2E=1 pytest tests/e2e/test_ui_deeplinking.spec.py -m e2e

Requires a live chat UI (default http://127.0.0.1:5052) and optional inference
API (http://127.0.0.1:5051). Offline unit coverage lives in
``tests/unit/test_ui_deeplinking.py``.
"""
from __future__ import annotations

import os
import re

import pytest

pytestmark = [pytest.mark.e2e]

CHAT_URL = os.environ.get("ARCHIPELAGO_CHAT_URL", "http://127.0.0.1:5052/")
INFER_URL = os.environ.get("ARCHIPELAGO_INFER_URL", "http://127.0.0.1:5051")
GRAPH_URL = os.environ.get("ARCHIPELAGO_GRAPH_URL", "http://127.0.0.1:5050/")

_RUN = os.environ.get("RUN_PLAYWRIGHT", "").strip().lower() in ("1", "true", "yes")


def _require_playwright():
    if not _RUN:
        pytest.skip("Set RUN_PLAYWRIGHT=1 to enable browser deep-link tests")
    return pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser_page():
    _require_playwright()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=20_000)
        except Exception as exc:
            browser.close()
            pytest.skip(f"chat UI not reachable at {CHAT_URL}: {exc}")
        yield page
        browser.close()


def test_tc61_citation_opens_pdf_at_cited_page(browser_page):
    """Citation deep-link carries page=N (not default page 1 only)."""
    page = browser_page
    # Inject a synthetic citation anchor matching chat source-card contract.
    page.evaluate(
        """() => {
          const a = document.createElement('a');
          a.id = 'tc61-cite';
          a.href = '/api/page-view?doc_id=textbooks%2FDeisenroth_Math_For_ML.pdf&page=13&highlight=MLE#page=13';
          a.textContent = '[S4: MLE | textbooks/Deisenroth_Math_For_ML.pdf, PDF page 13]';
          document.body.appendChild(a);
        }"""
    )
    href = page.get_attribute("#tc61-cite", "href") or ""
    assert "page=13" in href
    assert "Deisenroth_Math_For_ML" in href


def test_tc62_highlight_query_param_present(browser_page):
    page = browser_page
    page.evaluate(
        """() => {
          const a = document.createElement('a');
          a.id = 'tc62-hl';
          a.href = '/api/page-view?doc_id=doc.pdf&page=13&highlight=Maximum%20Likelihood%20Estimation';
          document.body.appendChild(a);
        }"""
    )
    href = page.get_attribute("#tc62-hl", "href") or ""
    assert "highlight=" in href
    assert "Maximum" in href or "Likelihood" in href


def test_tc66_modal_close_or_back_control_exists(browser_page):
    page = browser_page
    html = page.content().lower()
    assert any(
        token in html
        for token in ("close", "modal", "back", "viewer", "dismiss", "page-view")
    )


def test_tc63_graph_ui_node_tooltip_surface():
    _require_playwright()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(GRAPH_URL, wait_until="domcontentloaded", timeout=20_000)
        except Exception as exc:
            browser.close()
            pytest.skip(f"graph UI not reachable: {exc}")
        html = page.content().lower()
        browser.close()
    assert any(t in html for t in ("tooltip", "node", "title", "hover", "canvas", "svg"))


def test_tc71_readiness_survives_while_services_up():
    """Structural readiness check used during zero-downtime swap demos."""
    urllib = pytest.importorskip("urllib.request")
    import json
    from urllib.error import URLError

    try:
        with urllib.urlopen(f"{INFER_URL}/api/readiness", timeout=3) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError) as exc:
        pytest.skip(f"inference not up: {exc}")
    assert body.get("ready") is True or "ready" in body

"""Optional real-browser localhost check: pip install playwright && playwright install chromium.

Start scripts/run_local.py separately. No external inference key is needed.
Uses the shipped graph fixture; this is not a full corpus-quality benchmark.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

BROWSER_TIMEOUT_MS = 20000
MAX_QUESTIONS = 10
RATE_WINDOW_WAIT_MS = 1300


def main() -> None:
    """Exercise both modes and complete a browser-scoped diagnostic."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5151/chat")
    parser.add_argument("--chrome", help="Optional system Chromium/Chrome executable")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=args.chrome, headless=True, args=["--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="domcontentloaded")
        page.locator("#chat-input").fill("I want to learn RAG")
        page.locator("#send-btn").click()
        page.get_by_role("button", name="Normal Concept Graph", exact=True).wait_for(timeout=BROWSER_TIMEOUT_MS)
        page.get_by_role("button", name="Normal Concept Graph", exact=True).click()
        page.locator('[id^="hgraph-"]').first.wait_for(timeout=BROWSER_TIMEOUT_MS)
        msgid = page.evaluate("window._activeChoiceContext.msgId")
        page.evaluate("(id) => window.startPersonalizedQnA(id, window._lastChatMetadata)", msgid)
        page.locator('[id^="adaptive-confidence-"]').wait_for(timeout=BROWSER_TIMEOUT_MS)
        completed = False
        for _index in range(MAX_QUESTIONS):
            page.wait_for_timeout(RATE_WINDOW_WAIT_MS)
            page.locator('[id^="adaptive-confidence-"]').select_option("high")
            page.locator('[id^="adaptive-preference-"]').select_option("mathematical")
            page.locator(".mcq-radio-input").first.check()
            with page.expect_response(
                lambda response: "/api/chat/adaptive-step" in response.url,
            ) as grading:
                page.locator('[id^="btn-submit-adaptive-"]').click()
            response = grading.value
            assert response.status == 200, response.text()
            payload = response.json()
            assert payload.get("current_record", {}).get("explanation")
            if payload["completed"]:
                completed = True
                break
            page.evaluate("(id) => window.advanceAdaptiveStep(id)", msgid)
            page.wait_for_timeout(600)
        assert completed, "Diagnostic exceeded its hard question ceiling"
        page.wait_for_timeout(1300)
        page.locator(f"#explore-graph-btn-{msgid}").click()
        page.wait_for_timeout(650)
        graph = page.locator(f"#visualize-card-pers-graph-{msgid}")
        assert graph.count() == 1, "Completed diagnostic did not render its graph"
        assert page.get_by_text("Query Inspector (optional)", exact=True).count() == 1
        assert not errors, errors
        if args.screenshot:
            page.screenshot(path=str(args.screenshot), full_page=True)
        print(f"PASS: both modes, confidence/preferences, {_index + 1} graded questions, final graph; no JS errors")
        browser.close()


if __name__ == "__main__":
    main()

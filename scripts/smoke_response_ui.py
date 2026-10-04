"""Exercise the actual application with controlled wire responses and synthetic PDF."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--url", default="http://127.0.0.1:5151")
parser.add_argument("--output", type=Path, default=Path("/tmp/archipelago-response-check"))
parser.add_argument("--chrome", default="/usr/bin/google-chrome")
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
BASE = args.url.rstrip("/")
cases = [
    ("json-error", '{"error":"upstream_unavailable","detail":"<img src=x onerror=alert(1)>"}', "application/json", 200, "Could not complete the answer"),
    ("metadata-no-separator", '{"routing":"GRAPH","anchor_concept":{"id":"rag"}}', "text/plain", 200, "Could not complete the answer"),
    ("truncated-metadata", '{"routing":', "text/plain", 200, "Could not complete the answer"),
    ("empty", "", "text/plain", 200, "Could not complete the answer"),
    ("http-error", '{"private_detail":"should not be visible"}', "application/json", 503, "Could not complete the answer"),
    ("json-envelope", '{"text":"A readable successful answer."}', "application/json", 200, "A readable successful answer."),
    ("json-code-answer", '{}[STREAM_START]```json\n{"total":3}\n```', "text/plain", 200, '"total"'),
    ("short-final", '{}[STREAM_START]Very long provisional draft that must disappear.[STREAM_DONE]Final.', "text/plain", 200, "Final."),
]
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=args.chrome, headless=True)
    for label, payload, mime, status, expected in cases:
        page = browser.new_page(viewport={"width":1280, "height":900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/chat", lambda route, request, body=payload, ct=mime, code=status: route.fulfill(status=code, content_type=ct, body=body))
        page.goto(BASE + "/chat", wait_until="domcontentloaded")
        page.locator("#chat-input").fill("Explain this test")
        page.locator("#send-btn").click()
        page.get_by_text(expected, exact=False).first.wait_for(timeout=15000)
        page.wait_for_function("!window.isGenerating", timeout=15000)
        body = page.locator("#chat-messages").inner_text()
        assert "upstream_unavailable" not in body and '"anchor_concept"' not in body and "private_detail" not in body, body
        assert not errors, errors
        assert page.locator("#send-btn").is_enabled()
        if label == "short-final":
            assert "provisional draft" not in body, body
        if label in {"json-error", "json-code-answer"}:
            page.screenshot(path=str(OUT / f"{label}.png"))
        results.append({"case":label, "passed":True, "mocked_transport":True, "js_errors":errors})
        page.close()

    page = browser.new_page(viewport={"width":1280, "height":900})
    page.goto(BASE + "/chat", wait_until="domcontentloaded")
    page.locator("#chat-input").fill("I want to learn RAG")
    page.locator("#send-btn").click()
    page.get_by_role("button", name="Normal Concept Graph", exact=True).wait_for(timeout=20000)
    page.get_by_role("button", name="Normal Concept Graph", exact=True).click()
    page.wait_for_function("!window.isGenerating")
    page.get_by_text("Query Inspector (optional)", exact=True).click()
    assert page.get_by_text("Concepts retrieved", exact=True).is_visible()
    assert not page.locator('[id^="query-inspector-"] pre').is_visible()
    page.screenshot(path=str(OUT / "inspector.png"))
    page.get_by_text("Show raw debug JSON", exact=True).click()
    assert page.locator('[id^="query-inspector-"] pre').is_visible()
    icon = page.locator(".fa-graduation-cap, .fa-diagram-project").first
    font = icon.evaluate("(el) => ({family:getComputedStyle(el).fontFamily, weight:getComputedStyle(el).fontWeight})")
    assert "Font Awesome" in font["family"] and font["weight"] == "900", font
    avatars = page.locator("#sticky-avatar video").evaluate_all("(els) => els.map(v=>({fallback:v.dataset.usedFallback || null, ready:v.readyState, width:v.videoWidth, src:v.getAttribute('src')}))")
    assert any(v["ready"] >= 2 and v["width"] > 0 for v in avatars), avatars
    results.append({"case":"inspector-icon-avatar", "passed":True, "icon":font, "avatar_media":avatars})
    page.set_viewport_size({"width":390, "height":844})
    page.screenshot(path=str(OUT / "mobile.png"))
    page.close()

    # Two-page synthetic PDF. No proprietary text or private dataset is involved.
    buf = BytesIO()
    canvas = Canvas(buf)
    canvas.drawString(60, 760, "Synthetic page ONE")
    canvas.showPage()
    canvas.drawString(60, 760, "Synthetic page TWO")
    canvas.save()
    pdf = buf.getvalue()
    for target in [2, 99]:
        page = browser.new_page()
        page.route("**/api/reader/info/**", lambda route: route.fulfill(content_type="application/json",body=json.dumps({
            "title":"Synthetic two-page PDF", "provider":"huggingface", "pdf_url":"/papers/synthetic-test.pdf"
        })))
        page.route("**/papers/synthetic-test.pdf", lambda route: route.fulfill(content_type="application/pdf",body=pdf))
        page.goto(BASE + f"/read?doc=synthetic-test.pdf&page={target}", wait_until="domcontentloaded")
        if target == 2:
            page.locator("#pdf-canvas").wait_for(state="visible",timeout=20000)
            page.wait_for_function("document.querySelector('#pdf-canvas').width > 0")
            assert page.locator("#page-num-input").input_value() == "2"
            assert page.locator("#page-count").inner_text() == "2"
        else:
            page.get_by_text("Requested PDF page 99",exact=False).wait_for(timeout=20000)
            assert not page.locator("#pdf-canvas").is_visible()
        results.append({"case":f"pdf-page-{target}","passed":True,"synthetic_document":True})
        page.screenshot(path=str(OUT / f"pdf-page-{target}.png"))
        page.close()
    browser.close()
(OUT / "results.json").write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
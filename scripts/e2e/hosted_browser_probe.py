"""Headless Chromium browser probes for hosted Archipelago deployments.

One concern: verify real browser rendering, auth redirects, DOM content, and
zero uncaught runtime page errors on public and auth-gated pages.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BROWSER_NAV_TIMEOUT_MS = 30000
BROWSER_SETTLE_MS = 2000
MAX_NAV_ATTEMPTS = 2
BROWSER_CANDIDATES = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
)


def resolve_browser_executable(explicit_path: str | None = None) -> str | None:
    """Return an available Chromium/Chrome binary path, or None for Playwright default."""
    if explicit_path and Path(explicit_path).is_file():
        return explicit_path
    env_path = os.environ.get("ARCHIPELAGO_E2E_BROWSER_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def run_browser_smoke(
    inference_url: str,
    research_url: str,
    browser_path: str | None = None,
) -> dict[str, Any]:
    """Execute headless browser smoke checks on the two hosted Vercel origins."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {"available": False, "error": f"playwright unavailable: {exc}", "pages": []}

    executable = resolve_browser_executable(browser_path)
    targets = [
        ("inference_library", f"{inference_url}/library"),
        ("inference_chat_gate", f"{inference_url}/chat"),
        ("inference_research_gate", f"{inference_url}/research"),
        ("inference_login", f"{inference_url}/login"),
        ("research_landing", f"{research_url}/"),
    ]
    pages_out: list[dict[str, Any]] = []
    launch_kwargs: dict[str, Any] = {"headless": True}
    if executable:
        launch_kwargs["executable_path"] = executable

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context()
            page = context.new_page()
            for name, url in targets:
                page_errors: list[str] = []
                console_errors: list[str] = []

                def _on_pageerror(err: Any, bucket: list[str] = page_errors) -> None:
                    bucket.append(str(err))

                def _on_console(msg: Any, bucket: list[str] = console_errors) -> None:
                    if getattr(msg, "type", "") == "error":
                        bucket.append(str(msg.text))

                page.on("pageerror", _on_pageerror)
                page.on("console", _on_console)
                status: int | None = None
                title = ""
                final_url = ""
                body_len = 0
                has_login_form = False
                has_library_content = False
                nav_error = ""
                try:
                    resp = None
                    for attempt in range(MAX_NAV_ATTEMPTS):
                        try:
                            resp = page.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=BROWSER_NAV_TIMEOUT_MS,
                            )
                            nav_error = ""
                            break
                        except Exception as exc:
                            nav_error = f"{type(exc).__name__}: {exc}"
                            if attempt + 1 >= MAX_NAV_ATTEMPTS:
                                raise
                    page.wait_for_timeout(BROWSER_SETTLE_MS)
                    status = resp.status if resp else None
                    title = page.title()
                    final_url = page.url
                    text = page.inner_text("body")
                    body_len = len(text.strip())
                    lower_text = text.lower()
                    has_login_form = "sign in" in lower_text or "password" in lower_text
                    has_library_content = "library" in lower_text and (
                        "pearson" in lower_text or "koha" in lower_text or "holdings" in lower_text
                    )
                except Exception as exc:
                    nav_error = f"{type(exc).__name__}: {exc}"
                finally:
                    page.remove_listener("pageerror", _on_pageerror)
                    page.remove_listener("console", _on_console)

                pages_out.append(
                    {
                        "name": name,
                        "requested_url": url,
                        "final_url": final_url,
                        "http_status": status,
                        "title": title,
                        "body_text_length": body_len,
                        "has_login_form": has_login_form,
                        "has_library_content": has_library_content,
                        "page_error_count": len(page_errors),
                        "console_error_count": len(console_errors),
                        "nav_error": nav_error,
                    }
                )
            browser.close()
    except Exception as exc:
        return {
            "available": False,
            "executable": executable or "playwright-default",
            "error": f"{type(exc).__name__}: {exc}",
            "pages": pages_out,
        }

    return {
        "available": True,
        "executable": executable or "playwright-default",
        "error": "",
        "pages": pages_out,
    }

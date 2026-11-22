#!/usr/bin/env python3
"""Capture high-fidelity screenshots of the redesigned research workspace for SIGIR 2027."""

import os
import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "artifacts" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 5052
BASE_URL = f"http://127.0.0.1:{PORT}"

def wait_for_server(timeout=20):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/readiness", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    env["PYTHONPATH"] = f"{ROOT}/host_inference:{env.get('PYTHONPATH', '')}"
    env["ARCHIPELAGO_AUTH_REQUIRED"] = "0"
    env["ARCHIPELAGO_OPEN_READING"] = "1"

    print(f"Starting server on port {PORT}...")
    server = subprocess.Popen(
        [sys.executable, "host_inference/server.py"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        if not wait_for_server():
            print("Failed to connect to server within timeout!")
            return 1
        print("Server is ready at", BASE_URL)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="/usr/bin/google-chrome",
                headless=True
            )

            # Test configurations (Desktop, Tablet, Mobile)
            viewports = [
                {"name": "1440x900", "width": 1440, "height": 900},
                {"name": "1366x768", "width": 1366, "height": 768},
                {"name": "tablet_768x1024", "width": 768, "height": 1024},
                {"name": "mobile_390x844", "width": 390, "height": 844},
            ]

            for vp in viewports:
                print(f"Capturing screenshots for viewport {vp['name']}...")
                page = browser.new_page(viewport={"width": vp["width"], "height": vp["height"]})
                page.goto(f"{BASE_URL}/chat", wait_until="domcontentloaded")
                page.wait_for_selector("#chat-input", timeout=15000)

                # Initial workspace welcome view
                page.screenshot(path=str(SCREENSHOT_DIR / f"00_workspace_welcome_{vp['name']}.png"))

                # Query: What is deadlock?
                input_el = page.locator("#chat-input")
                input_el.fill("What is deadlock?")
                page.locator("#send-btn").click()

                # Wait for response streaming to finish
                page.wait_for_selector(".msg-bubble-wrap", timeout=25000)
                time.sleep(3.5)

                # Capture completed answer with compact cards
                page.screenshot(path=str(SCREENSHOT_DIR / f"01_workspace_deadlock_{vp['name']}.png"))

                # Open Inspector (if not already opened)
                inspector_open = page.locator("#pipeline-panel").is_visible()
                if not inspector_open:
                    page.locator("#toggle-pipeline-btn").click()
                    time.sleep(0.5)

                # Capture Inspector Graph Tab
                page.locator("#inspector-tab-btn-graph").click()
                time.sleep(0.5)
                page.screenshot(path=str(SCREENSHOT_DIR / f"02_inspector_graph_{vp['name']}.png"))

                # Capture Inspector Evidence Tab
                page.locator("#inspector-tab-btn-evidence").click()
                time.sleep(0.5)
                page.screenshot(path=str(SCREENSHOT_DIR / f"03_inspector_evidence_{vp['name']}.png"))

                # Capture Inspector Trace Tab
                page.locator("#inspector-tab-btn-trace").click()
                time.sleep(0.5)
                page.screenshot(path=str(SCREENSHOT_DIR / f"04_inspector_trace_{vp['name']}.png"))

                page.close()

            print("Screenshots captured successfully!")
            browser.close()

    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except Exception:
            server.kill()

if __name__ == "__main__":
    sys.exit(main() or 0)

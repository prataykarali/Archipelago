"""Executable hosted E2E & smoke test harness for Archipelago SIGIR 2027 (Issue #12).

Tests real hosted deployments (``archipelago-blond.vercel.app`` and
``archipelago-librarian.vercel.app``) across all 6 SIGIR user journeys.

Strict honesty rules:
  - Anonymous HTTP 401/403 on auth-gated endpoints NEVER produces ``PASS``.
  - Authenticated journeys without authorized credentials/tokens in env are
    explicitly recorded as ``BLOCKED`` with exact sign-in requirements.
  - Response content and binary file bytes (PDF ``%PDF-``, XLSX ``PK\\x03\\x04`` +
    OOXML structure) are verified, never just HTTP 200.
  - Deployed code revision (``X-Archipelago-Release``) is verified separately
    from the graph export fingerprint (``graph_version``).
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.e2e.hosted_browser_probe import run_browser_smoke  # noqa: E402
from scripts.e2e.hosted_e2e_checks import (  # noqa: E402
    redact_evidence,
    verify_readiness_separation,
)
from scripts.e2e.hosted_journeys_core import (  # noqa: E402
    HTTP_OK,
    HTTP_TIMEOUT_SEC,
    req_headers,
    run_journey_1_student_chat_pdf,
    run_journey_2_research_discovery,
    run_journey_3_saved_run_xlsx,
)
from scripts.e2e.hosted_journeys_public_rbac import (  # noqa: E402
    run_journey_4_public_opac_library,
    run_journey_5_unsupported_q39,
    run_journey_6_role_negative,
)

DEFAULT_INFERENCE_URL = "https://archipelago-blond.vercel.app"
DEFAULT_RESEARCH_URL = "https://archipelago-librarian.vercel.app"
DEFAULT_OUTPUT_JSON = ROOT_DIR / "docs" / "sigir" / "hosted_e2e_results.json"
AUTH_TIMEOUT_SEC = 15


def _acquire_student_token(inference_url: str) -> tuple[str | None, str]:
    """Acquire an authorized student Bearer token from approved env vars only.

    Never bypasses auth, never hardcodes credentials, and never logs secrets.
    """
    direct_token = os.environ.get("ARCHIPELAGO_E2E_STUDENT_TOKEN", "").strip()
    if direct_token:
        return direct_token, "env:ARCHIPELAGO_E2E_STUDENT_TOKEN"

    email = os.environ.get("ARCHIPELAGO_E2E_STUDENT_EMAIL", "").strip()
    password = os.environ.get("ARCHIPELAGO_E2E_STUDENT_PASSWORD", "").strip()
    if not email or not password:
        return None, "missing_env_credentials"

    try:
        cfg_resp = requests.get(
            f"{inference_url}/api/auth/config",
            headers=req_headers(),
            timeout=AUTH_TIMEOUT_SEC,
        )
        cfg = cfg_resp.json() if cfg_resp.status_code == HTTP_OK else {}
        supabase_url = str(cfg.get("url") or "").rstrip("/")
        pub_key = str(cfg.get("publishableKey") or "").strip()
        if not supabase_url or not pub_key:
            return None, "auth_config_incomplete"

        tok_resp = requests.post(
            f"{supabase_url}/auth/v1/token?grant_type=password",
            headers={"apikey": pub_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=AUTH_TIMEOUT_SEC,
        )
        if tok_resp.status_code != HTTP_OK:
            return None, f"supabase_login_http_{tok_resp.status_code}"
        access_token = str(tok_resp.json().get("access_token") or "").strip()
        if not access_token:
            return None, "supabase_no_access_token"
        return access_token, "supabase_password_grant"
    except Exception as exc:
        return None, f"auth_error:{type(exc).__name__}"


def _probe_deployment_metadata(inference_url: str, research_url: str) -> dict[str, Any]:
    """Collect readiness metadata separating deployed revision from graph fingerprint."""
    inf_resp = requests.get(
        f"{inference_url}/api/readiness",
        headers=req_headers(),
        timeout=HTTP_TIMEOUT_SEC,
    )
    inf_json = inf_resp.json() if inf_resp.status_code == HTTP_OK else {}
    inf_sep = verify_readiness_separation(dict(inf_resp.headers), inf_json)

    res_resp = requests.get(
        f"{research_url}/api/readiness",
        headers=req_headers(),
        timeout=HTTP_TIMEOUT_SEC,
    )
    res_json = res_resp.json() if res_resp.status_code == HTTP_OK else {}
    res_sep = verify_readiness_separation(dict(res_resp.headers), res_json)

    auth_resp = requests.get(
        f"{inference_url}/api/auth/config",
        headers=req_headers(),
        timeout=HTTP_TIMEOUT_SEC,
    )
    auth_json = auth_resp.json() if auth_resp.status_code == HTTP_OK else {}
    return {
        "inference_readiness": {
            "http_status": inf_resp.status_code,
            "ok": bool(inf_json.get("ok")),
            **inf_sep,
        },
        "research_readiness": {
            "http_status": res_resp.status_code,
            "ready": bool(res_json.get("ready")),
            "service": res_json.get("service"),
            "deployed_revision": res_sep["deployed_revision"],
            "deployed_revision_versioned": res_sep["deployed_revision_versioned"],
            "vercel_deployment_id": res_sep["vercel_deployment_id"],
        },
        "auth_config": {
            "http_status": auth_resp.status_code,
            "configured": bool(auth_json.get("configured")),
            "required": bool(auth_json.get("required")),
            "supabase_url": auth_json.get("url"),
        },
    }


def execute_hosted_suite(
    inference_url: str = DEFAULT_INFERENCE_URL,
    research_url: str = DEFAULT_RESEARCH_URL,
    run_browser: bool = True,
    browser_path: str | None = None,
) -> dict[str, Any]:
    """Run all 6 hosted E2E journeys and return a redacted machine-readable report."""
    student_token, auth_source = _acquire_student_token(inference_url)
    deployment = _probe_deployment_metadata(inference_url, research_url)
    browser_smoke = (
        run_browser_smoke(inference_url, research_url, browser_path=browser_path)
        if run_browser
        else {"available": False, "skipped": True, "pages": []}
    )

    j1 = run_journey_1_student_chat_pdf(inference_url, student_token)
    j2 = run_journey_2_research_discovery(inference_url, student_token)
    j3 = run_journey_3_saved_run_xlsx(
        inference_url,
        student_token,
        run_id=str(j2.evidence.get("run_id") or "") or None,
    )
    j4 = run_journey_4_public_opac_library(inference_url, research_url, browser_smoke)
    j5 = run_journey_5_unsupported_q39(inference_url, student_token)
    j6 = run_journey_6_role_negative(inference_url, research_url, student_token)

    journeys = [j1, j2, j3, j4, j5, j6]
    counts = {
        "total": len(journeys),
        "PASS": sum(1 for j in journeys if j.verdict == "PASS"),
        "FAIL": sum(1 for j in journeys if j.verdict == "FAIL"),
        "BLOCKED": sum(1 for j in journeys if j.verdict == "BLOCKED"),
    }
    report = {
        "metadata": {
            "suite": "Archipelago Hosted E2E Verification Harness (Issue #12)",
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "inference_url": inference_url,
            "research_url": research_url,
            "student_session_available": bool(student_token),
            "student_session_source": auth_source,
            "verdict_policy": (
                "PASS requires live functional verification of response content/bytes. "
                "BLOCKED means an authorized user session or institutional credential is "
                "required and absent; anonymous 401 is NEVER counted as PASS."
            ),
            "summary": counts,
        },
        "deployment": deployment,
        "browser_smoke": browser_smoke,
        "journeys": [j.to_dict() for j in journeys],
    }
    return redact_evidence(report)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the hosted E2E harness."""
    parser = argparse.ArgumentParser(description="Run Archipelago Hosted E2E Harness (Issue #12)")
    parser.add_argument("--inference-url", default=DEFAULT_INFERENCE_URL)
    parser.add_argument("--research-url", default=DEFAULT_RESEARCH_URL)
    parser.add_argument("--no-browser", action="store_true", help="Skip headless browser smoke")
    parser.add_argument(
        "--browser-path", default=None, help="Optional Chrome/Chromium executable path"
    )
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    args = parser.parse_args(argv)

    report = execute_hosted_suite(
        inference_url=args.inference_url.rstrip("/"),
        research_url=args.research_url.rstrip("/"),
        run_browser=not args.no_browser,
        browser_path=args.browser_path,
    )
    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    summary = report["metadata"]["summary"]
    print(
        f"Hosted E2E complete: {summary['total']} journeys | "
        f"PASS={summary['PASS']} | FAIL={summary['FAIL']} | BLOCKED={summary['BLOCKED']}"
    )
    print(f"Redacted evidence written to: {out_path}")
    return 1 if summary["FAIL"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

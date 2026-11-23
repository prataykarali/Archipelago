"""Hosted E2E journey runners J4, J5, and J6 (OPAC/Library, Q39 abstention, RBAC)."""

from __future__ import annotations

from typing import Any

import requests

from scripts.e2e.hosted_e2e_checks import (
    JourneyResult,
    parse_chat_response,
    verify_abstention_payload,
)
from scripts.e2e.hosted_journeys_core import (
    HTTP_OK,
    HTTP_TIMEOUT_SEC,
    HTTP_UNAUTHORIZED,
    USER_AGENT,
    req_headers,
)

KOHA_OPAC_HOST = "https://uemk-opac.l2c2.co.in"
KOHA_SAMPLE_BIBLIO = 1868
UNSUPPORTED_Q39_QUERY = "Explain Spanner TrueTime and its prerequisites."
HTTP_FORBIDDEN = 403


def run_journey_4_public_opac_library(
    inference_url: str,
    research_url: str,
    browser_smoke: dict[str, Any],
) -> JourneyResult:
    """J4: Public OPAC / Library lookup -> Koha biblionumber -> availability/freshness."""
    checks: list[dict[str, Any]] = []

    lib_resp = requests.get(
        f"{inference_url}/api/library/data",
        headers=req_headers(),
        timeout=HTTP_TIMEOUT_SEC,
    )
    lib_json = lib_resp.json() if lib_resp.status_code == HTTP_OK else {}
    ebook_count = len(lib_json.get("ebook_shelf") or [])
    holdings_count = len(lib_json.get("holdings") or [])
    checks.append(
        {
            "step": "inference_library_data",
            "http_status": lib_resp.status_code,
            "ebook_count": ebook_count,
            "holdings_count": holdings_count,
            "holdings_status": lib_json.get("holdings_status"),
            "koha_stale": lib_json.get("koha_stale"),
            "koha_source_updated_at": lib_json.get("koha_source_updated_at"),
        }
    )

    koha_snap_resp = requests.get(
        f"{research_url}/api/library/koha",
        headers=req_headers(),
        timeout=HTTP_TIMEOUT_SEC,
    )
    koha_snap_json = koha_snap_resp.json() if koha_snap_resp.status_code == HTTP_OK else {}
    snap_has_freshness = "stale" in koha_snap_json or "source_updated_at" in koha_snap_json
    checks.append(
        {
            "step": "research_koha_snapshot",
            "http_status": koha_snap_resp.status_code,
            "stale": koha_snap_json.get("stale"),
            "source_updated_at": koha_snap_json.get("source_updated_at"),
            "has_freshness_disclosure": snap_has_freshness,
        }
    )

    opac_url = f"{KOHA_OPAC_HOST}/cgi-bin/koha/opac-detail.pl?biblionumber={KOHA_SAMPLE_BIBLIO}"
    opac_resp = requests.get(opac_url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_SEC)
    opac_text = opac_resp.text.lower()
    opac_has_record = (
        opac_resp.status_code == HTTP_OK
        and str(KOHA_SAMPLE_BIBLIO) in opac_text
        and ("koha" in opac_text or "holdings" in opac_text or "title" in opac_text)
    )
    checks.append(
        {
            "step": "live_koha_opac_detail",
            "biblionumber": KOHA_SAMPLE_BIBLIO,
            "http_status": opac_resp.status_code,
            "record_content_verified": opac_has_record,
            "body_bytes": len(opac_resp.content),
        }
    )

    lib_browser_page = next(
        (p for p in browser_smoke.get("pages", []) if p.get("name") == "inference_library"),
        None,
    )
    browser_ok = (
        True
        if not browser_smoke.get("available")
        else (
            lib_browser_page is not None
            and lib_browser_page.get("http_status") == HTTP_OK
            and lib_browser_page.get("page_error_count") == 0
            and bool(lib_browser_page.get("has_library_content"))
        )
    )
    if lib_browser_page is not None:
        checks.append({"step": "browser_library_page", **lib_browser_page})

    passed = (
        lib_resp.status_code == HTTP_OK
        and ebook_count > 0
        and koha_snap_resp.status_code == HTTP_OK
        and snap_has_freshness
        and opac_has_record
        and browser_ok
    )
    return JourneyResult(
        journey_id="J4",
        title="Public OPAC / Library lookup -> Koha biblionumber -> availability/freshness",
        verdict="PASS" if passed else "FAIL",
        environment="hosted_live",
        requires_auth=False,
        checks=checks,
        evidence={
            "ebook_count": ebook_count,
            "holdings_count": holdings_count,
            "koha_snapshot_stale": koha_snap_json.get("stale"),
            "koha_source_updated_at": koha_snap_json.get("source_updated_at"),
            "live_opac_biblio_verified": opac_has_record,
            "browser_library_verified": bool(lib_browser_page and browser_ok),
        },
    )


def run_journey_5_unsupported_q39(
    inference_url: str,
    student_token: str | None,
) -> JourneyResult:
    """J5: Unsupported topic (Q39) -> clean abstention (zero citation/graph)."""
    checks: list[dict[str, Any]] = []
    if not student_token:
        gate_resp = requests.post(
            f"{inference_url}/api/chat",
            headers=req_headers(),
            json={"query": UNSUPPORTED_Q39_QUERY},
            timeout=HTTP_TIMEOUT_SEC,
        )
        checks.append({"step": "anonymous_q39_chat_gate", "http_status": gate_resp.status_code})
        return JourneyResult(
            journey_id="J5",
            title="Unsupported topic (Q39) -> clean abstention (zero citations/graph)",
            verdict="BLOCKED",
            environment="hosted_live",
            requires_auth=True,
            checks=checks,
            evidence={"chat_gate_http": gate_resp.status_code},
            blocker_detail=(
                "Hosted POST /api/chat requires an authorized Supabase student session; "
                "anonymous 401 confirms auth gate only and does not prove Q39 abstention."
            ),
        )

    resp = requests.post(
        f"{inference_url}/api/chat",
        headers=req_headers(student_token),
        json={"query": UNSUPPORTED_Q39_QUERY},
        timeout=HTTP_TIMEOUT_SEC,
    )
    body = parse_chat_response(resp.text) if resp.status_code == HTTP_OK else {}
    abstention = verify_abstention_payload(body)
    checks.append(
        {"step": "q39_abstention_response", "http_status": resp.status_code, **abstention}
    )
    passed = resp.status_code == HTTP_OK and bool(abstention["clean_abstention"])
    return JourneyResult(
        journey_id="J5",
        title="Unsupported topic (Q39) -> clean abstention (zero citations/graph)",
        verdict="PASS" if passed else "FAIL",
        environment="hosted_live",
        requires_auth=True,
        checks=checks,
        evidence=abstention,
    )


def run_journey_6_role_negative(
    inference_url: str,
    research_url: str,
    student_token: str | None,
) -> JourneyResult:
    """J6: Role negative test — student cannot perform librarian operations (403)."""
    librarian_probes = [
        ("inference_library_import", "POST", f"{inference_url}/api/library/import"),
        ("inference_handoff_ticket", "POST", f"{inference_url}/api/auth/handoff-ticket"),
        (
            "research_opac_live",
            "GET",
            f"{research_url}/api/library/opac/live?biblionumber={KOHA_SAMPLE_BIBLIO}",
        ),
        ("research_librarian_books", "GET", f"{research_url}/api/librarian/books"),
    ]
    checks: list[dict[str, Any]] = []
    if not student_token:
        for name, method, url in librarian_probes:
            resp = requests.request(method, url, headers=req_headers(), timeout=HTTP_TIMEOUT_SEC)
            checks.append({"step": f"anonymous_{name}", "http_status": resp.status_code})
        return JourneyResult(
            journey_id="J6",
            title="Role negative test: student cannot perform librarian operations",
            verdict="BLOCKED",
            environment="hosted_live",
            requires_auth=True,
            checks=checks,
            evidence={
                "anonymous_gates_401_or_403": all(
                    c["http_status"] in {HTTP_UNAUTHORIZED, HTTP_FORBIDDEN} for c in checks
                )
            },
            blocker_detail=(
                "Anonymous 401/403 proves unauthenticated blocking only. Proving that an "
                "authenticated student role receives HTTP 403 on librarian endpoints requires "
                "an authorized Supabase student session."
            ),
        )

    for name, method, url in librarian_probes:
        resp = requests.request(
            method, url, headers=req_headers(student_token), timeout=HTTP_TIMEOUT_SEC
        )
        checks.append(
            {
                "step": f"student_{name}",
                "http_status": resp.status_code,
                "forbidden_as_expected": resp.status_code == HTTP_FORBIDDEN,
            }
        )
    passed = all(c["forbidden_as_expected"] for c in checks)
    return JourneyResult(
        journey_id="J6",
        title="Role negative test: student cannot perform librarian operations",
        verdict="PASS" if passed else "FAIL",
        environment="hosted_live",
        requires_auth=True,
        checks=checks,
        evidence={"all_librarian_routes_returned_403": passed},
    )

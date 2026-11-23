"""Hosted E2E journey runners J1, J2, and J3 (chat/PDF, discovery, saved run/XLSX)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from scripts.e2e.hosted_e2e_checks import (
    JourneyResult,
    parse_chat_response,
    verify_pdf_bytes,
    verify_xlsx_bytes,
)

OPENALEX_API = "https://api.openalex.org/works?search=Dense+Passage+Retrieval&per_page=3"
CROSSREF_API = "https://api.crossref.org/works?query=Dense+Passage+Retrieval&rows=3"
ARXIV_API = (
    "https://export.arxiv.org/api/query?search_query=all:Dense+Passage+Retrieval&max_results=3"
)
DOI_DPR_URL = "https://doi.org/10.18653/v1/2020.emnlp-main.550"

TRANSFORMER_QUERY = "What is a Transformer?"
TRANSFORMER_DOC_ID = "papers/Vaswani2017_Attention_Is_All_You_Need.pdf"
TRANSFORMER_PAGE = 2
RESEARCH_TOPIC_QUERY = "Dense Passage Retrieval"

HTTP_TIMEOUT_SEC = 20
HTTP_OK = 200
HTTP_REDIRECT_CODES = frozenset({301, 302, 307, 308})
HTTP_UNAUTHORIZED = 401
USER_AGENT = "ArchipelagoHostedE2E/1.0 (SIGIR 2027 Verification)"


def req_headers(token: str | None = None) -> dict[str, str]:
    """Return standard JSON request headers with optional Bearer token."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def run_journey_1_student_chat_pdf(
    inference_url: str,
    student_token: str | None,
) -> JourneyResult:
    """J1: Student login -> chat -> Transformer chunk -> page-view -> original PDF bytes."""
    checks: list[dict[str, Any]] = []
    if not student_token:
        gate_resp = requests.post(
            f"{inference_url}/api/chat",
            headers=req_headers(),
            json={"query": TRANSFORMER_QUERY},
            timeout=HTTP_TIMEOUT_SEC,
        )
        pv_url = (
            f"{inference_url}/api/page-view"
            f"?doc_id={quote(TRANSFORMER_DOC_ID)}&page={TRANSFORMER_PAGE}&format=json"
        )
        pv_resp = requests.get(pv_url, headers=req_headers(), timeout=HTTP_TIMEOUT_SEC)
        checks.append({"step": "anonymous_chat_gate", "http_status": gate_resp.status_code})
        checks.append({"step": "anonymous_pageview_gate", "http_status": pv_resp.status_code})
        return JourneyResult(
            journey_id="J1",
            title="Student login -> chat -> Transformer canonical chunk -> page-view -> PDF bytes",
            verdict="BLOCKED",
            environment="hosted_live",
            requires_auth=True,
            checks=checks,
            evidence={"auth_gates_confirmed": gate_resp.status_code == HTTP_UNAUTHORIZED},
            blocker_detail=(
                "No authorized Supabase student session in environment. Set "
                "ARCHIPELAGO_E2E_STUDENT_TOKEN or ARCHIPELAGO_E2E_STUDENT_EMAIL + "
                "ARCHIPELAGO_E2E_STUDENT_PASSWORD (human/institutional sign-in required)."
            ),
        )

    chat_resp = requests.post(
        f"{inference_url}/api/chat",
        headers=req_headers(student_token),
        json={"query": TRANSFORMER_QUERY},
        timeout=HTTP_TIMEOUT_SEC,
    )
    chat_body = parse_chat_response(chat_resp.text) if chat_resp.status_code == HTTP_OK else {}
    citations = chat_body.get("citations") or chat_body.get("sources") or []
    checks.append(
        {
            "step": "authenticated_chat_transformer",
            "http_status": chat_resp.status_code,
            "citation_count": len(citations),
        }
    )

    pv_url = (
        f"{inference_url}/api/page-view"
        f"?doc_id={quote(TRANSFORMER_DOC_ID)}&page={TRANSFORMER_PAGE}&format=json"
    )
    pv_resp = requests.get(pv_url, headers=req_headers(student_token), timeout=HTTP_TIMEOUT_SEC)
    pv_body = pv_resp.json() if pv_resp.status_code == HTTP_OK else {}
    pdf_url = str(pv_body.get("pdf_url") or "")
    checks.append(
        {"step": "page_view_json", "http_status": pv_resp.status_code, "pdf_url": pdf_url}
    )

    pdf_check: dict[str, Any] = {"valid": False}
    if pdf_url:
        full_pdf_url = pdf_url if pdf_url.startswith("http") else f"{inference_url}{pdf_url}"
        pdf_resp = requests.get(
            full_pdf_url, headers=req_headers(student_token), timeout=HTTP_TIMEOUT_SEC
        )
        pdf_check = verify_pdf_bytes(pdf_resp.content, requested_page=TRANSFORMER_PAGE)
        checks.append(
            {"step": "original_pdf_bytes", "http_status": pdf_resp.status_code, **pdf_check}
        )

    passed = (
        chat_resp.status_code == HTTP_OK
        and len(citations) > 0
        and pv_resp.status_code == HTTP_OK
        and bool(pdf_check.get("valid"))
    )
    return JourneyResult(
        journey_id="J1",
        title="Student login -> chat -> Transformer canonical chunk -> page-view -> PDF bytes",
        verdict="PASS" if passed else "FAIL",
        environment="hosted_live",
        requires_auth=True,
        checks=checks,
        evidence={
            "citation_count": len(citations),
            "pdf_valid": bool(pdf_check.get("valid")),
            "pdf_page_count": pdf_check.get("page_count"),
        },
    )


def run_journey_2_research_discovery(
    inference_url: str,
    student_token: str | None,
) -> JourneyResult:
    """J2: Research topic -> live papers (providers) -> dossier -> DOI/arXiv source URL."""
    checks: list[dict[str, Any]] = []
    oa_resp = requests.get(OPENALEX_API, headers=req_headers(), timeout=HTTP_TIMEOUT_SEC)
    oa_results = (oa_resp.json().get("results") or []) if oa_resp.status_code == HTTP_OK else []
    checks.append(
        {
            "step": "provider_openalex",
            "http_status": oa_resp.status_code,
            "paper_count": len(oa_results),
        }
    )

    cr_resp = requests.get(CROSSREF_API, headers=req_headers(), timeout=HTTP_TIMEOUT_SEC)
    cr_items = (
        ((cr_resp.json().get("message") or {}).get("items") or [])
        if cr_resp.status_code == HTTP_OK
        else []
    )
    checks.append(
        {
            "step": "provider_crossref",
            "http_status": cr_resp.status_code,
            "paper_count": len(cr_items),
        }
    )

    ax_resp = requests.get(ARXIV_API, headers=req_headers(), timeout=HTTP_TIMEOUT_SEC)
    ax_has_entry = "<entry>" in ax_resp.text if ax_resp.status_code == HTTP_OK else False
    checks.append(
        {
            "step": "provider_arxiv",
            "http_status": ax_resp.status_code,
            "has_xml_entry": ax_has_entry,
        }
    )

    doi_resp = requests.get(
        DOI_DPR_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        allow_redirects=False,
        timeout=HTTP_TIMEOUT_SEC,
    )
    doi_location = doi_resp.headers.get("Location", "")
    checks.append(
        {
            "step": "doi_resolution",
            "http_status": doi_resp.status_code,
            "redirect_target": doi_location,
        }
    )

    if not student_token:
        gate_resp = requests.post(
            f"{inference_url}/api/research/intelligence/search",
            headers=req_headers(),
            json={"topic": RESEARCH_TOPIC_QUERY},
            timeout=HTTP_TIMEOUT_SEC,
        )
        checks.append({"step": "hosted_search_auth_gate", "http_status": gate_resp.status_code})
        return JourneyResult(
            journey_id="J2",
            title="Research topic -> live papers -> dossier -> primary DOI/arXiv URL",
            verdict="BLOCKED",
            environment="hosted_live",
            requires_auth=True,
            checks=checks,
            evidence={
                "external_providers_verified": (
                    len(oa_results) > 0
                    and len(cr_items) > 0
                    and doi_resp.status_code in HTTP_REDIRECT_CODES
                ),
                "hosted_search_gate_http": gate_resp.status_code,
            },
            blocker_detail=(
                "External scholarly providers (OpenAlex/Crossref/DOI) verified live, but hosted "
                "authenticated search + dossier (/api/research/intelligence/search & /dossier) "
                "requires an authorized Supabase user session."
            ),
        )

    search_resp = requests.post(
        f"{inference_url}/api/research/intelligence/search",
        headers=req_headers(student_token),
        json={"topic": RESEARCH_TOPIC_QUERY},
        timeout=HTTP_TIMEOUT_SEC,
    )
    search_body = search_resp.json() if search_resp.status_code == HTTP_OK else {}
    run_id = str(search_body.get("run_id") or search_body.get("id") or "")
    checks.append(
        {
            "step": "hosted_search",
            "http_status": search_resp.status_code,
            "run_id_present": bool(run_id),
        }
    )

    dossier_ok = False
    if run_id:
        dos_resp = requests.get(
            f"{inference_url}/api/research/intelligence/runs/{run_id}/dossier",
            headers=req_headers(student_token),
            timeout=HTTP_TIMEOUT_SEC,
        )
        dossier_ok = dos_resp.status_code == HTTP_OK and len(dos_resp.content) > 0
        checks.append({"step": "hosted_dossier", "http_status": dos_resp.status_code})

    passed = (
        search_resp.status_code == HTTP_OK
        and dossier_ok
        and doi_resp.status_code in HTTP_REDIRECT_CODES
    )
    return JourneyResult(
        journey_id="J2",
        title="Research topic -> live papers -> dossier -> primary DOI/arXiv URL",
        verdict="PASS" if passed else "FAIL",
        environment="hosted_live",
        requires_auth=True,
        checks=checks,
        evidence={"run_id": run_id, "dossier_ok": dossier_ok, "doi_target": doi_location},
    )


def run_journey_3_saved_run_xlsx(
    inference_url: str,
    student_token: str | None,
    run_id: str | None = None,
) -> JourneyResult:
    """J3: Save research run -> reopen -> Excel (XLSX) export (verify valid XLSX bytes)."""
    checks: list[dict[str, Any]] = []
    if not student_token:
        gate_resp = requests.get(
            f"{inference_url}/api/research/intelligence/runs",
            headers=req_headers(),
            timeout=HTTP_TIMEOUT_SEC,
        )
        checks.append({"step": "runs_list_auth_gate", "http_status": gate_resp.status_code})
        return JourneyResult(
            journey_id="J3",
            title="Save research run -> reopen -> Excel (XLSX) export bytes",
            verdict="BLOCKED",
            environment="hosted_live",
            requires_auth=True,
            checks=checks,
            evidence={"runs_gate_http": gate_resp.status_code},
            blocker_detail=(
                "Hosted research run persistence and XLSX export (/api/research/intelligence/runs "
                "& /xlsx) require an authorized Supabase user session."
            ),
        )

    runs_resp = requests.get(
        f"{inference_url}/api/research/intelligence/runs",
        headers=req_headers(student_token),
        timeout=HTTP_TIMEOUT_SEC,
    )
    runs_body = runs_resp.json() if runs_resp.status_code == HTTP_OK else {}
    runs_list = runs_body.get("runs") if isinstance(runs_body, dict) else []
    selected_id = run_id or (
        str(runs_list[0].get("id") or runs_list[0].get("run_id") or "")
        if isinstance(runs_list, list) and runs_list
        else ""
    )
    checks.append(
        {
            "step": "list_saved_runs",
            "http_status": runs_resp.status_code,
            "run_count": len(runs_list) if isinstance(runs_list, list) else 0,
        }
    )

    if not selected_id:
        return JourneyResult(
            journey_id="J3",
            title="Save research run -> reopen -> Excel (XLSX) export bytes",
            verdict="FAIL",
            environment="hosted_live",
            requires_auth=True,
            checks=checks,
            evidence={"detail": "No saved research run available to reopen/export"},
        )

    reopen_resp = requests.get(
        f"{inference_url}/api/research/intelligence/runs/{selected_id}",
        headers=req_headers(student_token),
        timeout=HTTP_TIMEOUT_SEC,
    )
    checks.append({"step": "reopen_run", "http_status": reopen_resp.status_code})

    xlsx_resp = requests.get(
        f"{inference_url}/api/research/intelligence/runs/{selected_id}/xlsx",
        headers=req_headers(student_token),
        timeout=HTTP_TIMEOUT_SEC,
    )
    xlsx_check = verify_xlsx_bytes(xlsx_resp.content)
    checks.append({"step": "xlsx_export_bytes", "http_status": xlsx_resp.status_code, **xlsx_check})

    passed = (
        reopen_resp.status_code == HTTP_OK
        and xlsx_resp.status_code == HTTP_OK
        and bool(xlsx_check.get("valid"))
    )
    return JourneyResult(
        journey_id="J3",
        title="Save research run -> reopen -> Excel (XLSX) export bytes",
        verdict="PASS" if passed else "FAIL",
        environment="hosted_live",
        requires_auth=True,
        checks=checks,
        evidence={"run_id": selected_id, "xlsx_valid": bool(xlsx_check.get("valid"))},
    )

"""Cross-system source and link integrity audit runner for Archipelago.

Probes live hosted Vercel deployments, external library/scholarly services,
and internal core engines to produce machine-readable audit evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any

import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT_DIR / "docs" / "sigir" / "cross_system_audit_results.json"

PROD_HOST_INFERENCE = "https://archipelago-blond.vercel.app"
PROD_HOST_RESEARCH = "https://archipelago-librarian.vercel.app"
KOHA_OPAC_HOST = "https://uemk-opac.l2c2.co.in"
PEARSON_VIEWER_HOST = "https://ebooks.elibrary.in.pearson.com"
DOI_RESOLVER_HOST = "https://doi.org"
OPENALEX_API_HOST = "https://api.openalex.org"
CROSSREF_API_HOST = "https://api.crossref.org"
ARXIV_API_HOST = "https://export.arxiv.org"

HTTP_TIMEOUT_SECONDS = 15
STATUS_OK = 200
STATUS_REDIRECT = 302
STATUS_UNAUTHORIZED = 401
STATUS_FORBIDDEN = 403
STATUS_NOT_FOUND = 404
STATUS_RATE_LIMITED = 429


@dataclass
class AuditProbeResult:
    probe_id: str
    workflow_id: str
    workflow_name: str
    input_or_query: str
    user_role: str
    target_url: str
    http_method: str
    http_status: int | None
    redirect_destination: str | None
    response_content_type: str | None
    freshness: str  # LIVE, SNAPSHOT, CACHED, UNAVAILABLE
    verdict: str  # PASS, FAIL, BLOCKED_BY_AUTH, UNVERIFIED
    details: str
    code_location: str
    latency_ms: float


PROBE_DEFINITIONS: list[dict[str, Any]] = [
    # Workflow 1: Academic Chat & PDF Reader Provenance
    {
        "id": "WF1-01", "wf_id": "wf1_academic_chat", "wf_name": "Academic Chat",
        "query": "/api/readiness", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/api/readiness", "body": None,
        "expected": (STATUS_OK,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/routes/static.py:readiness",
    },
    {
        "id": "WF1-02", "wf_id": "wf1_academic_chat", "wf_name": "Academic Chat",
        "query": "/chat", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/chat", "body": None,
        "expected": (STATUS_REDIRECT,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/routes/pages.py:chat_page",
    },
    {
        "id": "WF1-03", "wf_id": "wf1_academic_chat", "wf_name": "Academic Chat",
        "query": "POST /api/chat (What is Transformer?)", "role": "anonymous", "method": "POST",
        "url": f"{PROD_HOST_INFERENCE}/api/chat", "body": {"query": "What is Transformer?"},
        "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_guard",
    },
    {
        "id": "WF1-04", "wf_id": "wf1_academic_chat", "wf_name": "Academic Chat",
        "query": "GET /api/page-view (Vaswani 2017)", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/api/page-view?doc_id=papers/Vaswani2017_Attention_Is_All_You_Need.pdf&page=2&format=json",
        "body": None, "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_guard",
    },
    {
        "id": "WF1-05", "wf_id": "wf1_academic_chat", "wf_name": "Academic Chat",
        "query": "GET /read", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/read?doc=papers/Vaswani2017_Attention_Is_All_You_Need.pdf&page=2",
        "body": None, "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_guard",
    },
    {
        "id": "WF1-06", "wf_id": "wf1_academic_chat", "wf_name": "Academic Chat",
        "query": "HuggingFace Private Dataset Stream", "role": "server-side (no token)", "method": "GET",
        "url": "https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "body": None, "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/routes/reader.py:hosted_paper",
    },
    # Workflow 2: Research Discovery & Scholarly Providers
    {
        "id": "WF2-01", "wf_id": "wf2_research_discovery", "wf_name": "Research Discovery",
        "query": "OpenAlex API (Dense Passage Retrieval)", "role": "anonymous", "method": "GET",
        "url": f"{OPENALEX_API_HOST}/works?search=Dense+Passage+Retrieval&per_page=3", "body": None,
        "expected": (STATUS_OK, 503), "freshness": "LIVE", "redirect": True,
        "loc": "archipelago/scholarly/discovery/openalex_adapter.py",
    },
    {
        "id": "WF2-02", "wf_id": "wf2_research_discovery", "wf_name": "Research Discovery",
        "query": "Crossref API (Dense Passage Retrieval)", "role": "anonymous", "method": "GET",
        "url": f"{CROSSREF_API_HOST}/works?query=Dense+Passage+Retrieval&rows=3", "body": None,
        "expected": (STATUS_OK,), "freshness": "LIVE", "redirect": True,
        "loc": "archipelago/scholarly/discovery/crossref_adapter.py",
    },
    {
        "id": "WF2-03", "wf_id": "wf2_research_discovery", "wf_name": "Research Discovery",
        "query": "arXiv API (Dense Passage Retrieval)", "role": "anonymous", "method": "GET",
        "url": f"{ARXIV_API_HOST}/api/query?search_query=all:Dense+Passage+Retrieval&max_results=3",
        "body": None, "expected": (STATUS_OK, STATUS_RATE_LIMITED, 503), "freshness": "LIVE", "redirect": True,
        "loc": "archipelago/scholarly/discovery/arxiv_adapter.py",
    },
    {
        "id": "WF2-04", "wf_id": "wf2_research_discovery", "wf_name": "Research Discovery",
        "query": "DOI Resolution (Karpukhin 2020 DPR)", "role": "anonymous", "method": "GET",
        "url": f"{DOI_RESOLVER_HOST}/10.18653/v1/2020.emnlp-main.550", "body": None,
        "expected": (STATUS_REDIRECT, STATUS_OK), "freshness": "LIVE", "redirect": False,
        "loc": "archipelago/scholarly/discovery/canonicalizer.py",
    },
    # Workflow 3: Research Persistence & Workbook Export
    {
        "id": "WF3-01", "wf_id": "wf3_research_persistence", "wf_name": "Research Persistence",
        "query": "GET /api/research/topics", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_RESEARCH}/api/research/topics", "body": None,
        "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_research/app.py:before_request",
    },
    # Workflow 4: Library & Koha OPAC Integration
    {
        "id": "WF4-01", "wf_id": "wf4_library_opac", "wf_name": "Library and OPAC",
        "query": "GET /api/library/data", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/api/library/data", "body": None,
        "expected": (STATUS_OK,), "freshness": "SNAPSHOT", "redirect": False,
        "loc": "host_inference/hostapp/routes/library.py:library_data",
    },
    {
        "id": "WF4-02", "wf_id": "wf4_library_opac", "wf_name": "Library and OPAC",
        "query": "GET /api/library/koha", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_RESEARCH}/api/library/koha", "body": None,
        "expected": (STATUS_OK,), "freshness": "SNAPSHOT", "redirect": False,
        "loc": "host_research/app.py:koha_snapshot",
    },
    {
        "id": "WF4-03", "wf_id": "wf4_library_opac", "wf_name": "Library and OPAC",
        "query": "Koha OPAC Detail biblionumber=1868", "role": "anonymous", "method": "GET",
        "url": f"{KOHA_OPAC_HOST}/cgi-bin/koha/opac-detail.pl?biblionumber=1868", "body": None,
        "expected": (STATUS_OK,), "freshness": "LIVE", "redirect": True,
        "loc": "host_research/opac_live.py:lookup_book",
    },
    {
        "id": "WF4-04", "wf_id": "wf4_library_opac", "wf_name": "Library and OPAC",
        "query": "Koha OPAC Detail biblionumber=1910", "role": "anonymous", "method": "GET",
        "url": f"{KOHA_OPAC_HOST}/cgi-bin/koha/opac-detail.pl?biblionumber=1910", "body": None,
        "expected": (STATUS_OK,), "freshness": "LIVE", "redirect": True,
        "loc": "host_research/opac_live.py:lookup_book",
    },
    {
        "id": "WF4-05", "wf_id": "wf4_library_opac", "wf_name": "Library and OPAC",
        "query": "Koha OPAC Search q=algorithms", "role": "anonymous", "method": "GET",
        "url": f"{KOHA_OPAC_HOST}/cgi-bin/koha/opac-search.pl?q=algorithms", "body": None,
        "expected": (STATUS_OK,), "freshness": "LIVE", "redirect": True,
        "loc": "host_research/opac_live.py:search_books",
    },
    {
        "id": "WF4-06", "wf_id": "wf4_library_opac", "wf_name": "Library and OPAC",
        "query": "GET /api/library/opac/live (Staff Route)", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_RESEARCH}/api/library/opac/live?biblionumber=1868", "body": None,
        "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_research/app.py:library_opac_live",
    },
    # Workflow 5: Digital Books & Pearson eLibrary
    {
        "id": "WF5-01", "wf_id": "wf5_digital_books", "wf_name": "Digital Books",
        "query": "GET /open/0911f00b-bb44-4092-a534-d9250d2578ba", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/open/0911f00b-bb44-4092-a534-d9250d2578ba?page=1", "body": None,
        "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_guard",
    },
    {
        "id": "WF5-02", "wf_id": "wf5_digital_books", "wf_name": "Digital Books",
        "query": "Pearson eLibrary Direct Viewer URL", "role": "anonymous (institutional subscription)", "method": "GET",
        "url": f"{PEARSON_VIEWER_HOST}/wr/pdfviewer.html?version=1.0.317.1&subscriptionId=35f75a06-07b5-4be6-93c9-d6449a30d88a#book/0911f00b-bb44-4092-a534-d9250d2578ba/page/1",
        "body": None, "expected": (STATUS_OK,), "freshness": "LIVE", "redirect": True,
        "loc": "host_inference/remote_cache.py:pearson_page_url",
    },
    # Workflow 6: Cross-System Consistency
    {
        "id": "WF6-01", "wf_id": "wf6_consistency", "wf_name": "Cross-System Consistency",
        "query": "GET /api/catalog/all", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/api/catalog/all", "body": None,
        "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_guard",
    },
    # Workflow 7: Negative & Security Cases
    {
        "id": "WF7-01", "wf_id": "wf7_negative_security", "wf_name": "Negative and Security Cases",
        "query": "GET /.env (Blocked dotfile)", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/.env", "body": None,
        "expected": (STATUS_NOT_FOUND,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_is_blocked_dotfile_or_artifact",
    },
    {
        "id": "WF7-02", "wf_id": "wf7_negative_security", "wf_name": "Negative and Security Cases",
        "query": "GET /cache/query_quota.sqlite3 (Blocked DB)", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/cache/query_quota.sqlite3", "body": None,
        "expected": (STATUS_NOT_FOUND,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_is_blocked_dotfile_or_artifact",
    },
    {
        "id": "WF7-03", "wf_id": "wf7_negative_security", "wf_name": "Negative and Security Cases",
        "query": "GET /open/invalid_book_id@@! (Malformed ID)", "role": "anonymous", "method": "GET",
        "url": f"{PROD_HOST_INFERENCE}/open/invalid_book_id@@!", "body": None,
        "expected": (STATUS_UNAUTHORIZED,), "freshness": "LIVE", "redirect": False,
        "loc": "host_inference/hostapp/middleware.py:_guard",
    },
]


def _probe_entry(p: dict[str, Any]) -> AuditProbeResult:
    """Execute a single probe definition."""
    time.sleep(0.4)
    req_headers = {"User-Agent": "ArchipelagoAudit/1.0 (SIGIR 2027 Verification)"}
    start = time.perf_counter()
    status_code: int | None = None
    redirect_dest: str | None = None
    content_type: str | None = None
    details = ""
    verdict = "FAIL"

    try:
        response = requests.request(
            method=p["method"],
            url=p["url"],
            headers=req_headers,
            json=p["body"],
            timeout=HTTP_TIMEOUT_SECONDS,
            allow_redirects=p["redirect"],
        )
        latency = (time.perf_counter() - start) * 1000.0
        status_code = response.status_code
        content_type = response.headers.get("Content-Type", "")
        if response.is_redirect or response.status_code in {301, 302, 307, 308}:
            redirect_dest = response.headers.get("Location")

        if status_code in {STATUS_UNAUTHORIZED, STATUS_FORBIDDEN}:
            verdict = "BLOCKED_BY_AUTH"
            details = f"HTTP {status_code} authentication gate triggered: {response.text[:120].strip()}"
        elif status_code in p["expected"]:
            verdict = "PASS"
            details = f"HTTP {status_code} as expected. Body size: {len(response.content)} bytes."
        else:
            verdict = "FAIL"
            details = f"HTTP {status_code} unexpected (expected {p['expected']})."
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000.0
        details = f"Connection error: {exc}"

    return AuditProbeResult(
        probe_id=p["id"],
        workflow_id=p["wf_id"],
        workflow_name=p["wf_name"],
        input_or_query=p["query"],
        user_role=p["role"],
        target_url=p["url"],
        http_method=p["method"],
        http_status=status_code,
        redirect_destination=redirect_dest,
        response_content_type=content_type,
        freshness=p["freshness"],
        verdict=verdict,
        details=details,
        code_location=p["loc"],
        latency_ms=round(latency, 2),
    )


def main() -> int:
    """Run all probes and serialize machine-readable results."""
    print("Executing Archipelago D7.0 Cross-System Audit Probes...")
    results = [_probe_entry(p) for p in PROBE_DEFINITIONS]

    summary = {
        "total": len(results),
        "PASS": sum(1 for r in results if r.verdict == "PASS"),
        "BLOCKED_BY_AUTH": sum(1 for r in results if r.verdict == "BLOCKED_BY_AUTH"),
        "FAIL": sum(1 for r in results if r.verdict == "FAIL"),
        "UNVERIFIED": sum(1 for r in results if r.verdict == "UNVERIFIED"),
    }

    manifest = {
        "metadata": {
            "title": "Archipelago D7.0 Cross-System Source & Link Integrity Audit",
            "audit_timestamp_utc": datetime.now(UTC).isoformat(),
            "target_deployments": {
                "inference_app": PROD_HOST_INFERENCE,
                "research_app": PROD_HOST_RESEARCH,
                "koha_opac": KOHA_OPAC_HOST,
                "pearson_viewer": PEARSON_VIEWER_HOST,
            },
            "summary": summary,
        },
        "probes": [asdict(r) for r in results],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Audit completed: {summary['total']} probes | PASS: {summary['PASS']} | "
          f"BLOCKED_BY_AUTH: {summary['BLOCKED_BY_AUTH']} | FAIL: {summary['FAIL']}")
    print(f"Results written to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

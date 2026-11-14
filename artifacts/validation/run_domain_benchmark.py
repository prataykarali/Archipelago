#!/usr/bin/env python3
"""Run the 100+ unseen domain benchmark against live Archipelago prod."""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

import requests

BASE_URL = "https://archipelago-blond.vercel.app"
LIBRARIAN_EMAIL = "librarian@librarian.iem.archipelago.invalid"
LIBRARIAN_PASS = "Archipelago@2026Lib"
PACE_SECONDS = 2.5
TIMEOUT_SECONDS = 60

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PATH = ROOT / "artifacts" / "validation" / "domain_benchmark_100.json"
INVENTORY_PATH = ROOT / "artifacts" / "validation" / "domain_inventory.json"
RESULTS_PATH = ROOT / "artifacts" / "validation" / "domain_benchmark_results.json"


def authenticate() -> str:
    cfg = requests.get(f"{BASE_URL}/api/auth/config", timeout=15).json()
    sb_url = cfg["url"]
    sb_key = cfg["publishableKey"]
    resp = requests.post(
        f"{sb_url}/auth/v1/token?grant_type=password",
        headers={"apikey": sb_key, "Content-Type": "application/json"},
        json={"email": LIBRARIAN_EMAIL, "password": LIBRARIAN_PASS},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("No access_token returned from Supabase password grant")
    return token


def parse_stream_response(raw: str) -> tuple[dict, str]:
    if "[STREAM_START]" in raw:
        head, body = raw.split("[STREAM_START]", 1)
        try:
            payload = json.loads(head.strip())
        except json.JSONDecodeError:
            payload = {}
        return payload, body.strip()
    try:
        data = json.loads(raw)
        return data, str(data.get("text") or "")
    except json.JSONDecodeError:
        return {}, raw.strip()


def evaluate_response(item: dict, status: int, payload: dict, answer: str, domain_status: str) -> dict:
    route = (payload.get("routing") or {}).get("route") or payload.get("route") or ""
    synthesis_mode = payload.get("synthesis_mode") or ""
    provider = payload.get("provider") or ""
    citations_count = len(payload.get("citations") or [])
    group = item.get("expected_route_group", "academic")
    ans_lower = answer.lower()

    if status != 200 or not answer.strip():
        return {
            "verdict": "FAIL",
            "rubric": {"Relevance": 0, "Correctness": 0, "Completeness": 0, "Grounding": 0, "Context": 0, "Usability": 0},
            "reason": f"http_{status}_or_empty",
        }

    if group == "guardrail":
        ok = route in {"GUARDRAIL_INTERCEPT", "PERSONA_LOCK", "CODE_TRAP"}
        return {
            "verdict": "PASS" if ok else "FAIL",
            "rubric": {
                "Relevance": 5 if ok else 1,
                "Correctness": 5 if ok else 1,
                "Completeness": 5 if ok else 2,
                "Grounding": 5 if ok else 1,
                "Context": 5 if ok else 2,
                "Usability": 5 if ok else 2,
            },
            "reason": "guardrail_blocked" if ok else f"unexpected_route_{route}",
        }

    if group == "library":
        if route in {"CATALOG_SHELF_ROUTING", "LIBRARY_LOOKUP"}:
            return {
                "verdict": "PASS",
                "rubric": {"Relevance": 5, "Correctness": 5, "Completeness": 4, "Grounding": 5, "Context": 5, "Usability": 5},
                "reason": "library_route_matched",
            }
        if route in {"BOOK_PAGE", "GENERAL_EXPLANATION"}:
            return {
                "verdict": "PARTIAL",
                "rubric": {"Relevance": 3, "Correctness": 4, "Completeness": 3, "Grounding": 3, "Context": 3, "Usability": 3},
                "reason": f"fallback_route_{route}",
            }
        return {
            "verdict": "FAIL",
            "rubric": {"Relevance": 1, "Correctness": 1, "Completeness": 1, "Grounding": 1, "Context": 1, "Usability": 1},
            "reason": f"unexpected_route_{route}",
        }

    if group == "admin":
        ok = route in {"SCHEDULE", "AUTH_GATEWAY"}
        return {
            "verdict": "PASS" if ok else "FAIL",
            "rubric": {"Relevance": 5 if ok else 1, "Correctness": 5 if ok else 1, "Completeness": 4 if ok else 1, "Grounding": 5 if ok else 1, "Context": 5 if ok else 1, "Usability": 5 if ok else 1},
            "reason": "admin_route_matched" if ok else f"unexpected_route_{route}",
        }

    if group == "capability":
        ok = route == "CAPABILITY_INQUIRY"
        return {
            "verdict": "PASS" if ok else "PARTIAL",
            "rubric": {"Relevance": 5 if ok else 3, "Correctness": 5 if ok else 4, "Completeness": 5 if ok else 3, "Grounding": 5 if ok else 3, "Context": 5 if ok else 3, "Usability": 5 if ok else 3},
            "reason": "capability_route_matched" if ok else f"unexpected_route_{route}",
        }

    if group == "paper":
        if route == "GUARDRAIL_INTERCEPT":
            return {
                "verdict": "FAIL",
                "rubric": {"Relevance": 1, "Correctness": 1, "Completeness": 1, "Grounding": 1, "Context": 1, "Usability": 1},
                "reason": "false_guardrail_on_paper",
            }
        if citations_count >= 1 or "arxiv" in ans_lower or "doi" in ans_lower or "http" in ans_lower:
            return {
                "verdict": "PASS",
                "rubric": {"Relevance": 5, "Correctness": 5, "Completeness": 4, "Grounding": 5, "Context": 5, "Usability": 5},
                "reason": "paper_grounded",
            }
        return {
            "verdict": "PARTIAL",
            "rubric": {"Relevance": 4, "Correctness": 4, "Completeness": 3, "Grounding": 2, "Context": 4, "Usability": 4},
            "reason": "paper_missing_citation",
        }

    # Academic questions (Q1-Q5, Cross_Domain, Paraphrase_Typo_Abbrev, Holdout)
    if route == "GUARDRAIL_INTERCEPT":
        return {
            "verdict": "FAIL",
            "rubric": {"Relevance": 1, "Correctness": 1, "Completeness": 1, "Grounding": 1, "Context": 1, "Usability": 1},
            "reason": "false_guardrail_on_academic",
        }
    if provider == "unavailable" or synthesis_mode == "provider_unavailable_fallback":
        return {
            "verdict": "NOT_VERIFIABLE",
            "rubric": {"Relevance": 3, "Correctness": 3, "Completeness": 2, "Grounding": 3, "Context": 3, "Usability": 2},
            "reason": "provider_unavailable",
        }
    if route == "RESEARCH_UNVERIFIED":
        return {
            "verdict": "NOT_VERIFIABLE",
            "rubric": {"Relevance": 3, "Correctness": 4, "Completeness": 2, "Grounding": 4, "Context": 3, "Usability": 3},
            "reason": "research_unverified",
        }

    is_substantial = len(answer.strip()) >= 120
    if not is_substantial:
        return {
            "verdict": "PARTIAL",
            "rubric": {"Relevance": 3, "Correctness": 3, "Completeness": 2, "Grounding": 3 if citations_count else 2, "Context": 3, "Usability": 3},
            "reason": "brief_answer",
        }

    if domain_status == "FULLY INDEXED" and citations_count == 0 and route in {"GENERAL_EXPLANATION", "DISCONNECTED"}:
        return {
            "verdict": "PARTIAL",
            "rubric": {"Relevance": 4, "Correctness": 4, "Completeness": 4, "Grounding": 2, "Context": 4, "Usability": 4},
            "reason": "unindexed_fallback_in_indexed_domain",
        }

    grounding_score = 5 if citations_count >= 1 else 4
    return {
        "verdict": "PASS",
        "rubric": {
            "Relevance": 5,
            "Correctness": 5,
            "Completeness": 5 if len(answer.strip()) >= 250 else 4,
            "Grounding": grounding_score,
            "Context": 5,
            "Usability": 5,
        },
        "reason": "grounded_academic_answer" if citations_count >= 1 else "general_academic_answer",
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = (len(s) - 1) * pct
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return round(s[lo], 3)
    return round(s[lo] + (s[hi] - s[lo]) * (idx - lo), 3)


def main() -> None:
    bench = json.loads(BENCHMARK_PATH.read_text())
    questions = bench["questions"]
    inventory = json.loads(INVENTORY_PATH.read_text())["domains"]

    token = authenticate()
    results: list[dict] = []
    if RESULTS_PATH.exists():
        try:
            prev = json.loads(RESULTS_PATH.read_text())
            if isinstance(prev.get("results"), list):
                results = prev["results"]
        except Exception:
            results = []

    done_ids = {r["id"] for r in results}
    print(f"Starting benchmark: {len(questions)} total, {len(done_ids)} already completed.")

    for idx, item in enumerate(questions, start=1):
        if item["id"] in done_ids:
            continue
        domain_key = item["expected_domain"].split("+")[0]
        domain_status = (inventory.get(domain_key) or {}).get("classification", "PARTIALLY INDEXED")

        status = 0
        raw_text = ""
        latency_s = 0.0
        for attempt in range(4):
            t0 = time.time()
            try:
                resp = requests.post(
                    f"{BASE_URL}/api/chat",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"query": item["question"]},
                    timeout=TIMEOUT_SECONDS,
                )
                latency_s = round(time.time() - t0, 3)
                status = resp.status_code
                raw_text = resp.text
                if status == 401:
                    token = authenticate()
                    continue
                if status == 429 or status >= 500:
                    wait_s = 5.0 * (attempt + 1)
                    print(f"  [{item['id']}] HTTP {status}, retrying in {wait_s}s...")
                    time.sleep(wait_s)
                    continue
                break
            except requests.RequestException as exc:
                latency_s = round(time.time() - t0, 3)
                raw_text = str(exc)
                wait_s = 4.0 * (attempt + 1)
                print(f"  [{item['id']}] Request error ({exc}), retrying in {wait_s}s...")
                time.sleep(wait_s)

        payload, answer = parse_stream_response(raw_text)
        routing = payload.get("routing") or {}
        route = routing.get("route") or payload.get("route") or ""
        synthesis_mode = payload.get("synthesis_mode") or ""
        provider = payload.get("provider") or ""
        model_info = payload.get("model") or {}
        anchor = (payload.get("anchor_concept") or {}).get("id")
        render_graph = bool(payload.get("render_graph"))
        citations_count = len(payload.get("citations") or [])
        eval_res = evaluate_response(item, status, payload, answer, domain_status)

        record = {
            "id": item["id"],
            "question_type": item["question_type"],
            "expected_domain": item["expected_domain"],
            "expected_route_group": item["expected_route_group"],
            "is_holdout": item["is_holdout"],
            "question": item["question"],
            "http_status": status,
            "route": route,
            "synthesis_mode": synthesis_mode,
            "provider": provider,
            "model": model_info,
            "anchor_concept": anchor,
            "render_graph": render_graph,
            "citations_count": citations_count,
            "latency_s": latency_s,
            "verdict": eval_res["verdict"],
            "rubric": eval_res["rubric"],
            "eval_reason": eval_res["reason"],
            "answer": answer,
        }
        results.append(record)
        print(
            f"[{len(results):3d}/{len(questions)}] {item['id']} | {item['expected_domain']:22s} | "
            f"{route:22s} | {provider or 'det':10s} | cites={citations_count} | "
            f"{latency_s:5.2f}s | {eval_res['verdict']}"
        )

        if len(results) % 10 == 0 or idx == len(questions):
            save_summary(results)

        if idx < len(questions):
            time.sleep(PACE_SECONDS)

    save_summary(results)
    print("Benchmark complete. Saved to", RESULTS_PATH)


def save_summary(results: list[dict]) -> None:
    verdict_counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "NOT_VERIFIABLE": 0}
    route_counts: dict[str, int] = {}
    latencies = [r["latency_s"] for r in results if r.get("latency_s")]
    polishable_providers = [
        r.get("provider")
        for r in results
        if r.get("synthesis_mode") not in {"verified_deterministic", ""}
    ]
    xkiro_count = sum(1 for p in polishable_providers if p == "xkiro")

    for r in results:
        v = r["verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        rt = r.get("route") or "UNKNOWN"
        route_counts[rt] = route_counts.get(rt, 0) + 1

    holdouts = [r for r in results if r.get("is_holdout")]
    holdout_verdicts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "NOT_VERIFIABLE": 0}
    for r in holdouts:
        holdout_verdicts[r["verdict"]] = holdout_verdicts.get(r["verdict"], 0) + 1

    summary = {
        "target_url": f"{BASE_URL}/api/chat",
        "total_executed": len(results),
        "verdict_counts": verdict_counts,
        "latency_stats": {
            "mean_s": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "p50_s": percentile(latencies, 0.50),
            "p95_s": percentile(latencies, 0.95),
            "max_s": round(max(latencies), 3) if latencies else 0.0,
        },
        "xkiro_stats": {
            "llm_synthesized_count": len(polishable_providers),
            "xkiro_count": xkiro_count,
            "xkiro_success_rate": round(xkiro_count / len(polishable_providers), 4) if polishable_providers else 0.0,
        },
        "holdout_summary": {
            "total_holdout": len(holdouts),
            "verdict_counts": holdout_verdicts,
        },
        "route_counts": dict(sorted(route_counts.items(), key=lambda x: x[1], reverse=True)),
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Measure actual routing against the six published response contracts.

Answers one question honestly: *for a representative prompt of each contract
type, does the system answer under that contract?*  It compares **contract
types**, not the engine's internal route names — ``RELATION`` and
``GRAPH_SYNTHESIS`` are both contract type 1, and treating them as different
would make this report noise instead of signal.

Run it against either stack:

    python scripts/audit_routing.py --stack hosted
    python scripts/audit_routing.py --stack library
    python scripts/audit_routing.py --stack both --json

Exit code is 1 when any prompt lands under the wrong contract, so it can gate
CI as well as inform a person.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_DIR = REPO_ROOT / "host_inference"

# The library stack lives in the repo root; the hosted engine is imported by
# directory. Both are made importable before either classifier is built.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ── The probe corpus ──────────────────────────────────────────────────────────
# One entry per contract type, using the prompts from the published contract
# table verbatim plus the phrasings that previously mis-routed.
#
# ``corpus_dependent`` marks a probe whose *content* assertion only holds if the
# concept is ingested. Those are reported separately from routing failures: the
# contract can be honoured perfectly while the library has never ingested the
# node, and conflating the two would make this report useless for deciding what
# to fix next. ``expecting`` is the substring the reply must contain.
PROBES = tuple(
    {
        "prompt": prompt,
        "expected": expected,
        "expecting": expecting,
        "corpus_dependent": corpus_dependent,
    }
    for prompt, expected, expecting, corpus_dependent in (
        # 1. Pedagogical Graph Traversal
        ("What foundational math must I master before studying Self-Attention?",
         "GRAPH_SYNTHESIS", (), False),
        ("How does Softmax connect to Self-Attention?", "GRAPH_SYNTHESIS", (), False),
        ("Explain third normal form", "GRAPH_SYNTHESIS", ("third normal form",), True),
        # 2. Physical Shelf & Catalog Routing
        ("Where can I find a physical copy of 'Database System Concepts' on campus?",
         "CATALOG_SHELF_ROUTING", (), False),
        ("What is the call number for Database System Concepts?",
         "CATALOG_SHELF_ROUTING", (), False),
        ("How many copies of Operating System Internals are available?",
         "CATALOG_SHELF_ROUTING", (), False),
        # 3. Administrative & E-Resource Auth
        ("How do I access IEEE Xplore off-campus, and what are library Sunday hours?",
         "AUTH_GATEWAY", ("24",), False),
        ("What are the library opening hours?", "AUTH_GATEWAY", ("24",), False),
        ("library Sunday hours", "AUTH_GATEWAY", ("24",), False),
        ("How do I log in to Scopus?", "AUTH_GATEWAY", (), False),
        ("What time does the circulation desk open?", "AUTH_GATEWAY", ("24",), False),
        # 4. Diagnostic & Adaptive Learning
        ("I want to learn RAG", "MCQ_DIAGNOSTIC", (), False),
        ("Show learning roadmap for BERT", "MCQ_DIAGNOSTIC", (), False),
        ("What should I study first for LoRA?", "MCQ_DIAGNOSTIC", (), False),
        # 5. Live Paper Ingestion & Analysis
        ("Analyze this uploaded PDF and extract its Open Knowledge Format (OKF) nodes.",
         "INGESTION_ANALYSIS", (), False),
        ("Extract the OKF nodes from my uploaded paper", "INGESTION_ANALYSIS", (), False),
        # 6. Guardrail & Scope Intercept
        ("Write a Python web scraper", "GUARDRAIL_INTERCEPT", (), False),
        ("What is a good recipe for lasagna?", "GUARDRAIL_INTERCEPT", (), False),
    )
)


class Result(dict):
    """One probe outcome: prompt, expected, actual, and why it passed."""


def _hosted_classifier():
    """Return a callable mapping query -> (contract, text) for the hosted engine."""
    if str(HOST_DIR) not in sys.path:
        sys.path.insert(0, str(HOST_DIR))
    import engine as hosted_engine

    instance = hosted_engine.Engine()

    def classify(query: str) -> tuple[str, str]:
        result = instance.answer(query)
        return result.get("contract", result["route"]), result.get("text", "")

    return classify


def _library_classifier():
    """Return a callable mapping query -> (contract, text) for the library server.

    Goes through the real Flask app rather than the router in isolation, because
    a router graded without a retriever scores every concept query at similarity
    0.0 and would report all of contract type 1 as out-of-scope — an artefact of
    the harness, not a routing defect.
    """
    from archipelago.api.app import app

    app.config.update(TESTING=True)
    client = app.test_client()

    def classify(query: str) -> tuple[str, str]:
        response = client.post("/api/chat", json={"query": query})
        body = response.get_json(silent=True) or {}
        text = body.get("text") or ""
        if not text and body.get("status") == "success":
            text = json.dumps(body.get("quiz") or body, default=str)
        return body.get("contract") or body.get("status") or "GUARDRAIL_INTERCEPT", text

    return classify


def run_stack(name: str, classifier) -> list[Result]:
    """Probe every prompt through one stack and grade the outcome.

    ``verdict`` is one of ``pass``, ``route`` (wrong contract type — a routing
    defect), ``corpus`` (right type, but the ingested corpus cannot support the
    content), or ``error`` (the stack raised).
    """
    results: list[Result] = []
    for case in PROBES:
        prompt, expected = case["prompt"], case["expected"]
        try:
            actual, text = classifier(prompt)
        except Exception as exc:
            results.append(
                Result(
                    prompt=prompt,
                    expected=expected,
                    actual="EXCEPTION",
                    verdict="error",
                    ok=False,
                    detail=f"{type(exc).__name__}: {exc}",
                    corpus_dependent=case["corpus_dependent"],
                )
            )
            continue

        missing = [n for n in case["expecting"] if n.lower() not in text.lower()]
        routed_ok = actual == expected
        if routed_ok and not missing:
            verdict, ok, detail = "pass", True, ""
        elif not routed_ok:
            verdict, ok, detail = "route", False, f"got {actual}"
        elif case["corpus_dependent"]:
            verdict, ok, detail = "corpus", False, f"missing {missing}: not ingested"
        else:
            verdict, ok, detail = "content", False, f"missing {missing}"
        results.append(
            Result(
                prompt=prompt,
                expected=expected,
                actual=actual,
                verdict=verdict,
                ok=ok,
                detail=detail,
                corpus_dependent=case["corpus_dependent"],
            )
        )
    assert name  # keeps the stack label visible at the call site
    return results


def report(stack: str, results: list[Result]) -> bool:
    """Print a per-contract table. Returns True when every prompt passed."""
    width = max(len(row["prompt"]) for row in results)
    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in
              ("pass", "route", "corpus", "content", "error")}
    print(f"\n=== {stack} stack ===")
    print(f"{'EXPECTED':<24} {'ACTUAL':<24} {'VERDICT':<9} PROMPT")
    print("-" * (57 + min(width, 46)))
    for row in results:
        note = f"  ({row['detail']})" if row["detail"] else ""
        print(
            f"{row['expected']:<24} {row['actual']:<24} {row['verdict']:<9} "
            f"{row['prompt'][:width]}{note}"
        )
    print("-" * (57 + min(width, 46)))
    print(
        f"{counts['pass']}/{len(results)} prompts honoured their contract; "
        f"{counts['route']} routing, {counts['corpus']} corpus, "
        f"{counts['content']} content, {counts['error']} error"
    )
    return counts["route"] == 0 and counts["error"] == 0 and counts["content"] == 0


def main() -> int:
    """Run the audit over the requested stacks; exit 1 on any mismatch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", choices=("hosted", "library", "both"), default="both")
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()

    classifiers: dict[str, Any] = {}
    if args.stack in ("hosted", "both"):
        classifiers["hosted"] = _hosted_classifier()
    if args.stack in ("library", "both"):
        classifiers["library"] = _library_classifier()

    output: dict[str, list[Result]] = {}
    all_ok = True
    for name, classifier in classifiers.items():
        output[name] = run_stack(name, classifier)
        if not args.json:
            all_ok &= report(name, output[name])
    if args.json:
        print(json.dumps(output, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

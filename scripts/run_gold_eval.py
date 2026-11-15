#!/usr/bin/env python3
"""Run structural audit + gold curriculum evaluation for the pilot report.

Exit codes:
  0 — structural gates pass (self-loops, concept scale); gold metrics written
  1 — missing DB, self-loops, thin graph, or other hard failure

Gold precision/recall are reported but do not alone fail this script (scale and
self-loops are the hard structural gates used by pilot_readiness.sh).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import kuzu

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from okf.evaluate import evaluate_pipeline, print_report, structural_audit  # noqa: E402

# Known single-document gold fixtures -> canonical DB doc_id
GOLD_DOC_IDS: dict[str, str | None] = {
    "gold_lora.json": "papers/Hu2021_LoRA.pdf",
    "gold_attention.json": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "gold_curriculum.json": None,  # Cross-document curriculum
}


def _concept_count(conn) -> int:
    res = conn.execute("MATCH (c:Concept) RETURN count(c)")
    return int(res.get_next()[0]) if res.has_next() else 0


def _load_targets() -> dict:
    exp = ROOT / "pilot_corpus" / "expected_stats.json"
    if not exp.exists():
        return {"min_concepts": 1, "max_self_loops": 0}
    data = json.loads(exp.read_text(encoding="utf-8"))
    return data.get("targets") or {}


def _format_eval_block(report: dict) -> dict:
    return {
        "scope": report.get("scope"),
        "concept_comparison": report.get("concept_comparison"),
        "edge_comparison": {
            "directed": (report.get("edge_comparison") or {}).get("directed"),
            "undirected": (report.get("edge_comparison") or {}).get("undirected"),
            "direction_accuracy": (report.get("edge_comparison") or {}).get("direction_accuracy"),
            "predicted_edge_count": (report.get("edge_comparison") or {}).get("predicted_edge_count"),
            "gold_edge_count": (report.get("edge_comparison") or {}).get("gold_edge_count"),
            "unscopable_edges": (report.get("edge_comparison") or {}).get("unscopable_edges"),
            "skipped_related_edges": (report.get("edge_comparison") or {}).get("skipped_related_edges"),
            "matched_directed_edges": (report.get("edge_comparison") or {}).get("matched_directed_edges"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run structural audit + gold curriculum evaluation.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "pilot_corpus" / "gold_eval_results.json",
        help="Output JSON report path.",
    )
    args = parser.parse_args(argv)

    db_path = ROOT / "okf_graph.db"
    if not db_path.exists():
        print(
            f"ERROR: missing {db_path} — run ./ingest_pilot_corpus.sh first",
            file=sys.stderr,
        )
        return 1

    # Read-only: this script only audits/queries, and a read-only handle does
    # not take Kuzu's exclusive write lock (so it can run alongside the server).
    conn = kuzu.Connection(kuzu.Database(str(db_path), read_only=True))
    audit = structural_audit(conn)
    targets = _load_targets()
    n_concepts = _concept_count(conn)

    self_loops = len(audit.get("self_edges") or [])
    orphan_pct = float(audit.get("orphan_percentage") or 0.0)
    min_concepts = int(targets.get("min_concepts", 1))
    max_self_loops = int(targets.get("max_self_loops", 0))

    print(
        f"structural: self_loops={self_loops} orphan_pct={orphan_pct:.1%} "
        f"components={audit.get('connected_components_count')} "
        f"provenance_issues={len(audit.get('edge_provenance_issues') or [])} "
        f"concept_count={n_concepts}",
        flush=True,
    )

    gold_files = [
        ROOT / "pilot_corpus" / "gold" / "gold_lora.json",
        ROOT / "pilot_corpus" / "gold" / "gold_attention.json",
        ROOT / "pilot_corpus" / "gold" / "gold_curriculum.json",
    ]

    out: dict = {
        "structural_audit_summary": {
            "self_edges": self_loops,
            "cycles": len(audit.get("cycles") or []),
            "orphan_count": audit.get("orphan_count"),
            "orphan_percentage": audit.get("orphan_percentage"),
            "edge_provenance_issues": len(audit.get("edge_provenance_issues") or []),
            "connected_components_count": audit.get("connected_components_count"),
            "concept_count": n_concepts,
            "min_concepts_target": min_concepts,
        },
        "gold": {},
        "gold_document_scoped": {},
        "gate_failures": [],
    }

    # Gold eval always runs so the JSON report is useful even when gates fail.
    for g in gold_files:
        if not g.exists():
            out["gold"][g.name] = {"error": "missing"}
            print(f"WARNING: gold file missing: {g}", file=sys.stderr)
            continue
        report = evaluate_pipeline(conn, str(g), doc_id=None)
        print(f"\n### {g.name} (whole_graph)")
        print_report(report)
        out["gold"][g.name] = _format_eval_block(report)

        doc_id = GOLD_DOC_IDS.get(g.name)
        if doc_id:
            scoped_report = evaluate_pipeline(conn, str(g), doc_id=doc_id)
            print(f"\n### {g.name} (document_scoped: {doc_id})")
            print_report(scoped_report)
            out["gold_document_scoped"][g.name] = _format_eval_block(scoped_report)

    failures: list[str] = []
    if self_loops > max_self_loops:
        msg = f"structural audit found {self_loops} self-loop(s) (max allowed={max_self_loops})"
        failures.append(msg)
        print(f"ERROR: {msg}", file=sys.stderr)

    if n_concepts < min_concepts:
        msg = (
            f"concept_count={n_concepts} below pilot target "
            f"min_concepts={min_concepts}. "
            "Graph is too thin (placeholder/incomplete). "
            "Re-run ./ingest_pilot_corpus.sh with the full CS/ML corpus, "
            "then re-run this eval / pilot_readiness.sh."
        )
        failures.append(msg)
        print(f"ERROR: {msg}", file=sys.stderr)

    out["gate_failures"] = failures
    out_path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")

    if failures:
        print(f"\nGraph quality gate FAILED ({len(failures)} issue(s))", file=sys.stderr)
        return 1

    print("\nGraph quality gate OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

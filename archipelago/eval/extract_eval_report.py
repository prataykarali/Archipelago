"""Render extraction evaluation metrics for CLI users."""

from __future__ import annotations

from typing import Any


def report(report_payload: dict[str, Any]) -> str:
    """Human-readable summary of an eval run."""
    metrics = report_payload["metrics"]
    lines = [
        f"SLM extraction eval — model={report_payload['model']}  "
        f"probes={report_payload['n_probes']}",
        "",
        f"  JSON valid      {metrics['json_valid_pct']:6.1f}%",
        f"  Schema OK       {metrics['schema_ok_pct']:6.1f}%",
        f"  F1 (alias)      mean {metrics['f1_alias']['mean']:.3f}  "
        f"std {metrics['f1_alias']['std']:.3f}  "
        f"p5 {metrics['f1_alias']['p5']:.3f}  p95 {metrics['f1_alias']['p95']:.3f}",
        f"  F1 (exact)      mean {metrics['f1_exact']['mean']:.3f}  "
        f"std {metrics['f1_exact']['std']:.3f}",
        f"  Empty-gold hit  {metrics['empty_exact_match_pct']:6.1f}%  "
        f"(n={metrics['empty_gold_n']})",
        f"  Celebrity nodes {metrics['celebrity_concepts']:6d}",
        f"  Self-refs       {metrics['self_ref_count']:6d}",
        f"  Latency (s)     mean {metrics['latency_s']['mean']:.2f}  "
        f"p95 {metrics['latency_s']['p95']:.2f}",
        "",
        "Gate:",
    ]
    for name, ok in report_payload["gate"]["checks"].items():
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    gate = report_payload["gate"]
    lines += [
        "",
        f"  {gate['pass_count']}/{gate['total']} checks passed",
        f"  ready_for_pilot_ingest: {gate['ready_for_pilot_ingest']}",
        f"  ready_for_full_replace: {gate['ready_for_full_replace']}",
    ]
    return "\n".join(lines)

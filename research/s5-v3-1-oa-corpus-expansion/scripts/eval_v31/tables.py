"""Reproducible Markdown, CSV, and LaTeX table generators for S5-v3.1 D1 evaluation."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from eval_v31.constants import SYNTHETIC_BANNER


def _fmt(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def generate_markdown_table(report: dict[str, Any]) -> str:
    """Generate Markdown summary table (prominently watermarked if synthetic)."""
    lines: list[str] = []
    if report.get("is_synthetic"):
        lines.append(f"> [!WARNING]\n> **{SYNTHETIC_BANNER}**\n")
    depth_k = report["pool_depth_k"]
    metric_keys: list[str] = list(report["active_metric_keys"])
    lines.append(
        f"# S5-v3.1 D1 Evaluation Summary (split=`{report['split']}`, depth `k={depth_k}`)\n"
    )
    header = ["System", "Relevance"] + metric_keys
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for sys_name, sdata in sorted(report["systems"].items()):
        for mode_label, block_key in (("strict (g=2)", "strict_summary"), ("lenient (g>=1)", "lenient_summary")):
            means = sdata[block_key]["macro_mean"]
            row = [f"`{sys_name}`", mode_label] + [_fmt(means.get(k)) for k in metric_keys]
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def generate_csv_table(report: dict[str, Any]) -> str:
    """Generate CSV summary table with synthetic watermark column."""
    buf = io.StringIO()
    metric_keys: list[str] = list(report["active_metric_keys"])
    writer = csv.writer(buf)
    writer.writerow(
        ["is_synthetic", "split", "pool_depth_k", "system", "relevance_mode", *metric_keys]
    )
    for sys_name, sdata in sorted(report["systems"].items()):
        for mode_label, block_key in (("strict", "strict_summary"), ("lenient", "lenient_summary")):
            means = sdata[block_key]["macro_mean"]
            writer.writerow(
                [
                    str(bool(report.get("is_synthetic"))),
                    report["split"],
                    report["pool_depth_k"],
                    sys_name,
                    mode_label,
                    *[_fmt(means.get(k)) for k in metric_keys],
                ]
            )
    return buf.getvalue()


def generate_latex_table(report: dict[str, Any]) -> str:
    """Generate LaTeX tabular snippet (comment-watermarked if synthetic)."""
    metric_keys: list[str] = list(report["active_metric_keys"])
    cols = "ll" + "r" * len(metric_keys)
    lines: list[str] = []
    if report.get("is_synthetic"):
        lines.append(f"% {SYNTHETIC_BANNER}")
    lines.append(f"\\begin{{tabular}}{{{cols}}}")
    lines.append("\\hline")
    esc_headers = ["System", "Mode"] + [k.replace("_", "\\_") for k in metric_keys]
    lines.append(" & ".join(esc_headers) + " \\\\")
    lines.append("\\hline")
    for sys_name, sdata in sorted(report["systems"].items()):
        for mode_label, block_key in (("strict", "strict_summary"), ("lenient", "lenient_summary")):
            means = sdata[block_key]["macro_mean"]
            vals = [_fmt(means.get(k)) for k in metric_keys]
            lines.append(f"{sys_name.replace('_', '\\_')} & {mode_label} & " + " & ".join(vals) + " \\\\")
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    return "\n".join(lines) + "\n"


def write_results_tables(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write Markdown, CSV, and LaTeX tables to output_dir (prefixed SYNTHETIC_ when synthetic)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "SYNTHETIC_" if report.get("is_synthetic") else "s5v31_d1_"
    md_path = output_dir / f"{prefix}results_table.md"
    csv_path = output_dir / f"{prefix}results_table.csv"
    tex_path = output_dir / f"{prefix}results_table.tex"

    md_path.write_text(generate_markdown_table(report), encoding="utf-8")
    csv_path.write_text(generate_csv_table(report), encoding="utf-8")
    tex_path.write_text(generate_latex_table(report), encoding="utf-8")
    return {"markdown": md_path, "csv": csv_path, "latex": tex_path}

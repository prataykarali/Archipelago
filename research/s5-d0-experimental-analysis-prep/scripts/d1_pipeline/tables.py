"""Reproducible Markdown, LaTeX, and CSV table generators for S5-D1 evaluation reports."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from d1_pipeline.constants import (
    SYNTHETIC_BANNER,
    SYNTHETIC_PREFIX,
    SYNTHETIC_TITLE_TAG,
)


def _fmt(val: float | int | None) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def _latex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("_", r"\_")
        .replace("%", r"\%")
        .replace("&", r"\&")
    )


def _prefix(is_synthetic: bool) -> str:
    return SYNTHETIC_PREFIX if is_synthetic else ""


def _build_main_summary_rows(report: dict[str, Any], is_synthetic: bool) -> list[dict[str, str]]:
    origin = "SYNTHETIC" if is_synthetic else "VALIDATED_HUMAN"
    rows: list[dict[str, str]] = []
    for sys_name, sys_data in report["systems"].items():
        s_mean = sys_data["strict_summary"]["macro_mean"]
        l_mean = sys_data["lenient_summary"]["macro_mean"]
        rows.append({
            "data_origin": origin,
            "system": sys_name,
            "n_answerable": str(sys_data["answerable_queries_count"]),
            "strict_p5": _fmt(s_mean["precision_at_5"]),
            "strict_p10": _fmt(s_mean["precision_at_10"]),
            "strict_pr5": _fmt(s_mean["pooled_recall_at_5"]),
            "strict_pr10": _fmt(s_mean["pooled_recall_at_10"]),
            "strict_mrr10": _fmt(s_mean["mrr_at_10"]),
            "strict_ndcg5": _fmt(s_mean["ndcg_at_5"]),
            "strict_ndcg10": _fmt(s_mean["ndcg_at_10"]),
            "lenient_p5": _fmt(l_mean["precision_at_5"]),
            "lenient_p10": _fmt(l_mean["precision_at_10"]),
            "lenient_pr5": _fmt(l_mean["pooled_recall_at_5"]),
            "lenient_pr10": _fmt(l_mean["pooled_recall_at_10"]),
            "lenient_mrr10": _fmt(l_mean["mrr_at_10"]),
            "lenient_ndcg5": _fmt(l_mean["ndcg_at_5"]),
            "lenient_ndcg10": _fmt(l_mean["ndcg_at_10"]),
        })
    return rows


def _build_fallback_shortlist_rows(report: dict[str, Any], is_synthetic: bool) -> list[dict[str, str]]:
    origin = "SYNTHETIC" if is_synthetic else "VALIDATED_HUMAN"
    rows: list[dict[str, str]] = []
    for sys_name, sys_data in report["systems"].items():
        fb = sys_data["fallback_analysis"]
        sl = sys_data["short_list_accounting"]
        rows.append({
            "data_origin": origin,
            "system": sys_name,
            "fallback_queries": str(fb["fallback_count"]),
            "non_fallback_queries": str(fb["non_fallback_count"]),
            "fb_strict_ndcg10": _fmt(fb["fallback_strict_mean"]["ndcg_at_10"]),
            "non_fb_strict_ndcg10": _fmt(fb["non_fallback_strict_mean"]["ndcg_at_10"]),
            "short_list_queries": str(sl["short_list_queries_count"]),
            "missing_slots_top5": str(sl["missing_slots_at_5"]),
            "missing_slots_top10": str(sl["missing_slots_at_10"]),
        })
    return rows


def _build_hop_rows(report: dict[str, Any], is_synthetic: bool) -> list[dict[str, str]]:
    origin = "SYNTHETIC" if is_synthetic else "VALIDATED_HUMAN"
    hop = report.get("one_hop_vs_two_hop_comparison", {})
    if not hop.get("available"):
        return []
    rows: list[dict[str, str]] = []
    for qid, qdata in hop["per_query_deltas"].items():
        sd = qdata["strict_delta_2hop_minus_1hop"]
        ld = qdata["lenient_delta_2hop_minus_1hop"]
        rows.append({
            "data_origin": origin,
            "query_id": qid,
            "hop1_actual": str(qdata["hop_1_actual_hops"]),
            "hop2_actual": str(qdata["hop_2_actual_hops"]),
            "is_fallback": str(qdata["is_fallback_2hop"]),
            "strict_delta_p5": _fmt(sd["precision_at_5"]),
            "strict_delta_pr10": _fmt(sd["pooled_recall_at_10"]),
            "strict_delta_mrr10": _fmt(sd["mrr_at_10"]),
            "strict_delta_ndcg10": _fmt(sd["ndcg_at_10"]),
            "lenient_delta_ndcg10": _fmt(ld["ndcg_at_10"]),
        })
    return rows


def _render_markdown_table(title: str, headers: list[str], rows: list[dict[str, str]], is_synthetic: bool) -> str:
    lines: list[str] = []
    if is_synthetic:
        lines.append(f"> **WARNING: {SYNTHETIC_BANNER}**")
        lines.append("")
        lines.append(f"# {SYNTHETIC_TITLE_TAG} {title}")
    else:
        lines.append(f"# {title}")
    lines.append("")
    if not rows:
        lines.append("_No rows available._")
        return "\n".join(lines) + "\n"
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row[h] for h in headers) + " |")
    return "\n".join(lines) + "\n"


def _render_latex_table(
    caption: str,
    label: str,
    headers: list[str],
    rows: list[dict[str, str]],
    is_synthetic: bool,
) -> str:
    col_spec = "l" + "r" * (len(headers) - 1)
    cap_text = f"{SYNTHETIC_TITLE_TAG} {caption}" if is_synthetic else caption
    lines: list[str] = []
    if is_synthetic:
        lines.append(f"% {SYNTHETIC_BANNER}")
    lines.extend([
        r"\begin{table}[htbp]",
        r"\centering",
        f"\\caption{{{_latex_escape(cap_text)}}}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        " & ".join(_latex_escape(h) for h in headers) + r" \\",
        r"\midrule",
    ])
    for row in rows:
        lines.append(" & ".join(_latex_escape(row[h]) for h in headers) + r" \\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    return "\n".join(lines) + "\n"


def _render_csv_table(headers: list[str], rows: list[dict[str, str]], is_synthetic: bool) -> str:
    buf = io.StringIO()
    if is_synthetic:
        buf.write(f"# {SYNTHETIC_BANNER}\n")
    writer = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({h: row[h] for h in headers})
    return buf.getvalue()


def generate_all_tables(
    report: dict[str, Any],
    output_dir: Path,
    *,
    force_synthetic: bool = False,
) -> dict[str, str]:
    """Generate Markdown, LaTeX, and CSV tables from an S5-D1 evaluation report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    is_synthetic = bool(report.get("is_synthetic", False)) or force_synthetic
    pref = _prefix(is_synthetic)

    specs = [
        (
            "system_effectiveness_summary",
            "S5-D1 Per-System Effectiveness Summary (Strict grade==2 & Lenient grade>=1)",
            "tab:s5d1_system_summary",
            _build_main_summary_rows(report, is_synthetic),
        ),
        (
            "fallback_and_shortlist_accounting",
            "S5-D1 Fallback Stratification and Short-List Accounting",
            "tab:s5d1_fallback_shortlist",
            _build_fallback_shortlist_rows(report, is_synthetic),
        ),
        (
            "one_hop_vs_two_hop_comparison",
            "S5-D1 One-Hop vs Two-Hop Descriptive Comparison (2-Hop minus 1-Hop)",
            "tab:s5d1_hop_comparison",
            _build_hop_rows(report, is_synthetic),
        ),
    ]

    written: dict[str, str] = {}
    for stem, title, label, rows in specs:
        headers = list(rows[0].keys()) if rows else ["data_origin"]
        md_path = output_dir / f"{pref}{stem}.md"
        tex_path = output_dir / f"{pref}{stem}.tex"
        csv_path = output_dir / f"{pref}{stem}.csv"

        md_path.write_text(_render_markdown_table(title, headers, rows, is_synthetic), encoding="utf-8")
        tex_path.write_text(_render_latex_table(title, label, headers, rows, is_synthetic), encoding="utf-8")
        csv_path.write_text(_render_csv_table(headers, rows, is_synthetic), encoding="utf-8")

        written[f"{stem}_md"] = str(md_path)
        written[f"{stem}_tex"] = str(tex_path)
        written[f"{stem}_csv"] = str(csv_path)

    return written

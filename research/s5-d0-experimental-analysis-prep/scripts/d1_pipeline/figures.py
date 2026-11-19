"""Reproducible zero-dependency SVG figure generators for S5-D1 evaluation reports."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from d1_pipeline.constants import (
    SVG_AXIS_FONT_SIZE,
    SVG_BAR_GROUP_PADDING,
    SVG_GRID_STEPS,
    SVG_HEIGHT,
    SVG_LEGEND_FONT_SIZE,
    SVG_MARGIN_BOTTOM,
    SVG_MARGIN_LEFT,
    SVG_MARGIN_RIGHT,
    SVG_MARGIN_TOP,
    SVG_SUBTITLE_FONT_SIZE,
    SVG_TITLE_FONT_SIZE,
    SVG_WATERMARK_FONT_SIZE,
    SVG_WIDTH,
    SYNTHETIC_BANNER,
    SYNTHETIC_PREFIX,
    SYNTHETIC_TITLE_TAG,
)

PALETTE = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728")
BG_COLOR = "#ffffff"
GRID_COLOR = "#e2e8f0"
AXIS_COLOR = "#334155"
TEXT_COLOR = "#0f172a"
WATERMARK_COLOR = "#dc2626"
WATERMARK_OPACITY = 0.14
WATERMARK_ROTATION_DEG = -28
LEGEND_BOX_SIZE = 12
LEGEND_ITEM_SPACING = 155
BAR_LABEL_OFFSET_Y = 5
AXIS_LABEL_ROTATE_DEG = -20
AXIS_LABEL_Y_OFFSET = 22
SUBTITLE_Y_OFFSET = 46
TITLE_Y_OFFSET = 26
LEGEND_Y_OFFSET = 64
ZERO_LINE_STROKE_WIDTH = 1.5
PLOT_MIN_Y_MAX = 1.0


def _svg_header(title: str, subtitle: str, is_synthetic: bool) -> list[str]:
    full_title = f"{SYNTHETIC_TITLE_TAG} {title}" if is_synthetic else title
    desc = SYNTHETIC_BANNER if is_synthetic else "Validated S5-D1 Evaluation Figure"
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" '
        f'viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img">',
        f"  <title>{escape(full_title)}</title>",
        f"  <desc>{escape(desc)}</desc>",
        f'  <rect width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="{BG_COLOR}" />',
        f'  <text x="{SVG_WIDTH / 2:.1f}" y="{TITLE_Y_OFFSET}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="{SVG_TITLE_FONT_SIZE}" font-weight="bold" '
        f'fill="{TEXT_COLOR}">{escape(full_title)}</text>',
        f'  <text x="{SVG_WIDTH / 2:.1f}" y="{SUBTITLE_Y_OFFSET}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="{SVG_SUBTITLE_FONT_SIZE}" fill="{AXIS_COLOR}">'
        f"{escape(subtitle)}</text>",
    ]
    return lines


def _svg_watermark(is_synthetic: bool) -> list[str]:
    if not is_synthetic:
        return []
    cx = SVG_WIDTH / 2.0
    cy = SVG_HEIGHT / 2.0
    return [
        f'  <text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="{SVG_WATERMARK_FONT_SIZE}" font-weight="bold" '
        f'fill="{WATERMARK_COLOR}" fill-opacity="{WATERMARK_OPACITY}" '
        f'transform="rotate({WATERMARK_ROTATION_DEG} {cx:.1f} {cy:.1f})">SYNTHETIC</text>',
    ]


def _render_grouped_bar_svg(
    *,
    title: str,
    subtitle: str,
    categories: list[str],
    series: list[tuple[str, list[float]]],
    is_synthetic: bool,
    y_max: float = PLOT_MIN_Y_MAX,
) -> str:
    plot_w = SVG_WIDTH - SVG_MARGIN_LEFT - SVG_MARGIN_RIGHT
    plot_h = SVG_HEIGHT - SVG_MARGIN_TOP - SVG_MARGIN_BOTTOM
    y_top = SVG_MARGIN_TOP
    y_bottom = SVG_MARGIN_TOP + plot_h

    lines = _svg_header(title, subtitle, is_synthetic)

    # Legend
    n_series = max(len(series), 1)
    legend_start_x = SVG_MARGIN_LEFT
    for s_idx, (s_name, _) in enumerate(series):
        lx = legend_start_x + s_idx * LEGEND_ITEM_SPACING
        color = PALETTE[s_idx % len(PALETTE)]
        lines.append(
            f'  <rect x="{lx:.1f}" y="{LEGEND_Y_OFFSET - LEGEND_BOX_SIZE + 2}" '
            f'width="{LEGEND_BOX_SIZE}" height="{LEGEND_BOX_SIZE}" fill="{color}" />'
        )
        lines.append(
            f'  <text x="{lx + LEGEND_BOX_SIZE + 6:.1f}" y="{LEGEND_Y_OFFSET}" '
            f'font-family="sans-serif" font-size="{SVG_LEGEND_FONT_SIZE}" fill="{TEXT_COLOR}">'
            f"{escape(s_name)}</text>"
        )

    # Horizontal gridlines & Y ticks
    for step in range(SVG_GRID_STEPS + 1):
        frac = step / float(SVG_GRID_STEPS)
        val = y_max * frac
        yy = y_bottom - frac * plot_h
        lines.append(
            f'  <line x1="{SVG_MARGIN_LEFT}" y1="{yy:.1f}" x2="{SVG_MARGIN_LEFT + plot_w}" '
            f'y2="{yy:.1f}" stroke="{GRID_COLOR}" stroke-width="1" />'
        )
        lines.append(
            f'  <text x="{SVG_MARGIN_LEFT - 8}" y="{yy + 4:.1f}" text-anchor="end" '
            f'font-family="sans-serif" font-size="{SVG_AXIS_FONT_SIZE}" fill="{AXIS_COLOR}">'
            f"{val:.2f}</text>"
        )

    # Axes
    lines.append(
        f'  <line x1="{SVG_MARGIN_LEFT}" y1="{y_top}" x2="{SVG_MARGIN_LEFT}" y2="{y_bottom}" '
        f'stroke="{AXIS_COLOR}" stroke-width="{ZERO_LINE_STROKE_WIDTH}" />'
    )
    lines.append(
        f'  <line x1="{SVG_MARGIN_LEFT}" y1="{y_bottom}" x2="{SVG_MARGIN_LEFT + plot_w}" '
        f'y2="{y_bottom}" stroke="{AXIS_COLOR}" stroke-width="{ZERO_LINE_STROKE_WIDTH}" />'
    )

    # Bars
    n_cats = max(len(categories), 1)
    cat_slot = plot_w / float(n_cats)
    group_w = cat_slot * (1.0 - SVG_BAR_GROUP_PADDING)
    bar_w = group_w / float(n_series)

    for c_idx, cat in enumerate(categories):
        group_x = SVG_MARGIN_LEFT + c_idx * cat_slot + (cat_slot - group_w) / 2.0
        for s_idx, (_, values) in enumerate(series):
            val = values[c_idx] if c_idx < len(values) else 0.0
            clamped = max(0.0, min(val, y_max))
            bar_h = (clamped / y_max) * plot_h if y_max > 0 else 0.0
            bx = group_x + s_idx * bar_w
            by = y_bottom - bar_h
            color = PALETTE[s_idx % len(PALETTE)]
            lines.append(
                f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{max(bar_w - 2.0, 2.0):.1f}" '
                f'height="{bar_h:.1f}" fill="{color}" />'
            )
            lines.append(
                f'  <text x="{bx + bar_w / 2.0:.1f}" y="{by - BAR_LABEL_OFFSET_Y:.1f}" '
                f'text-anchor="middle" font-family="sans-serif" font-size="9" fill="{TEXT_COLOR}">'
                f"{val:.2f}</text>"
            )

        label_x = SVG_MARGIN_LEFT + (c_idx + 0.5) * cat_slot
        label_y = y_bottom + AXIS_LABEL_Y_OFFSET
        lines.append(
            f'  <text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="end" '
            f'font-family="sans-serif" font-size="{SVG_AXIS_FONT_SIZE}" fill="{TEXT_COLOR}" '
            f'transform="rotate({AXIS_LABEL_ROTATE_DEG} {label_x:.1f} {label_y:.1f})">'
            f"{escape(cat)}</text>"
        )

    lines.extend(_svg_watermark(is_synthetic))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def generate_all_figures(
    report: dict[str, Any],
    output_dir: Path,
    *,
    force_synthetic: bool = False,
) -> dict[str, str]:
    """Generate reproducible SVG figures from an S5-D1 evaluation report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    is_synthetic = bool(report.get("is_synthetic", False)) or force_synthetic
    pref = SYNTHETIC_PREFIX if is_synthetic else ""

    systems = list(report["systems"].keys())
    strict_ndcg10 = [float(report["systems"][s]["strict_summary"]["macro_mean"]["ndcg_at_10"] or 0.0) for s in systems]
    lenient_ndcg10 = [float(report["systems"][s]["lenient_summary"]["macro_mean"]["ndcg_at_10"] or 0.0) for s in systems]
    strict_mrr10 = [float(report["systems"][s]["strict_summary"]["macro_mean"]["mrr_at_10"] or 0.0) for s in systems]
    strict_p5 = [float(report["systems"][s]["strict_summary"]["macro_mean"]["precision_at_5"] or 0.0) for s in systems]

    fig1_path = output_dir / f"{pref}fig1_system_effectiveness.svg"
    fig1_svg = _render_grouped_bar_svg(
        title="S5-D1 Per-System Effectiveness Overview",
        subtitle="Descriptive macro means across answerable queries (no statistical claims)",
        categories=systems,
        series=[
            ("Strict nDCG@10", strict_ndcg10),
            ("Lenient nDCG@10", lenient_ndcg10),
            ("Strict MRR@10", strict_mrr10),
            ("Strict P@5", strict_p5),
        ],
        is_synthetic=is_synthetic,
    )
    fig1_path.write_text(fig1_svg, encoding="utf-8")

    # Figure 2: Fallback vs Non-Fallback Strict nDCG@10
    fb_vals = [
        float(report["systems"][s]["fallback_analysis"]["fallback_strict_mean"]["ndcg_at_10"] or 0.0)
        for s in systems
    ]
    non_fb_vals = [
        float(report["systems"][s]["fallback_analysis"]["non_fallback_strict_mean"]["ndcg_at_10"] or 0.0)
        for s in systems
    ]
    fig2_path = output_dir / f"{pref}fig2_fallback_vs_nonfallback.svg"
    fig2_svg = _render_grouped_bar_svg(
        title="S5-D1 Fallback vs Non-Fallback Strict nDCG@10",
        subtitle="Comparing fallback-triggered vs native graph/retrieval queries per system",
        categories=systems,
        series=[
            ("Non-Fallback nDCG@10", non_fb_vals),
            ("Fallback nDCG@10", fb_vals),
        ],
        is_synthetic=is_synthetic,
    )
    fig2_path.write_text(fig2_svg, encoding="utf-8")

    return {
        "fig1_system_effectiveness_svg": str(fig1_path),
        "fig2_fallback_vs_nonfallback_svg": str(fig2_path),
    }

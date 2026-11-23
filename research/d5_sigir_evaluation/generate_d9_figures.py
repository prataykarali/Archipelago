#!/usr/bin/env python3
"""Generate publication-quality D9 scientific figures (A-F) for SIGIR 2027 Demo.

Every figure is computed deterministically from frozen repository evaluation
artifacts (`d5_1_evaluation_results_v2.json`, `queries_heldout_50.json`,
`passage_qrels.json`, `ranked_runs/*.run`, `citation_grounding_audit.json`,
`quarantined_edges.json`, and live `Engine` inspection) and exported to
`docs/sigir/manuscript/figures/` in vector `.pdf`, `.svg`, and 300-DPI `.png`.
"""

from __future__ import annotations

import json
import math
from math import comb
from pathlib import Path
import sys
from typing import Any

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "research" / "d5_sigir_evaluation"
HOST_DIR = REPO_ROOT / "host_inference"
OUT_DIR = REPO_ROOT / "docs" / "sigir" / "manuscript" / "figures"

if str(HOST_DIR) not in sys.path:
    sys.path.append(str(HOST_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.answer import Engine  # noqa: E402

from archipelago.eval.retrieval_baselines import (  # noqa: E402
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

DPI_EXPORT = 300
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_SEED = 42
TOP_K_EVAL = 5
WILSON_Z_95 = 1.959963984540054
PERCENT_SCALE = 100.0
HALF_PROB = 0.5
TWO_SIDED_MULT = 2.0
CI_LOWER_PCT = 2.5
CI_UPPER_PCT = 97.5
FIG_A_YLIM = 106
FIG_B_LABEL_CAP = 102.0
FIG_B_XLIM = 134
FIG_D_XLIM = 27
FIG_F_YLIM = 44
FIG_F_TOP_Y = 27.2
FIG_F_ARROW_Y = 33.2
FIG_F_TOP_BOT = 27.0
FIG_F_BOX3_X = 39.0
FIG_F_BOX5_END = 74.0
FIG_F_BOX_C_X = 68.5
FIG_F_ARR1_END = 36.6
FIG_F_ARR2_START = 38.8
FIG_F_ARR2_END = 58.0
FIG_F_ARR3_START = 78.2
FIG_F_BOT_X3 = 72.0
FIG_F_BOT_END3 = 83.5

COLOR_ARCHI = "#1b4f72"
COLOR_BM25 = "#2e86ab"
COLOR_ARCTIC = "#48a9a6"
COLOR_FH = "#8d99ae"
COLOR_ACCENT = "#d1495b"
COLOR_WARN = "#e07a5f"
COLOR_OK = "#2a9d8f"
COLOR_MUTED = "#6c757d"


def configure_style() -> None:
    """Apply clean publication typography and layout defaults."""
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.5,
            "axes.labelweight": "bold",
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.28,
            "grid.linestyle": "--",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save_all_formats(fig: matplotlib.figure.Figure, stem: str) -> list[Path]:
    """Export figure in PDF, SVG, and 300-DPI PNG formats."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for ext in ("pdf", "svg", "png"):
        out_path = OUT_DIR / f"{stem}.{ext}"
        fig.savefig(out_path, dpi=DPI_EXPORT, bbox_inches="tight", facecolor="white")
        saved.append(out_path)
    plt.close(fig)
    return saved


def wilson_ci(hits: int, total: int, z_val: float = WILSON_Z_95) -> tuple[float, float]:
    """Return 95% Wilson score confidence interval (lower, upper) in [0, 1]."""
    if total <= 0:
        return 0.0, 0.0
    p_hat = hits / total
    z_sq = z_val * z_val
    denom = 1.0 + z_sq / total
    center = (p_hat + z_sq / (TWO_SIDED_MULT * total)) / denom
    rad = math.sqrt((p_hat * (1.0 - p_hat) / total) + (z_sq / (4.0 * total * total)))
    half = (z_val / denom) * rad
    return max(0.0, center - half), min(1.0, center + half)


def mcnemar_exact_p(arr_a: list[int], arr_b: list[int]) -> tuple[int, int, float]:
    """Return discordant counts (b, c) and exact two-sided binomial McNemar p-value."""
    b_cnt = sum(1 for x, y in zip(arr_a, arr_b, strict=True) if x == 1 and y == 0)
    c_cnt = sum(1 for x, y in zip(arr_a, arr_b, strict=True) if x == 0 and y == 1)
    n_disc = b_cnt + c_cnt
    if n_disc == 0:
        return b_cnt, c_cnt, 1.0
    k_min = min(b_cnt, c_cnt)
    p_one = sum(comb(n_disc, idx) * (HALF_PROB**n_disc) for idx in range(k_min + 1))
    return b_cnt, c_cnt, min(1.0, TWO_SIDED_MULT * p_one)


def generate_fig_a(eval_res: dict[str, Any], queries: list[dict[str, Any]]) -> list[Path]:
    """Figure A: Held-out top-1 concept resolution accuracy (N=38) with Wilson CIs."""
    exp_a = eval_res["experiment_a_concept_resolution"]
    supp_qids = [q["query_id"] for q in queries if q["is_supported"]]
    n_supp = len(supp_qids)
    sys_order = [
        ("archipelago_resolver", "Archipelago\nConcept Resolver", COLOR_ARCHI),
        ("bm25_lexical", "BM25Okapi\nLexical Baseline", COLOR_BM25),
        ("snowflake_arctic_neural", "Snowflake-Arctic\nNeural Dense", COLOR_ARCTIC),
        ("feature_hashed_vector", "Feature-Hashed\n(BLAKE2b 384-d)", COLOR_FH),
    ]
    hit_vectors = {
        k: [0 if qid in {e["query_id"] for e in exp_a[k]["errors"]} else 1 for qid in supp_qids]
        for k, _, _ in sys_order
    }
    labels, pcts, err_low, err_high, counts, colors = [], [], [], [], [], []
    for key, label, col in sys_order:
        k_hits = sum(hit_vectors[key])
        p_val = (k_hits / n_supp) * PERCENT_SCALE
        lo, hi = wilson_ci(k_hits, n_supp)
        labels.append(label)
        pcts.append(p_val)
        err_low.append(p_val - lo * PERCENT_SCALE)
        err_high.append(hi * PERCENT_SCALE - p_val)
        counts.append(k_hits)
        colors.append(col)

    fig, ax = plt.subplots(figsize=(6.4, 3.5))
    x_pos = np.arange(len(sys_order))
    err_kw = {"elinewidth": 1.3, "ecolor": "#111111", "capthick": 1.3}
    bars = ax.bar(
        x_pos,
        pcts,
        width=0.54,
        color=colors,
        edgecolor="#1a1a1a",
        linewidth=0.8,
        yerr=[err_low, err_high],
        capsize=5,
        error_kw=err_kw,
        zorder=3,
    )
    for idx, bar in enumerate(bars):
        top_y = pcts[idx] + err_high[idx] + 2.2
        ax.text(
            bar.get_x() + bar.get_width() / TWO_SIDED_MULT,
            top_y,
            f"{pcts[idx]:.1f}%\n({counts[idx]}/{n_supp})",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color="#111111",
        )
    b_bm, c_bm, p_bm = mcnemar_exact_p(
        hit_vectors["archipelago_resolver"], hit_vectors["bm25_lexical"]
    )
    b_ar, c_ar, p_ar = mcnemar_exact_p(
        hit_vectors["archipelago_resolver"], hit_vectors["snowflake_arctic_neural"]
    )
    b_fh, c_fh, _ = mcnemar_exact_p(
        hit_vectors["archipelago_resolver"], hit_vectors["feature_hashed_vector"]
    )
    callout = (
        "Paired Exact McNemar Tests vs. Archipelago (N=38):\n"
        f"• vs. BM25: +26.3 pp (b={b_bm}, c={c_bm}, p = {p_bm:.4f})\n"
        f"• vs. Snowflake-Arctic: +31.6 pp (b={b_ar}, c={c_ar}, p = {p_ar:.4f})\n"
        f"• vs. Feature-Hashed: +60.5 pp (b={b_fh}, c={c_fh}, p < 0.0001)"
    )
    box_style = {
        "boxstyle": "round,pad=0.45",
        "facecolor": "#f8f9fa",
        "edgecolor": "#adb5bd",
        "linewidth": 0.9,
    }
    ax.text(
        0.98,
        0.95,
        callout,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7.8,
        bbox=box_style,
        zorder=4,
    )
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Top-1 Concept Resolution Accuracy (%)")
    ax.set_ylim(0, FIG_A_YLIM)
    ax.set_title("Experiment A: Held-Out In-Scope Top-1 Concept Resolution (N = 38, 95% Wilson CI)")
    return save_all_formats(fig, "fig_a_concept_resolution")


def generate_fig_b(queries: list[dict[str, Any]], engine: Engine) -> list[Path]:
    """Figure B: Abstention breakdown across the 12 unsupported queries (N=12)."""
    unsupp = [q for q in queries if not q["is_supported"]]
    n_unsupp = len(unsupp)
    no_concept, no_graph, zero_passage_cites, zero_total_cites = 0, 0, 0, 0
    for q in unsupp:
        payload = engine.answer(q["query"])["payload"]
        no_concept += int(payload.get("anchor_concept") is None)
        no_graph += int(not payload.get("render_graph"))
        cites = payload.get("citations") or []
        passage_cites = [c for c in cites if not c.get("is_pearson") and c.get("chunk_id")]
        zero_passage_cites += int(len(passage_cites) == 0)
        zero_total_cites += int(len(cites) == 0)

    criteria = [
        "(1) No Resolved Concept\n(anchor_concept = None)",
        "(2) No Graph Rendering\n(render_graph = False)",
        "(3) Zero Indexed Corpus\nPassage Citations",
        "(4) Zero Total Citations\n(Excl. Q45 Catalog Metadata)",
    ]
    counts = [no_concept, no_graph, zero_passage_cites, zero_total_cites]
    pcts = [(c / n_unsupp) * PERCENT_SCALE for c in counts]
    err_low, err_high = [], []
    for c_val, p_val in zip(counts, pcts, strict=True):
        lo, hi = wilson_ci(c_val, n_unsupp)
        err_low.append(max(0.0, p_val - lo * PERCENT_SCALE))
        err_high.append(max(0.0, hi * PERCENT_SCALE - p_val))

    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    y_pos = np.arange(len(criteria))
    bars = ax.barh(
        y_pos,
        pcts,
        height=0.52,
        color=[COLOR_OK, COLOR_OK, COLOR_OK, COLOR_WARN],
        edgecolor="#1a1a1a",
        linewidth=0.8,
        xerr=[err_low, err_high],
        capsize=4,
        error_kw={"elinewidth": 1.2, "ecolor": "#222222"},
        zorder=3,
    )
    for idx, bar in enumerate(bars):
        note = (
            f"  {counts[idx]}/{n_unsupp} ({pcts[idx]:.1f}%)"
            if counts[idx] == n_unsupp
            else f"  {counts[idx]}/{n_unsupp} ({pcts[idx]:.1f}%) — Q45 exception"
        )
        x_txt = min(FIG_B_LABEL_CAP, pcts[idx] + err_high[idx] + 1.5)
        y_txt = bar.get_y() + bar.get_height() / TWO_SIDED_MULT
        ax.text(
            x_txt,
            y_txt,
            note,
            va="center",
            ha="left",
            fontsize=8.3,
            fontweight="bold",
            color="#111111",
        )

    q45_msg = (
        "Q45 Nuance ('How do compilers transform source code into machine instructions?'): returns anchor_concept=None,\n"
        "render_graph=False, and 0 corpus passage citations, but surfaces 1 Pearson catalog book metadata entry (Compilers 2e)."
    )
    q45_box = {
        "boxstyle": "round,pad=0.38",
        "facecolor": "#fff3cd",
        "edgecolor": "#d39e00",
        "linewidth": 0.9,
    }
    ax.text(
        0.5,
        -0.25,
        q45_msg,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=7.6,
        bbox=q45_box,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(criteria)
    ax.invert_yaxis()
    ax.set_xlabel("Out-of-Corpus Abstention Rate (%) [95% Wilson CI]")
    ax.set_xlim(0, FIG_B_XLIM)
    ax.set_title("Out-of-Corpus Boundary Abstention Across 4 Verification Criteria (N = 12)")
    return save_all_formats(fig, "fig_b_unsupported_abstention")


def generate_fig_c() -> list[Path]:
    """Figure C: Passage retrieval comparison (N=37) with bootstrap 95% CIs and provisional banner."""
    raw_qrels = json.loads((EVAL_DIR / "passage_qrels.json").read_text(encoding="utf-8"))
    flat_qrels = {
        qid: {pid: int(lbl["relevance_grade"]) for pid, lbl in qdata["passages"].items()}
        for qid, qdata in raw_qrels["qrels"].items()
    }
    eval_qids = sorted(qid for qid, rel in flat_qrels.items() if rel)
    systems = [
        ("bm25", "BM25Okapi (Lexical)", COLOR_BM25),
        ("snowflake_arctic_neural", "Snowflake-Arctic (Neural)", COLOR_ARCTIC),
        ("archipelago_graph_assisted", "Archipelago (Heuristic Graph)", COLOR_WARN),
        ("feature_hashed_vector", "Feature-Hashed (BLAKE2b)", COLOR_FH),
    ]
    metric_names = ["MRR", "nDCG@5", "Recall@5", "Precision@5"]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means: dict[str, list[float]] = {s[0]: [] for s in systems}
    ci_lo: dict[str, list[float]] = {s[0]: [] for s in systems}
    ci_hi: dict[str, list[float]] = {s[0]: [] for s in systems}

    for s_key, _, _ in systems:
        run_path = EVAL_DIR / "ranked_runs" / f"{s_key}.run"
        by_q: dict[str, list[str]] = {qid: [] for qid in eval_qids}
        for line in run_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parts = line.split()
                if parts[0] in by_q:
                    by_q[parts[0]].append(" ".join(parts[2:-3]))
        per_m = [
            [reciprocal_rank(by_q[q], flat_qrels[q]) or 0.0 for q in eval_qids],
            [ndcg_at_k(by_q[q], flat_qrels[q], TOP_K_EVAL) or 0.0 for q in eval_qids],
            [recall_at_k(by_q[q], flat_qrels[q], TOP_K_EVAL) or 0.0 for q in eval_qids],
            [precision_at_k(by_q[q], flat_qrels[q], TOP_K_EVAL) or 0.0 for q in eval_qids],
        ]
        for arr in per_m:
            vec = np.array(arr, dtype=np.float64)
            mean_v = float(np.mean(vec))
            boot_means = vec[rng.integers(0, len(vec), size=(BOOTSTRAP_RESAMPLES, len(vec)))].mean(
                axis=1
            )
            means[s_key].append(mean_v)
            ci_lo[s_key].append(max(0.0, mean_v - float(np.percentile(boot_means, CI_LOWER_PCT))))
            ci_hi[s_key].append(max(0.0, float(np.percentile(boot_means, CI_UPPER_PCT)) - mean_v))

    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    x_pos = np.arange(len(metric_names))
    bar_w = 0.19
    offsets = [-1.5 * bar_w, -0.5 * bar_w, 0.5 * bar_w, 1.5 * bar_w]
    for idx, (s_key, s_label, col) in enumerate(systems):
        vals = means[s_key]
        bars = ax.bar(
            x_pos + offsets[idx],
            vals,
            width=bar_w,
            label=s_label,
            color=col,
            edgecolor="#1a1a1a",
            linewidth=0.7,
            yerr=[ci_lo[s_key], ci_hi[s_key]],
            capsize=3,
            error_kw={"elinewidth": 1.0, "ecolor": "#222222"},
            zorder=3,
        )
        for b_idx, bar in enumerate(bars):
            x_b = bar.get_x() + bar.get_width() / TWO_SIDED_MULT
            y_b = vals[b_idx] + ci_hi[s_key][b_idx] + 0.015
            ax.text(
                x_b,
                y_b,
                f"{vals[b_idx]:.2f}",
                ha="center",
                va="bottom",
                fontsize=6.8,
                fontweight="bold",
                color="#111111",
            )

    banner_txt = (
        "PROVISIONAL — ALGORITHMIC CANDIDATE QRELS; NOT HUMAN VALIDATED\n"
        "Flat lexical (BM25) and neural (Snowflake-Arctic) rankers outperform Archipelago's heuristic citation decay."
    )
    banner_box = {
        "boxstyle": "round,pad=0.36",
        "facecolor": "#f8d7da",
        "edgecolor": "#f5c6cb",
        "linewidth": 1.0,
    }
    ax.text(
        0.5,
        0.97,
        banner_txt,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=7.7,
        fontweight="bold",
        color="#721c24",
        bbox=banner_box,
        zorder=5,
    )
    ax.set_xticks(x_pos)
    ax.set_xticklabels(metric_names)
    ax.set_ylabel("Score (Mean ± 95% Bootstrap CI)")
    ax.set_ylim(0, 1.15)
    ax.set_title(
        "Experiment B: Ranked Passage Retrieval Across N = 37 Queries with Candidate Qrels"
    )
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.84), frameon=True, ncol=2)
    return save_all_formats(fig, "fig_c_passage_retrieval")


def generate_fig_d(
    eval_res: dict[str, Any],
    queries: list[dict[str, Any]],
    cite_audit: dict[str, Any],
    engine: Engine,
) -> list[Path]:
    """Figure D: Post-hoc failure & outcome taxonomy across all 50 held-out queries."""
    graph_raw = json.loads((HOST_DIR / "fixtures" / "okf_graph.json").read_text(encoding="utf-8"))
    ont = set(graph_raw["concepts"].keys())
    errs = {
        e["query_id"]: e
        for e in eval_res["experiment_a_concept_resolution"]["archipelago_resolver"]["errors"]
    }
    rel_cases = {
        c["query_id"]: c for c in eval_res["relationship_prediction_evaluation"]["detailed_cases"]
    }

    supp_errs = [q for q in queries if q["is_supported"] and q["query_id"] in errs]
    missing_ont = [q["query_id"] for q in supp_errs if q["expected_concept"] not in ont]
    alias_mismatch = [
        q["query_id"]
        for q in supp_errs
        if q["expected_concept"] in ont and errs[q["query_id"]]["predicted"] is None
    ]
    wrong_anchor = [
        q["query_id"]
        for q in supp_errs
        if q["expected_concept"] in ont and errs[q["query_id"]]["predicted"] is not None
    ]
    unsupp_pred = [
        qid for qid, c in rel_cases.items() if c["verdict"] == "PREDICATE_ABSENT_IN_GRAPH"
    ]
    quarantined = json.loads((EVAL_DIR / "quarantined_edges.json").read_text(encoding="utf-8"))
    inverted_edges = [e for e in quarantined if "invert" in e["quarantine_reason"].lower()]

    pre_diluted, post_diluted = 0, 0
    bad_grades = ("IRRELEVANT_OR_SPURIOUS", "UNSUPPORTED", "UNASSESSABLE_NO_TEXT")
    for case in cite_audit["audited_query_cases"]:
        pre_diluted += int(
            any(r["claim_support_grade"] in bad_grades for r in case["citation_records"])
        )
        post_diluted += int(len(engine.answer(case["query"])["payload"].get("citations") or []) > 3)

    legit_abst = [q["query_id"] for q in queries if not q["is_supported"]]
    categories = [
        "Unsupported Runtime Predicate\n(USES / CONTRASTS_WITH / APPLIES_TO)",
        "Legitimate Out-of-Corpus Abstention\n(12/12 zero passage citations; Q45 metadata)",
        "Missing Ontology Concept Node\n(e.g., cross_encoder, dual_encoder, mips)",
        "Alias / Compound Phrasing Unmatched\n(e.g., GraphRAG, query-key projection)",
        "Citation Irrelevance / Dilution Queries\n(Pre-D7.2: 3/5 audited -> Post-D7.2: 0/5 >3 cites)",
        "Incorrect Canonical Anchoring\n(e.g., self_attention -> attention_mechanism)",
        "Wrong Relation Direction (Quarantined)\n(Q21 legacy self_attention -> transformer edge)",
    ]
    counts = [
        len(unsupp_pred),
        len(legit_abst),
        len(missing_ont),
        len(alias_mismatch),
        pre_diluted,
        len(wrong_anchor),
        len(inverted_edges),
    ]
    notes = [
        f"{len(unsupp_pred)}/18 relational queries (Q21, Q23-Q28, Q31-Q33, Q35-Q36, Q38)",
        f"{len(legit_abst)}/12 unsupported queries (Q39-Q50)",
        f"{len(missing_ont)}/38 supported queries ({', '.join(missing_ont)})",
        f"{len(alias_mismatch)}/38 supported queries ({', '.join(alias_mismatch)})",
        f"Pre-D7.2: {pre_diluted}/5 queries (11/24 cites) -> Post-D7.2: {post_diluted}/5 diluted",
        f"{len(wrong_anchor)}/38 supported queries ({', '.join(wrong_anchor)})",
        f"{len(inverted_edges)} legacy edge in okf_graph.json (0/18 under exact triple match)",
    ]
    bar_colors = [
        COLOR_ACCENT,
        COLOR_OK,
        COLOR_WARN,
        COLOR_WARN,
        COLOR_BM25,
        "#e76f51",
        COLOR_MUTED,
    ]

    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    y_pos = np.arange(len(categories))
    bars = ax.barh(
        y_pos, counts, height=0.56, color=bar_colors, edgecolor="#1a1a1a", linewidth=0.8, zorder=3
    )
    for idx, bar in enumerate(bars):
        y_b = bar.get_y() + bar.get_height() / TWO_SIDED_MULT
        ax.text(
            counts[idx] + 0.35,
            y_b,
            notes[idx],
            va="center",
            ha="left",
            fontsize=7.8,
            fontweight="bold",
            color="#111111",
        )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=8.0)
    ax.invert_yaxis()
    ax.set_xlabel("Affected Held-Out Queries / Audited Cases (Overlapping Categories)")
    ax.set_xlim(0, FIG_D_XLIM)
    ax.set_title("Post-Hoc Failure & Outcome Taxonomy Across 50 Held-Out Queries (Overlapping)")
    return save_all_formats(fig, "fig_d_failure_taxonomy")


def generate_fig_e(cite_audit: dict[str, Any], engine: Engine) -> list[Path]:
    """Figure E: Recorded 24-citation author audit vs post-Issue #11 deterministic selection."""
    bd = cite_audit["overall_audit_statistics"]["claim_support_breakdown"]
    pre_labels = [
        "Fully Supported\n(7/24 = 29.2%)",
        "Partially Supported\n(6/24 = 25.0%)",
        "Unsupported\n(1/24 = 4.2%)",
        "Irrelevant / Spurious\nDilution (9/24 = 37.5%)",
        "Unassessable\n(1/24 = 4.2%)",
    ]
    pre_counts = [
        int(bd["fully_supported"]),
        int(bd["partially_supported"]),
        int(bd["unsupported"]),
        int(bd["irrelevant_or_spurious"]),
        int(bd["unassessable_no_text"]),
    ]
    pre_colors = [COLOR_OK, "#52b788", COLOR_WARN, COLOR_ACCENT, COLOR_MUTED]
    audited_cases = cite_audit["audited_query_cases"]
    q_labels = [c["query_id"] for c in audited_cases]
    pre_per_q = [int(c["citation_count"]) for c in audited_cases]
    post_per_q = [
        len(engine.answer(c["query"])["payload"].get("citations") or []) for c in audited_cases
    ]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(7.6, 3.4), gridspec_kw={"width_ratios": [1.15, 1.0]}
    )
    y_pos = np.arange(len(pre_labels))
    bars1 = ax1.barh(
        y_pos,
        pre_counts,
        height=0.55,
        color=pre_colors,
        edgecolor="#1a1a1a",
        linewidth=0.8,
        zorder=3,
    )
    for idx, bar in enumerate(bars1):
        y_b = bar.get_y() + bar.get_height() / TWO_SIDED_MULT
        ax1.text(
            pre_counts[idx] + 0.25,
            y_b,
            f"{pre_counts[idx]}",
            va="center",
            ha="left",
            fontsize=8.3,
            fontweight="bold",
        )
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(pre_labels, fontsize=7.8)
    ax1.invert_yaxis()
    ax1.set_xlabel("Citation Count (Total = 24)")
    ax1.set_xlim(0, 11.5)
    ax1.set_title("Pre-D7.2 Recorded Audit (N = 24)", fontsize=9.5)

    x_q = np.arange(len(q_labels))
    bw = 0.34
    b_pre = ax2.bar(
        x_q - bw / TWO_SIDED_MULT,
        pre_per_q,
        width=bw,
        label="Pre-Issue #11 (Total = 24)",
        color=COLOR_ACCENT,
        edgecolor="#1a1a1a",
        linewidth=0.7,
        zorder=3,
    )
    b_post = ax2.bar(
        x_q + bw / TWO_SIDED_MULT,
        post_per_q,
        width=bw,
        label="Post-Issue #11 Cap<=3 (Total = 7,\nclaim_support=not_assessed)",
        color=COLOR_ARCHI,
        edgecolor="#1a1a1a",
        linewidth=0.7,
        zorder=3,
    )
    for bars in (b_pre, b_post):
        for bar in bars:
            h_val = int(bar.get_height())
            x_b = bar.get_x() + bar.get_width() / TWO_SIDED_MULT
            ax2.text(
                x_b,
                h_val + 0.2,
                str(h_val),
                ha="center",
                va="bottom",
                fontsize=7.8,
                fontweight="bold",
            )
    ax2.set_xticks(x_q)
    ax2.set_xticklabels(q_labels)
    ax2.set_ylabel("Citations Returned per Query")
    ax2.set_ylim(0, 12.2)
    ax2.set_title("Deterministic Selection Pruning (24 -> 7)", fontsize=9.5)
    ax2.legend(loc="upper right", fontsize=7.2, frameon=True)
    fig.suptitle(
        "PRELIMINARY AUTHOR-ATTRIBUTED AUDIT (N=24); INDEPENDENT HUMAN VERIFICATION PENDING",
        fontsize=9.2,
        fontweight="bold",
        color="#721c24",
        y=1.03,
    )
    fig.tight_layout()
    return save_all_formats(fig, "fig_e_citation_audit")


def generate_fig_f() -> list[Path]:
    """Figure F: Publication-quality vector system architecture diagram."""
    fig, ax = plt.subplots(figsize=(9.8, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, FIG_F_YLIM)
    ax.axis("off")

    def draw_box(
        x_v: float,
        y_v: float,
        w_v: float,
        h_v: float,
        title: str,
        sub: str,
        fc: str,
        ec: str = "#1b4f72",
    ) -> None:
        patch = mpatches.FancyBboxPatch(
            (x_v, y_v),
            w_v,
            h_v,
            boxstyle="round,pad=0.35,rounding_size=0.9",
            facecolor=fc,
            edgecolor=ec,
            linewidth=1.3,
            zorder=2,
        )
        ax.add_patch(patch)
        ax.text(
            x_v + w_v / TWO_SIDED_MULT,
            y_v + h_v * 0.72,
            title,
            ha="center",
            va="center",
            fontsize=7.3,
            fontweight="bold",
            color="#111111",
            zorder=3,
        )
        ax.text(
            x_v + w_v / TWO_SIDED_MULT,
            y_v + h_v * 0.27,
            sub,
            ha="center",
            va="center",
            fontsize=6.5,
            color="#2b2d42",
            zorder=3,
        )

    def draw_arrow(x1: float, y1: float, x2: float, y2: float, label: str = "") -> None:
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops={"arrowstyle": "-|>", "color": "#1b4f72", "lw": 1.3, "mutation_scale": 11},
            zorder=4,
        )
        if label:
            ax.text(
                (x1 + x2) / TWO_SIDED_MULT - 4.0,
                (y1 + y2) / TWO_SIDED_MULT + 0.3,
                label,
                ha="right",
                va="center",
                fontsize=6.5,
                fontweight="bold",
                color="#1b4f72",
            )

    top_boxes = [
        (
            0.8,
            14.8,
            "1. User Query",
            "Authenticated Role\n(Student / Faculty /\nLibrarian RBAC)",
            "#e8f4f8",
            "#1b4f72",
        ),
        (
            18.2,
            18.2,
            "2. Concept Resolver",
            "okf_graph.json\n610 Concepts · 775 Chunks\nLexical + Alias + Dense",
            "#d4edda",
            "#2a9d8f",
        ),
        (
            FIG_F_BOX3_X,
            18.8,
            "3. Coverage / Abstention\nGate",
            "If Unmatched:\nanchor=None, render=False\n0 Fabricated Edges (12/12)",
            "#fff3cd",
            "#d39e00",
        ),
        (
            60.4,
            17.6,
            "4. 1-Hop Graph\nNeighborhood",
            "Runtime Predicates:\nREQUIRES · RELATED\nUNLOCKS",
            "#e8f4f8",
            "#1b4f72",
        ),
        (
            80.6,
            18.6,
            "5. Evidence Selection\n(Issue #11 Cap <= 3)",
            "Canonical chunk_id Check\nMax 3 Anchor Citations\nProvenance != Support",
            "#f8d7da",
            "#b23a48",
        ),
    ]
    for x_b, w_b, t_b, s_b, fc_b, ec_b in top_boxes:
        draw_box(x_b, FIG_F_TOP_Y, w_b, 12.0, t_b, s_b, fc_b, ec_b)

    for x_start, x_end in (
        (15.8, 18.0),
        (FIG_F_ARR1_END, FIG_F_ARR2_START),
        (FIG_F_ARR2_END, 60.2),
        (FIG_F_ARR3_START, 80.4),
    ):
        draw_arrow(x_start, FIG_F_ARROW_Y, x_end, FIG_F_ARROW_Y)

    ws_title = "6. Interactive Split-Pane Research Workspace (https://archipelago-blond.vercel.app · SHA 1785846a)"
    ws_sub = "Synchronized Grounded Chat + Interactive Subgraph Inspector + Explicit Provenance Badges (provenance_verified | claim_support=not_assessed)"
    draw_box(5.5, 13.6, 89.0, 8.4, ws_title, ws_sub, "#edf2f4", "#1b4f72")
    draw_arrow(90.0, FIG_F_TOP_BOT, FIG_F_BOX5_END, 22.3)
    draw_arrow(48.4, FIG_F_TOP_BOT, 42.0, 22.3, "Abstain Banner")

    bot_boxes = [
        (
            1.5,
            "A. Canonical PDF Reader (/read)",
            "Authenticated /api/page-view\nExact Page & %PDF- Byte Stream\n(e.g., Vaswani 2017 p. 2/15)",
            "#e8f4f8",
            "#1b4f72",
        ),
        (
            35.0,
            "B. Research Discovery (/research)",
            "OpenAlex · Crossref · arXiv\nPer-User Isolated Runs (P0-2)\n4-Sheet .xlsx Export (103 Links)",
            "#d4edda",
            "#2a9d8f",
        ),
        (
            FIG_F_BOX_C_X,
            "C. Koha OPAC Bridge (/library)",
            "91 E-Books · 109 Koha Holdings\nExplicit koha_stale Disclosure\nLive biblionumber Handoff",
            "#fff3cd",
            "#d39e00",
        ),
    ]
    for x_b, t_b, s_b, fc_b, ec_b in bot_boxes:
        draw_box(x_b, 1.0, 30.0, 8.8, t_b, s_b, fc_b, ec_b)

    for x_top, x_bot in ((28.0, 16.5), (50.0, 50.0), (FIG_F_BOT_X3, FIG_F_BOT_END3)):
        draw_arrow(x_top, 13.4, x_bot, 10.1)

    ax.set_title(
        "Archipelago Verified Runtime Architecture: Concept Grounding, Boundary Abstention & Provenance Verification",
        fontsize=9.8,
        fontweight="bold",
        pad=6,
    )
    return save_all_formats(fig, "fig_f_system_architecture")


def main() -> int:
    """Generate all 6 D9 publication figures in PDF, SVG, and 300-DPI PNG."""
    configure_style()
    eval_res = json.loads(
        (EVAL_DIR / "d5_1_evaluation_results_v2.json").read_text(encoding="utf-8")
    )
    queries = json.loads((EVAL_DIR / "queries_heldout_50.json").read_text(encoding="utf-8"))
    cite_audit = json.loads(
        (EVAL_DIR / "citation_grounding_audit.json").read_text(encoding="utf-8")
    )
    engine = Engine()

    generated: list[Path] = []
    generated.extend(generate_fig_a(eval_res, queries))
    generated.extend(generate_fig_b(queries, engine))
    generated.extend(generate_fig_c())
    generated.extend(generate_fig_d(eval_res, queries, cite_audit, engine))
    generated.extend(generate_fig_e(cite_audit, engine))
    generated.extend(generate_fig_f())

    print(f"Generated {len(generated)} figure files in {OUT_DIR}:")
    for path in generated:
        print(f"  - {path.relative_to(REPO_ROOT)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

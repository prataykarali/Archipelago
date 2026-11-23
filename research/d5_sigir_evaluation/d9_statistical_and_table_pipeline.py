"""D9 Phase 3 & 4 Statistical Analysis, Failure Taxonomy, and Table Pipeline (T1-T7)."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from d9_statistics import bootstrap_and_randomization, compute_query_ir_metrics
from scipy.stats import beta, binomtest

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
TABLES_DIR = EVAL_DIR / "d9_tables"
Z_95 = 1.959963984540054
ALPHA_05 = 0.05
BOOTSTRAP_RESAMPLES = 10000
RANDOM_SEED = 20270501
TOP_K_CUTOFF = 5
PERCENT_SCALE = 100.0
HALF_CORRECTION = 0.5
CI_LOW_PCT = 2.5
CI_HIGH_PCT = 97.5
EPSILON = 1e-9
STRICT_ABST_HITS = 11
ROUND_P_DIGITS = 7
ROUND_P5_DIGITS = 5
MAX_REP_QIDS = 8
TOTAL_HELD_QUERIES = 50
K_KEYS = ("k", "n", "proportion", "wilson_95_ci", "clopper_pearson_95_ci")

SYSTEM_LABELS: dict[str, str] = {
    "archipelago_resolver": "Archipelago Concept Resolver",
    "bm25_lexical": "BM25 Lexical (k1=1.5, b=0.75)",
    "snowflake_arctic_neural": "Snowflake-Arctic-Embed-M (fc74610d)",
    "feature_hashed_vector": "Feature-Hashed Vector (BLAKE2b 384-d)",
}
PASSAGE_SYSTEM_LABELS: dict[str, str] = {
    "bm25": "BM25Okapi (k1=1.5, b=0.75)",
    "arctic": "Snowflake-Arctic-Embed-M",
    "archipelago": "Archipelago Graph-Assisted (Heuristic)",
    "feature_hash": "Feature-Hashed (BLAKE2b 384-d)",
}


def wilson_ci(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Compute 95% Wilson score interval for binomial proportion k/n."""
    if n <= 0:
        return (0.0, 0.0)
    p, z2 = k / n, z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
    return (max(0.0, center - half), min(1.0, center + half))


def clopper_pearson_ci(k: int, n: int, alpha: float = ALPHA_05) -> tuple[float, float]:
    """Compute exact 95% Clopper-Pearson interval for binomial proportion k/n."""
    if n <= 0:
        return (0.0, 0.0)
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return (lo, hi)


def _binom_stat(k: int, n: int) -> dict[str, Any]:
    w_ci, cp_ci = list(wilson_ci(k, n)), list(clopper_pearson_ci(k, n))
    return dict(zip(K_KEYS, (k, n, round(k / n, 4), w_ci, cp_ci), strict=True))


def paired_mcnemar_exact(outcomes_a: list[int], outcomes_b: list[int]) -> dict[str, Any]:
    """Compute exact paired McNemar test, Haldane-Anscombe OR, and paired difference 95% CI."""
    n = len(outcomes_a)
    pairs = list(zip(outcomes_a, outcomes_b, strict=True))
    a = sum(1 for x, y in pairs if x == 1 and y == 1)
    b = sum(1 for x, y in pairs if x == 1 and y == 0)
    c = sum(1 for x, y in pairs if x == 0 and y == 1)
    d = sum(1 for x, y in pairs if x == 0 and y == 0)
    p_val = 1.0 if b + c == 0 else float(binomtest(b, b + c, HALF_CORRECTION).pvalue)
    diff = (b - c) / n
    se_wald = math.sqrt(max(0.0, (b + c) - ((b - c) ** 2) / n)) / n
    ci = [round(max(-1.0, diff - Z_95 * se_wald), 4), round(min(1.0, diff + Z_95 * se_wald), 4)]
    or_ex = "inf" if c == 0 and b > 0 else round(b / c, 4) if c > 0 else 1.0
    or_ha = round((b + HALF_CORRECTION) / (c + HALF_CORRECTION), 4)
    res: dict[str, Any] = {"n": n, "both_correct_a": a, "a_only_b": b, "b_only_c": c}
    res.update({"both_wrong_d": d, "discordant_total": b + c, "delta_accuracy": round(diff, 4)})
    res.update(
        {
            "exact_two_sided_p": round(p_val, ROUND_P_DIGITS),
            "delta_ci_95": ci,
            "delta_ci_method": "paired Wald",
        }
    )
    res.update({"odds_ratio_exact": or_ex, "odds_ratio_haldane_anscombe": or_ha})
    return res


def load_trec_run(path: Path) -> dict[str, list[str]]:
    """Load TREC run file into ordered passage ID lists per query_id."""
    runs: dict[str, list[tuple[int, str]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) >= 4:
            runs.setdefault(parts[0], []).append((int(parts[-3]), " ".join(parts[2:-3])))
    return {qid: [pid for _, pid in sorted(items)] for qid, items in runs.items()}


def analyze_failure_taxonomy(
    queries: list[dict[str, Any]],
    archi_exp_a: dict[str, Any],
    exp_c_cases: list[dict[str, Any]],
    graph_data: dict[str, Any],
) -> dict[str, Any]:
    """Classify all 50 held-out queries into the 7 overlapping failure taxonomy categories."""
    node_map = {str(n["id"]): n for n in graph_data.get("nodes", [])}
    node_ids = set(node_map.keys())
    edges = graph_data.get("edges", [])
    edge_preds = {
        str(e.get("edge_type") or e.get("predicate") or e.get("type") or "") for e in edges
    }
    edge_pairs = {
        (str(e["from_id"]), str(e["to_id"])): str(e.get("edge_type") or "") for e in edges
    }
    err_by_q = {e["query_id"]: e for e in archi_exp_a.get("errors", [])}
    exp_c_by_q = {d["query_id"]: d for d in exp_c_cases}
    cats: dict[str, list[str]] = {
        "Missing ontology concept": [],
        "Alias-resolution mismatch": [],
        "Incorrect canonical anchoring": [],
        "Unsupported runtime predicate": [],
        "Wrong relation direction": [],
        "Citation irrelevance": [],
        "Legitimate abstention": [],
    }
    per_query_rows: list[dict[str, Any]] = []
    for q in queries:
        qid, qtext, qlow, cat = q["query_id"], q["query"], q["query"].lower(), q["category"]
        exp_c, gold_set = q.get("expected_concept"), q.get("gold_relevant_concepts", [])
        rel = q.get("expected_relation")
        is_abst = not q.get("is_supported", True)
        hit = qid not in err_by_q if not is_abst else True
        pred = err_by_q[qid].get("predicted") if qid in err_by_q else exp_c
        if qid in exp_c_by_q and exp_c_by_q[qid].get("anchor_resolved"):
            pred = exp_c_by_q[qid]["anchor_resolved"]
        q_tags: list[str] = []
        if is_abst:
            q_tags.append("Legitimate abstention")
        else:
            rel_miss = bool(rel and (rel["from"] not in node_ids or rel["to"] not in node_ids))
            if (exp_c not in node_ids) or rel_miss:
                q_tags.append("Missing ontology concept")
            alias_fail = not hit
            if exp_c in node_map:
                lbl = str(node_map[exp_c].get("label", "")).lower()
                als = [str(a).lower() for a in node_map[exp_c].get("aliases", [])]
                alias_fail = not ((lbl and lbl in qlow) or any(a and a in qlow for a in als))
            if alias_fail and pred != exp_c:
                q_tags.append("Alias-resolution mismatch")
            if not hit or (pred != exp_c):
                q_tags.append("Incorrect canonical anchoring")
            if rel:
                if rel["rel"] not in edge_preds:
                    q_tags.append("Unsupported runtime predicate")
                src, tgt = rel["from"], rel["to"]
                rev = (src, tgt) not in edge_pairs and (tgt, src) in edge_pairs
                if rev or exp_c_by_q.get(qid, {}).get("verdict") == "INVERTED_DIRECTION":
                    q_tags.append("Wrong relation direction")
            if not hit or pred != exp_c or cat == "relational":
                q_tags.append("Citation irrelevance")
        for t in q_tags:
            cats[t].append(qid)
        row = {"query_id": qid, "category": cat, "query": qtext, "expected_concept": exp_c}
        row.update({"gold_concepts": sorted(gold_set), "predicted_concept": pred})
        row.update({"concept_hit": hit, "failure_tags": q_tags})
        per_query_rows.append(row)
    return {"categories": cats, "per_query": per_query_rows}


def _esc(val: Any) -> str:
    return str(val).replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("#", "\\#")


def _write_table(stem: str, spec: dict[str, Any], rows: list[list[str]]) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    headers, caption, label = spec["headers"], spec["caption"], spec["label"]
    with (TABLES_DIR / f"{stem}.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    col_spec = "l" + "r" * (len(headers) - 1)
    hdr_line = " & ".join(f"\\textbf{{{_esc(h)}}}" for h in headers) + " \\\\"
    body = [" & ".join(_esc(c) for c in r) + " \\\\" for r in rows]
    tex = [
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
    ]
    tex.extend([f"\\begin{{tabular}}{{{col_spec}}}", "\\toprule", hdr_line, "\\midrule", *body])
    tex.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    (TABLES_DIR / f"{stem}.tex").write_text("\n".join(tex), encoding="utf-8")


def _fci(ci: list[float]) -> str:
    return f"[{ci[0] * PERCENT_SCALE:.1f}%, {ci[1] * PERCENT_SCALE:.1f}%]"


def _fm(ps: dict[str, Any], mk: str) -> str:
    return f"{ps[mk]['mean']:.3f} [{ps[mk]['ci_95'][0]:.3f}, {ps[mk]['ci_95'][1]:.3f}]"


def _fd(ps: dict[str, Any], mk: str, s: str) -> str:
    if s == "archipelago":
        return "---"
    d, ci = ps[mk]["archipelago_minus_system_diff"], ps[mk]["diff_ci_95"]
    return f"{d:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]"


def run_d9_statistical_pipeline() -> dict[str, Any]:
    """Execute full D9 statistical analysis and write T1-T7 CSV/LaTeX tables + summary JSON."""
    eval_v2 = json.loads((EVAL_DIR / "d5_1_evaluation_results_v2.json").read_text(encoding="utf-8"))
    q_raw = json.loads((EVAL_DIR / "queries_heldout_50.json").read_text(encoding="utf-8"))
    queries = q_raw["queries"] if isinstance(q_raw, dict) else q_raw
    qrels_raw = json.loads((EVAL_DIR / "passage_qrels.json").read_text(encoding="utf-8"))["qrels"]
    qrels = {
        qid: {pid: int(meta["relevance_grade"]) for pid, meta in entry["passages"].items()}
        for qid, entry in qrels_raw.items()
        if any(int(meta["relevance_grade"]) > 0 for meta in entry["passages"].values())
    }
    graph_path = REPO_ROOT / "host_inference" / "cache" / "okf_graph.json"
    if not graph_path.exists():
        graph_path = REPO_ROOT / "host_inference" / "fixtures" / "okf_graph.json"
    graph_data = json.loads(graph_path.read_text(encoding="utf-8"))
    specs = json.loads((TABLES_DIR / "d9_table_specs.json").read_text(encoding="utf-8"))

    exp_a = eval_v2["experiment_a_concept_resolution"]
    sup_qids = [q["query_id"] for q in queries if q.get("is_supported", True)]
    abst_qids = [q["query_id"] for q in queries if not q.get("is_supported", True)]
    n_sup, n_abst = len(sup_qids), len(abst_qids)
    err_sets = {s: {e["query_id"] for e in exp_a[s].get("errors", [])} for s in SYSTEM_LABELS}
    out_sup = {s: [0 if qid in err_sets[s] else 1 for qid in sup_qids] for s in SYSTEM_LABELS}

    exp_a_stats: dict[str, Any] = {}
    for s in SYSTEM_LABELS:
        ks = sum(out_sup[s])
        ka = int(str(exp_a[s]["abstentions_correct"]).split("/")[0])
        st = {"supported": _binom_stat(ks, n_sup), "abstention_corpus": _binom_stat(ka, n_abst)}
        st["overall"] = _binom_stat(ks + ka, n_sup + n_abst)
        exp_a_stats[s] = st
    exp_a_stats["archipelago_resolver"]["abstention_strict_zero_citations"] = _binom_stat(
        STRICT_ABST_HITS, n_abst
    )

    mcnemar: dict[str, Any] = {}
    for b in ("bm25_lexical", "snowflake_arctic_neural", "feature_hashed_vector"):
        res = paired_mcnemar_exact(out_sup["archipelago_resolver"], out_sup[b])
        res["archi_only_queries"] = [
            qid
            for qid in sup_qids
            if qid not in err_sets["archipelago_resolver"] and qid in err_sets[b]
        ]
        res["base_only_queries"] = [
            qid
            for qid in sup_qids
            if qid in err_sets["archipelago_resolver"] and qid not in err_sets[b]
        ]
        mcnemar[f"archipelago_vs_{b}"] = res

    r_files = {"bm25": "bm25.run", "arctic": "snowflake_arctic_neural.run"}
    r_files["archipelago"] = "archipelago_graph_assisted.run"
    r_files["feature_hash"] = "feature_hashed_vector.run"
    runs = {s: load_trec_run(EVAL_DIR / "ranked_runs" / fn) for s, fn in r_files.items()}
    eval_qids = sorted(qrels.keys())
    mkeys = ("mrr", "ndcg@5", "r@5", "p@5")
    per_q: dict[str, dict[str, list[float]]] = {s: {m: [] for m in mkeys} for s in r_files}
    for qid in eval_qids:
        for s in r_files:
            met = compute_query_ir_metrics(runs[s].get(qid, []), qrels[qid], k=TOP_K_CUTOFF)
            for mk in mkeys:
                per_q[s][mk].append(met[mk])

    p_stats: dict[str, Any] = {s: {} for s in r_files}
    for s in r_files:
        for mk in mkeys:
            c = bootstrap_and_randomization(per_q["archipelago"][mk], per_q[s][mk])
            p_stats[s][mk] = {
                "mean": c["mean_b"],
                "std": c["std_b"],
                "ci_95": c["ci_b_95"],
                "archipelago_minus_system_diff": c["mean_diff"],
                "diff_ci_95": c["ci_diff_95"],
                "p_randomization": c["p_randomization"],
                "p_sign_test": c["p_sign_test"],
                "archi_wins": c["wins_a"],
                "ties": c["ties"],
                "archi_losses": c["losses_a"],
            }

    tax = analyze_failure_taxonomy(
        queries,
        exp_a["archipelago_resolver"],
        eval_v2["relationship_prediction_evaluation"]["detailed_cases"],
        graph_data,
    )
    _write_table("t1_dataset_corpus_stats", specs["t1"], specs["t1"]["rows"])

    t2_rows: list[list[str]] = []
    for s, lbl in SYSTEM_LABELS.items():
        sp, ab, ov = (
            exp_a_stats[s]["supported"],
            exp_a_stats[s]["abstention_corpus"],
            exp_a_stats[s]["overall"],
        )
        r = [lbl, str(sp["k"]), str(sp["n"]), f"{sp['proportion'] * PERCENT_SCALE:.1f}%"]
        r += [_fci(sp["wilson_95_ci"]), _fci(sp["clopper_pearson_95_ci"])]
        r += [str(ab["k"]), str(ab["n"]), f"{ab['proportion'] * PERCENT_SCALE:.1f}%"]
        r += [_fci(ab["wilson_95_ci"]), _fci(ab["clopper_pearson_95_ci"])]
        r += [f"{ov['proportion'] * PERCENT_SCALE:.1f}%", _fci(ov["wilson_95_ci"])]
        t2_rows.append(r)
    _write_table("t2_concept_resolution_and_abstention", specs["t2"], t2_rows)

    t3_rows: list[list[str]] = []
    for b in ("bm25_lexical", "snowflake_arctic_neural", "feature_hashed_vector"):
        mc = mcnemar[f"archipelago_vs_{b}"]
        lo, hi = mc["delta_ci_95"][0] * PERCENT_SCALE, mc["delta_ci_95"][1] * PERCENT_SCALE
        qs = ",".join(mc["archi_only_queries"][:MAX_REP_QIDS])
        if len(mc["archi_only_queries"]) > MAX_REP_QIDS:
            qs += "..."
        r = [f"Archipelago vs. {SYSTEM_LABELS[b]}", str(mc["n"]), str(mc["both_correct_a"])]
        r += [str(mc["a_only_b"]), str(mc["b_only_c"]), str(mc["both_wrong_d"])]
        r += [f"+{mc['delta_accuracy'] * PERCENT_SCALE:.1f}%", f"[+{lo:.1f}%, +{hi:.1f}%]"]
        r += [f"{mc['exact_two_sided_p']:.6f}", f"{mc['odds_ratio_haldane_anscombe']:.2f}", qs]
        t3_rows.append(r)
    _write_table("t3_paired_mcnemar_concept_tests", specs["t3"], t3_rows)

    t4_rows: list[list[str]] = []
    for s, lbl in PASSAGE_SYSTEM_LABELS.items():
        ps = p_stats[s]
        p_m = "---" if s == "archipelago" else f"{ps['mrr']['p_randomization']:.4f}"
        p_n = "---" if s == "archipelago" else f"{ps['ndcg@5']['p_randomization']:.4f}"
        r = [lbl, str(len(eval_qids)), "PROVISIONAL (algorithmic)"]
        r += [_fm(ps, "mrr"), _fm(ps, "ndcg@5"), _fm(ps, "r@5"), _fm(ps, "p@5")]
        r += [_fd(ps, "mrr", s), p_m, _fd(ps, "ndcg@5", s), p_n]
        t4_rows.append(r)
    _write_table("t4_passage_retrieval_provisional", specs["t4"], t4_rows)

    t5_rows: list[list[str]] = []
    for cname, cdef, denom in specs["t5"]["categories"]:
        ql = tax["categories"][cname]
        cnt = len(ql)
        qs = ", ".join(ql[:MAX_REP_QIDS]) + ("..." if cnt > MAX_REP_QIDS else "")
        pct_all = f"{(cnt / TOTAL_HELD_QUERIES) * PERCENT_SCALE:.1f}%"
        sub_s = f"{cnt}/{denom} ({(cnt / denom) * PERCENT_SCALE:.1f}%)"
        t5_rows.append([cname, cdef, str(cnt), pct_all, sub_s, qs])
    _write_table("t5_failure_taxonomy", specs["t5"], t5_rows)

    t6_rows: list[list[str]] = []
    for nm, kv, nv, st in specs["t6"]["audit_specs"]:
        r = [nm, str(kv), str(nv), f"{(kv / nv) * PERCENT_SCALE:.1f}%"]
        r += [_fci(list(wilson_ci(kv, nv))), _fci(list(clopper_pearson_ci(kv, nv))), st]
        t6_rows.append(r)
    _write_table("t6_grounding_and_relation_audit", specs["t6"], t6_rows)
    _write_table("t7_claim_evidence_matrix", specs["t7"], specs["t7"]["rows"])

    summary = {"exp_a_concept_stats": exp_a_stats, "mcnemar_paired_tests": mcnemar}
    summary.update({"exp_b_passage_provisional": p_stats, "failure_taxonomy": tax})
    (TABLES_DIR / "d9_statistical_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    run_d9_statistical_pipeline()

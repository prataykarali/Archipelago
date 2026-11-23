"""Passage metrics and Monte Carlo paired inference for D9 tables."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.stats import binomtest

TOP_K_CUTOFF = 5
BOOTSTRAP_RESAMPLES = 10000
RANDOM_SEED = 20270501
CI_LOW_PCT = 2.5
CI_HIGH_PCT = 97.5
EPSILON = 1e-9
HALF_CORRECTION = 0.5
ROUND_P5_DIGITS = 5


def compute_query_ir_metrics(
    ranked_ids: list[str], qrel_map: dict[str, int], k: int = TOP_K_CUTOFF
) -> dict[str, float]:
    """Compute per-query MRR (full list), nDCG@k, R@k, and P@k matching D5.1 protocol."""
    hits = [1.0 / idx for idx, pid in enumerate(ranked_ids, 1) if qrel_map.get(pid, 0) >= 1]
    mrr = hits[0] if hits else 0.0
    top_k = ranked_ids[:k]
    dcg = sum(
        ((2 ** qrel_map.get(p, 0)) - 1.0) / math.log2(i + 1.0) for i, p in enumerate(top_k, 1)
    )
    ideal = sorted([rel for rel in qrel_map.values() if rel > 0], reverse=True)[:k]
    idcg = sum(((2**rel) - 1.0) / math.log2(i + 1.0) for i, rel in enumerate(ideal, 1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0
    total_rel = sum(1 for rel in qrel_map.values() if rel >= 1)
    hits_k = sum(1 for pid in top_k if qrel_map.get(pid, 0) >= 1)
    rec = (hits_k / total_rel) if total_rel > 0 else 0.0
    return {"mrr": mrr, "ndcg@5": ndcg, "r@5": rec, "p@5": hits_k / k}


def _pct_ci(arr: Any) -> list[float]:
    return [
        round(float(np.percentile(arr, CI_LOW_PCT)), 4),
        round(float(np.percentile(arr, CI_HIGH_PCT)), 4),
    ]


def bootstrap_and_randomization(
    scores_a: list[float],
    scores_b: list[float],
    n_boot: int = BOOTSTRAP_RESAMPLES,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """Compute paired bootstrap 95% CI, paired sign test, and paired randomization p-value."""
    rng = np.random.default_rng(seed)
    arr_a = np.asarray(scores_a, dtype=np.float64)
    arr_b = np.asarray(scores_b, dtype=np.float64)
    diffs = arr_a - arr_b
    n = len(diffs)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_a, boot_b, boot_d = arr_a[idx].mean(1), arr_b[idx].mean(1), diffs[idx].mean(1)
    obs_diff = float(diffs.mean())
    perm = (rng.choice([-1.0, 1.0], size=(n_boot, n)) * diffs).mean(axis=1)
    p_rand = float((np.sum(np.abs(perm) >= (abs(obs_diff) - EPSILON)) + 1) / (n_boot + 1))
    wins, losses = int(np.sum(diffs > EPSILON)), int(np.sum(diffs < -EPSILON))
    p_sign = (
        1.0 if wins + losses == 0 else float(binomtest(wins, wins + losses, HALF_CORRECTION).pvalue)
    )
    res: dict[str, Any] = {"mean_a": round(float(arr_a.mean()), 4), "ci_a_95": _pct_ci(boot_a)}
    res.update(
        {"std_a": round(float(arr_a.std(ddof=1)), 4), "mean_b": round(float(arr_b.mean()), 4)}
    )
    res.update({"std_b": round(float(arr_b.std(ddof=1)), 4), "ci_b_95": _pct_ci(boot_b)})
    res.update({"mean_diff": round(obs_diff, 4), "ci_diff_95": _pct_ci(boot_d)})
    res.update(
        {
            "p_randomization": round(p_rand, ROUND_P5_DIGITS),
            "randomization_method": "Monte Carlo sign-flip, 10000 draws",
            "p_sign_test": round(p_sign, ROUND_P5_DIGITS),
        }
    )
    res.update({"wins_a": wins, "ties": n - wins - losses, "losses_a": losses})
    return res

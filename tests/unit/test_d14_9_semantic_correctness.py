"""Executable mathematical and semantic correctness tests for D14.9 B3 and B4."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) in sys.path:
    sys.path.remove(str(_REPO))
sys.path.insert(0, str(_REPO))
if str(_REPO / "host_inference") not in sys.path:
    sys.path.append(str(_REPO / "host_inference"))
if "archipelago" in sys.modules and not hasattr(sys.modules["archipelago"], "inference"):
    sys.modules.pop("archipelago", None)

from engine.followups import build_follow_up_questions  # noqa: E402
from engine.graph import LibraryGraph  # noqa: E402

from archipelago.inference.math_validator import (  # noqa: E402
    compute_softmax,
    verify_attention_concat_dims,
    verify_cfg_production,
    verify_kl_discrete,
    verify_kl_gaussian_1d,
    verify_softmax,
)


def test_dpo_summary_and_graph_v2_no_explicit_reward_model() -> None:
    graph_path = _REPO / "host_inference" / "fixtures" / "okf_graph_v2_d14.json"
    raw = graph_path.read_text(encoding="utf-8")
    assert "uses a reward model to evaluate generations" not in raw
    data = json.loads(raw)
    nodes = {n["id"]: n for n in data["nodes"]}
    dpo_summary = nodes["direct_preference_optimization"]["summary"].lower()
    assert "policy" in dpo_summary and "reference-policy" in dpo_summary
    assert "avoiding the need to train a separate explicit reward model" in dpo_summary


def test_b4_no_os_paging_to_vllm_prerequisite_and_all_edges_pending_review() -> None:
    graph = LibraryGraph(
        _REPO / "host_inference" / "fixtures" / "okf_graph_v2_d14.json",
        allow_env_override=False,
    )
    assert "vllm" not in graph.unlocks("paging")
    assert "vllm" not in graph.prereqs("paging")
    # PagedAttention USES paging is preserved as an associative interdisciplinary edge.
    assert "paging" in graph.related("paged_attention")

    data = json.loads(
        (_REPO / "host_inference" / "fixtures" / "okf_graph_v2_d14.json").read_text(encoding="utf-8")
    )
    assert all(e.get("review_status") == "PENDING_REVIEW" for e in data["edges"])

    fups = build_follow_up_questions(
        graph,
        {"anchor_concept": "paging", "citations": []},
        "How does paging work?",
        "CONCEPT_LOOKUP",
    )
    assert not any("vllm" in f.lower() for f in fups)


def test_executable_gat_kl_spectral_and_lalr_math_checks() -> None:
    # 1. GAT dimensions + softmax normalization check
    gat_ok = verify_attention_concat_dims(feature_dim=8, attention_vec_dim=16, concat_count=2)
    assert gat_ok.passed is True
    probs = compute_softmax([1.0, 2.0, 0.5])
    assert verify_softmax([1.0, 2.0, 0.5], probs).passed is True

    # 2. KL divergence Gibbs inequality & asymmetry (discrete + 1D Gaussian)
    p = np.array([0.7, 0.2, 0.1], dtype=np.float64)
    q = np.array([0.2, 0.5, 0.3], dtype=np.float64)
    expected_kl_pq = float(np.sum(p * np.log(p / q)))
    expected_kl_qp = float(np.sum(q * np.log(q / p)))
    assert verify_kl_discrete(p.tolist(), q.tolist(), claimed=expected_kl_pq).passed is True
    assert verify_kl_discrete(p.tolist(), p.tolist(), claimed=0.0).passed is True
    assert expected_kl_pq > 0.0 and abs(expected_kl_pq - expected_kl_qp) > 0.01

    g_kl = verify_kl_gaussian_1d(mu1=0.0, sigma1=1.0, mu2=1.0, sigma2=2.0)
    assert g_kl.passed is True

    # 3. Symmetric matrix spectral diagonalization: A = Q diag(lambda) Q^T
    sym = np.array([[4.0, 1.0, 0.5], [1.0, 3.0, -0.5], [0.5, -0.5, 2.0]], dtype=np.float64)
    eigvals, eigvecs = np.linalg.eigh(sym)
    assert np.allclose(eigvecs.T @ eigvecs, np.eye(3), atol=1e-10)
    assert np.linalg.norm(sym - eigvecs @ np.diag(eigvals) @ eigvecs.T) < 1e-10

    # 4. LALR production structural validation
    lalr_ok = verify_cfg_production("E -> E + T")
    assert lalr_ok.passed is True

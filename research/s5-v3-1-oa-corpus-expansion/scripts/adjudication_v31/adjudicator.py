"""Dual-human IAA computation, disagreement worksheet, and adjudication."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .constants import (
    ASSISTANCE_NONE_HUMAN,
    BENCHMARK_VERSION,
    GRADE_SCALE_MAX_DIFF_SQ,
    MIN_RATIONALE_CHARS,
    PROVENANCE_ADJUDICATED_HUMAN,
    PROVENANCE_ZERO_DISAGREEMENTS,
    VALID_GRADES,
)


def compute_inter_annotator_agreement(
    grades_a: list[int],
    grades_c: list[int],
) -> dict[str, Any]:
    """Compute exact agreement, unweighted Cohen's kappa, and QWK."""
    if len(grades_a) != len(grades_c) or not grades_a:
        msg = "grades_a and grades_c must be non-empty lists of equal length."
        raise ValueError(msg)

    n = len(grades_a)
    exact = sum(1 for a, c in zip(grades_a, grades_c, strict=True) if a == c)
    disagree = n - exact
    p_o = exact / n

    counts_a = Counter(grades_a)
    counts_c = Counter(grades_c)
    p_e = sum(
        (counts_a[g] / n) * (counts_c[g] / n) for g in sorted(VALID_GRADES)
    )
    kappa_unweighted = 1.0 if p_e == 1.0 else (p_o - p_e) / (1.0 - p_e)

    obs_w = (
        sum(
            ((a - c) ** 2) / GRADE_SCALE_MAX_DIFF_SQ
            for a, c in zip(grades_a, grades_c, strict=True)
        )
        / n
    )
    exp_w = sum(
        (((ga - gc) ** 2) / GRADE_SCALE_MAX_DIFF_SQ)
        * (counts_a[ga] / n)
        * (counts_c[gc] / n)
        for ga in sorted(VALID_GRADES)
        for gc in sorted(VALID_GRADES)
    )
    qwk = 1.0 if exp_w == 0.0 else 1.0 - (obs_w / exp_w)

    return {
        "total_pairs": n,
        "exact_agreement_count": exact,
        "disagreement_count": disagree,
        "exact_agreement_rate": round(p_o, 6),
        "cohens_kappa_unweighted": round(kappa_unweighted, 6),
        "cohens_kappa_quadratic_weighted": round(qwk, 6),
    }


def generate_disagreement_worksheet(
    sub_a: dict[str, Any],
    sub_c: dict[str, Any],
    pool: dict[str, Any],
) -> dict[str, Any]:
    """Generate a blank human adjudication worksheet for all A/C disagreements."""
    judgments_a = sub_a.get("judgments", {})
    judgments_c = sub_c.get("judgments", {})
    disagreements: list[dict[str, Any]] = []

    for pair in pool.get("pairs", []):
        pid = str(pair["pair_id"])
        ja = judgments_a.get(pid)
        jc = judgments_c.get(pid)
        if ja is None or jc is None:
            msg = f"Missing judgment for {pid} in reviewer submission."
            raise KeyError(msg)
        ga = int(ja["grade"])
        gc = int(jc["grade"])
        if ga != gc:
            disagreements.append(
                {
                    "pair_id": pid,
                    "query_id": str(pair["query_id"]),
                    "passage_id": str(pair["passage_id"]),
                    "passage_sha256": str(pair["passage_sha256"]),
                    "reviewer_a_grade": ga,
                    "reviewer_c_grade": gc,
                    "reviewer_a_quotation": str(
                        ja.get("supporting_quotation", "")
                    ),
                    "reviewer_c_quotation": str(
                        jc.get("supporting_quotation", "")
                    ),
                    "final_grade": None,
                    "adjudication_rationale": "",
                    "supporting_quotation": "",
                }
            )

    prov_class = (
        PROVENANCE_ZERO_DISAGREEMENTS
        if not disagreements
        else PROVENANCE_ADJUDICATED_HUMAN
    )
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "pool_id": str(pool["pool_id"]),
        "total_disagreements": len(disagreements),
        "adjudicator_provenance": {
            "adjudicator_id": "",
            "provenance_class": prov_class,
            "assistance_declaration": ASSISTANCE_NONE_HUMAN,
            "human_attestation_signed": False,
            "attestation_signer": "",
            "signed_timestamp_utc": "",
        },
        "disagreements": disagreements,
    }


def validate_adjudication_worksheet(
    worksheet: dict[str, Any],
    expected_disagreement_pair_ids: frozenset[str],
) -> list[str]:
    """Validate completed human adjudication; reject unsigned or incomplete."""
    errors: list[str] = []
    if worksheet.get("benchmark_version") != BENCHMARK_VERSION:
        errors.append("INVALID_BENCHMARK_VERSION")

    prov = worksheet.get("adjudicator_provenance", {})
    if prov.get("assistance_declaration") != ASSISTANCE_NONE_HUMAN:
        errors.append("AI_ASSISTED_ADJUDICATION_FORBIDDEN")
    if prov.get("human_attestation_signed") is not True:
        errors.append("UNSIGNED_ADJUDICATION")
    for fname in (
        "adjudicator_id",
        "attestation_signer",
        "signed_timestamp_utc",
    ):
        if not str(prov.get(fname, "")).strip():
            errors.append(f"MISSING_ADJUDICATOR_{fname.upper()}")

    expected_class = (
        PROVENANCE_ZERO_DISAGREEMENTS
        if not expected_disagreement_pair_ids
        else PROVENANCE_ADJUDICATED_HUMAN
    )
    if prov.get("provenance_class") != expected_class:
        errors.append("INVALID_ADJUDICATOR_PROVENANCE_CLASS")

    rows = worksheet.get("disagreements", [])
    seen_ids: set[str] = set()
    for row in rows:
        pid = str(row.get("pair_id", ""))
        seen_ids.add(pid)
        if row.get("final_grade") not in VALID_GRADES:
            errors.append(f"INVALID_ADJUDICATED_GRADE:{pid}")
        if len(str(row.get("adjudication_rationale", "")).strip()) < MIN_RATIONALE_CHARS:
            errors.append(f"MISSING_ADJUDICATION_RATIONALE:{pid}")

    if seen_ids != expected_disagreement_pair_ids:
        errors.append("DISAGREEMENT_SET_MISMATCH")
    return errors

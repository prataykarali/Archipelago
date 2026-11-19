"""S5-D0 — Read-Only Post-Adjudication Retrieval Analysis Pipeline.

Accepts ONLY finalized, human-adjudicated gold labels matching the frozen 254-pair
S5-B2.1 pool (`s5b2_1_proposed_pooled_v2.1_pending_approval`) and evaluates the
six frozen retrieval systems from `s5b2_1_frozen_ranked_results.json`.

Strict Scientific Guardrails:
- Read-only with respect to all frozen datasets, corpora, rankings, and workbooks.
- Does NOT generate, infer, or assume gold labels.
- Does NOT resolve the 51 S5-C2 disagreements.
- Refuses to compute metrics unless:
  1. `status == "ADJUDICATED_HUMAN_GOLD_FINAL"`
  2. `reviewer_b_independence_confirmed is True`
  3. `all_disagreements_adjudicated is True`
  4. All 254 `(pair_id, query_id, passage_id)` entries are present with integer grades in {0, 1, 2}
  5. Unjudged passages in Top-K are explicitly counted and NEVER silently treated as irrelevant.
- Reports answerable queries and verified negative-control queries separately.
- Never emits superiority or statistical significance claims (N=10 pilot).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FROZEN_RANKINGS = (
    ROOT / "research" / "s5-b2-benchmark-correction" / "reports" / "s5b2_1_frozen_ranked_results.json"
)
DEFAULT_FROZEN_POOL = (
    ROOT / "research" / "s5-b2-benchmark-correction" / "proposed_package_v2_1" / "retrieval_query_pool_blinded.json"
)

VALID_GRADES = {0, 1, 2}
VALID_ADJUDICATION_SOURCES = {
    "DUAL_HUMAN_AGREEMENT",
    "THIRD_PARTY_ADJUDICATION",
    "INVESTIGATOR_ADJUDICATION",
}
VALID_NEG_CONTROL_CLASSES = {
    "NO_ANSWER_IN_SELECTED_PASSAGES",
    "NO_ANSWER_IN_FROZEN_CORPUS",
    "AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION",
    "QUESTION_REQUIRING_REVISION",
}
PROVISIONAL_NEG_CONTROL_IDS = ("Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11")


class GoldLabelValidationError(ValueError):
    """Raised when a supplied gold-label file fails S5-D0 integrity gates."""


def expected_gold_label_schema() -> dict[str, Any]:
    """Return the required JSON schema template for adjudicated gold labels."""
    return {
        "schema_version": "s5d0_adjudicated_gold_v1",
        "status": "ADJUDICATED_HUMAN_GOLD_FINAL",
        "pool_version": "s5b2_1_proposed_pooled_v2.1_pending_approval",
        "pool_sha256": "2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037",
        "reviewer_b_independence_confirmed": True,
        "all_disagreements_adjudicated": True,
        "negative_control_verifications": {
            qid: {
                "human_answerability_classification": "NO_ANSWER_IN_FROZEN_CORPUS",
                "verifier_id": "<HUMAN_VERIFIER_ID>",
            }
            for qid in PROVISIONAL_NEG_CONTROL_IDS
        },
        "judgments": [
            {
                "pair_id": "S5B21-PAIR-001",
                "query_id": "Q-S5B2-01",
                "passage_id": "<PASSAGE_ID>",
                "final_grade": 0,
                "adjudication_source": "DUAL_HUMAN_AGREEMENT",
            }
        ],
    }


def load_frozen_pool_index(pool_path: Path) -> tuple[dict[str, tuple[str, str]], str, str]:
    """Load frozen pool mapping pair_id -> (query_id, passage_id), pool_version, and sha256."""
    raw_bytes = pool_path.read_bytes()
    pool_sha = hashlib.sha256(raw_bytes).hexdigest()
    pool = json.loads(raw_bytes.decode("utf-8"))
    index: dict[str, tuple[str, str]] = {}
    for q in pool["queries"]:
        qid = q["query_id"]
        for cand in q["candidates"]:
            index[cand["pair_id"]] = (qid, cand["candidate_passage_id"])
    return index, pool["version"], pool_sha


def validate_adjudicated_gold_labels(
    gold_payload: dict[str, Any],
    pool_index: dict[str, tuple[str, str]],
    expected_pool_version: str,
    expected_pool_sha256: str,
) -> dict[tuple[str, str], int]:
    """Validate adjudicated gold-label payload and return (query_id, passage_id) -> grade."""
    errors: list[str] = []

    if gold_payload.get("status") != "ADJUDICATED_HUMAN_GOLD_FINAL":
        errors.append(
            f"status must be 'ADJUDICATED_HUMAN_GOLD_FINAL', got {gold_payload.get('status')!r}"
        )
    if gold_payload.get("pool_version") != expected_pool_version:
        errors.append(
            f"pool_version mismatch: expected {expected_pool_version!r}, got {gold_payload.get('pool_version')!r}"
        )
    if gold_payload.get("pool_sha256") != expected_pool_sha256:
        errors.append(
            f"pool_sha256 mismatch: expected {expected_pool_sha256!r}, got {gold_payload.get('pool_sha256')!r}"
        )
    if gold_payload.get("reviewer_b_independence_confirmed") is not True:
        errors.append("reviewer_b_independence_confirmed must be explicitly True")
    if gold_payload.get("all_disagreements_adjudicated") is not True:
        errors.append("all_disagreements_adjudicated must be explicitly True")

    neg_ver = gold_payload.get("negative_control_verifications")
    if not isinstance(neg_ver, dict):
        errors.append("negative_control_verifications must be a dict covering provisional negative controls")
    else:
        for qid in PROVISIONAL_NEG_CONTROL_IDS:
            rec = neg_ver.get(qid)
            if not isinstance(rec, dict):
                errors.append(f"Missing negative-control verification record for {qid}")
                continue
            cls = rec.get("human_answerability_classification")
            vid = rec.get("verifier_id")
            if cls not in VALID_NEG_CONTROL_CLASSES:
                errors.append(f"{qid}: invalid human_answerability_classification {cls!r}")
            if not isinstance(vid, str) or not vid.strip():
                errors.append(f"{qid}: verifier_id must be a non-empty string")

    judgments = gold_payload.get("judgments")
    if not isinstance(judgments, list):
        errors.append("judgments must be a list")
        raise GoldLabelValidationError("; ".join(errors))

    seen_pairs: set[str] = set()
    qrels: dict[tuple[str, str], int] = {}

    for idx, row in enumerate(judgments):
        if not isinstance(row, dict):
            errors.append(f"judgments[{idx}] is not an object")
            continue
        pid = row.get("pair_id")
        qid = row.get("query_id")
        passage_id = row.get("passage_id")
        grade = row.get("final_grade")
        src = row.get("adjudication_source")

        if pid not in pool_index:
            errors.append(f"Unknown pair_id {pid!r}")
            continue
        if pid in seen_pairs:
            errors.append(f"Duplicate pair_id {pid!r}")
            continue
        seen_pairs.add(pid)

        exp_qid, exp_passage = pool_index[pid]
        if (qid, passage_id) != (exp_qid, exp_passage):
            errors.append(
                f"{pid}: (query_id, passage_id) mismatch: expected {(exp_qid, exp_passage)}, got {(qid, passage_id)}"
            )
        if type(grade) is not int or grade not in VALID_GRADES:
            errors.append(f"{pid}: final_grade must be int in {{0, 1, 2}}, got {grade!r}")
            continue
        if src not in VALID_ADJUDICATION_SOURCES:
            errors.append(f"{pid}: invalid adjudication_source {src!r}")
            continue

        qrels[(exp_qid, exp_passage)] = grade

    missing_pairs = sorted(set(pool_index.keys()) - seen_pairs)
    if missing_pairs:
        errors.append(f"Missing {len(missing_pairs)} required pair_id(s), e.g. {missing_pairs[:5]}")

    if errors:
        raise GoldLabelValidationError("Gold label validation failed:\n- " + "\n- ".join(errors))

    return qrels


def _dcg_at_k(grades: list[int], k: int) -> float:
    total = 0.0
    for rank, g in enumerate(grades[:k], start=1):
        gain = (2**g) - 1
        total += gain / math.log2(rank + 1)
    return total


def evaluate_query_ranking(
    ranked_passage_ids: list[str],
    query_qrels: dict[str, int],
    *,
    rel_threshold: int = 2,
) -> dict[str, Any]:
    """Compute standard IR metrics for one query without treating unjudged passages as irrelevant."""
    top5 = ranked_passage_ids[:5]
    top10 = ranked_passage_ids[:10]

    unjudged_at_5 = sum(1 for p in top5 if p not in query_qrels)
    unjudged_at_10 = sum(1 for p in top10 if p not in query_qrels)

    relevant_in_pool = {p for p, g in query_qrels.items() if g >= rel_threshold}
    n_rel = len(relevant_in_pool)

    # Judged-only grades for nDCG (unjudged passages cannot be silently assigned grade 0)
    if unjudged_at_10 > 0:
        raise GoldLabelValidationError(
            f"Encountered {unjudged_at_10} unjudged passage(s) in Top-10; "
            "unjudged passages are never silently treated as irrelevant."
        )

    grades_10 = [query_qrels[p] for p in top10]
    ideal_grades = sorted(query_qrels.values(), reverse=True)

    idcg_5 = _dcg_at_k(ideal_grades, 5)
    idcg_10 = _dcg_at_k(ideal_grades, 10)
    ndcg_5 = (_dcg_at_k(grades_10, 5) / idcg_5) if idcg_5 > 0 else None
    ndcg_10 = (_dcg_at_k(grades_10, 10) / idcg_10) if idcg_10 > 0 else None

    hits_5 = sum(1 for p in top5 if p in relevant_in_pool)
    hits_10 = sum(1 for p in top10 if p in relevant_in_pool)

    rr_10 = 0.0
    for rank, p in enumerate(top10, start=1):
        if p in relevant_in_pool:
            rr_10 = 1.0 / rank
            break

    return {
        "n_relevant_in_pool": n_rel,
        "returned_count": len(top10),
        "unjudged_at_5": unjudged_at_5,
        "unjudged_at_10": unjudged_at_10,
        "recall_at_5": round(hits_5 / n_rel, 4) if n_rel > 0 else None,
        "recall_at_10": round(hits_10 / n_rel, 4) if n_rel > 0 else None,
        "precision_at_5": round(hits_5 / 5.0, 4),
        "precision_at_10": round(hits_10 / 10.0, 4),
        "mrr_at_10": round(rr_10, 4) if n_rel > 0 else None,
        "ndcg_at_5": round(ndcg_5, 4) if ndcg_5 is not None else None,
        "ndcg_at_10": round(ndcg_10, 4) if ndcg_10 is not None else None,
        "max_grade_in_top10": max(grades_10) if grades_10 else None,
    }


def run_readonly_evaluation(
    frozen_rankings_path: Path,
    frozen_pool_path: Path,
    gold_labels_path: Path,
) -> dict[str, Any]:
    """Validate gold labels and evaluate all six frozen systems in read-only mode."""
    pool_index, expected_pool_version, expected_pool_sha = load_frozen_pool_index(frozen_pool_path)
    gold_payload = json.loads(gold_labels_path.read_text(encoding="utf-8"))
    qrels = validate_adjudicated_gold_labels(
        gold_payload, pool_index, expected_pool_version, expected_pool_sha
    )

    frozen = json.loads(frozen_rankings_path.read_text(encoding="utf-8"))

    # Group qrels by query_id
    qrels_by_query: dict[str, dict[str, int]] = {}
    for (qid, pid), grade in qrels.items():
        qrels_by_query.setdefault(qid, {})[pid] = grade

    neg_ver = gold_payload["negative_control_verifications"]
    verified_neg_qids = {
        qid
        for qid, rec in neg_ver.items()
        if rec["human_answerability_classification"] == "NO_ANSWER_IN_FROZEN_CORPUS"
    }

    results_by_system: dict[str, Any] = {}
    for sys_name, sys_data in frozen["systems"].items():
        per_query_strict: dict[str, Any] = {}
        per_query_lenient: dict[str, Any] = {}
        neg_control_diagnostics: dict[str, Any] = {}

        for q_entry in sys_data["queries"]:
            qid = q_entry["query_id"]
            ranked_pids = [item["passage_id"] for item in q_entry["ranked_top10"]]
            q_qrels = qrels_by_query[qid]
            is_fb = bool(q_entry.get("meta", {}).get("is_fallback", False))

            m_strict = evaluate_query_ranking(ranked_pids, q_qrels, rel_threshold=2)
            m_lenient = evaluate_query_ranking(ranked_pids, q_qrels, rel_threshold=1)
            m_strict["is_fallback"] = is_fb
            m_lenient["is_fallback"] = is_fb

            if qid in verified_neg_qids:
                neg_control_diagnostics[qid] = {
                    "returned_count": len(ranked_pids),
                    "is_fallback": is_fb,
                    "max_grade_in_top10": m_strict["max_grade_in_top10"],
                    "any_grade_ge_1_in_top10": any(q_qrels[p] >= 1 for p in ranked_pids),
                }
            else:
                per_query_strict[qid] = m_strict
                per_query_lenient[qid] = m_lenient

        def _mean_metric(records: dict[str, Any], key: str) -> float | None:
            vals = [r[key] for r in records.values() if r[key] is not None]
            return round(sum(vals) / len(vals), 4) if vals else None

        results_by_system[sys_name] = {
            "answerable_queries_count": len(per_query_strict),
            "verified_negative_controls_count": len(neg_control_diagnostics),
            "macro_average_strict_grade_ge_2": {
                "recall_at_5": _mean_metric(per_query_strict, "recall_at_5"),
                "recall_at_10": _mean_metric(per_query_strict, "recall_at_10"),
                "precision_at_5": _mean_metric(per_query_strict, "precision_at_5"),
                "precision_at_10": _mean_metric(per_query_strict, "precision_at_10"),
                "mrr_at_10": _mean_metric(per_query_strict, "mrr_at_10"),
                "ndcg_at_5": _mean_metric(per_query_strict, "ndcg_at_5"),
                "ndcg_at_10": _mean_metric(per_query_strict, "ndcg_at_10"),
            },
            "macro_average_lenient_grade_ge_1": {
                "recall_at_5": _mean_metric(per_query_lenient, "recall_at_5"),
                "recall_at_10": _mean_metric(per_query_lenient, "recall_at_10"),
                "precision_at_5": _mean_metric(per_query_lenient, "precision_at_5"),
                "precision_at_10": _mean_metric(per_query_lenient, "precision_at_10"),
                "mrr_at_10": _mean_metric(per_query_lenient, "mrr_at_10"),
                "ndcg_at_5": _mean_metric(per_query_lenient, "ndcg_at_5"),
                "ndcg_at_10": _mean_metric(per_query_lenient, "ndcg_at_10"),
            },
            "per_query_strict": per_query_strict,
            "per_query_lenient": per_query_lenient,
            "negative_control_diagnostics": neg_control_diagnostics,
        }

    return {
        "pipeline_name": "S5-D0 Read-Only Post-Adjudication Retrieval Evaluation",
        "pool_version": expected_pool_version,
        "pool_sha256": expected_pool_sha,
        "gold_labels_sha256": hashlib.sha256(gold_labels_path.read_bytes()).hexdigest(),
        "statistical_scope_disclaimer": (
            "Descriptive pilot metrics only (10 active queries, 0 validated cross-document queries). "
            "No statistical significance, superiority, or generalizable performance claims are authorized."
        ),
        "systems": results_by_system,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only evaluation pipeline for finalized, adjudicated human gold labels."
    )
    parser.add_argument(
        "--gold-labels",
        type=Path,
        help="Path to finalized adjudicated human gold-label JSON file.",
    )
    parser.add_argument(
        "--frozen-rankings",
        type=Path,
        default=DEFAULT_FROZEN_RANKINGS,
        help="Path to frozen six-system ranked results JSON.",
    )
    parser.add_argument(
        "--frozen-pool",
        type=Path,
        default=DEFAULT_FROZEN_POOL,
        help="Path to frozen 254-pair blinded pool JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output JSON path for computed metrics.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate gold-label file integrity without computing retrieval metrics.",
    )
    parser.add_argument(
        "--print-schema",
        action="store_true",
        help="Print the required adjudicated gold-label JSON schema and exit.",
    )
    args = parser.parse_args()

    if args.print_schema:
        print(json.dumps(expected_gold_label_schema(), indent=2))
        return

    if not args.gold_labels:
        raise SystemExit(
            "Error: --gold-labels is required. This read-only pipeline does not generate or assume gold labels."
        )

    if args.validate_only:
        pool_index, exp_ver, exp_sha = load_frozen_pool_index(args.frozen_pool)
        gold_payload = json.loads(args.gold_labels.read_text(encoding="utf-8"))
        validate_adjudicated_gold_labels(gold_payload, pool_index, exp_ver, exp_sha)
        print("OK: Adjudicated gold-label file passed all S5-D0 integrity checks.")
        return

    report = run_readonly_evaluation(args.frozen_rankings, args.frozen_pool, args.gold_labels)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote read-only evaluation report to {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()

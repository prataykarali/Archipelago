"""Validate completed human worksheets before computing agreement and retrieval metrics."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from build_blinded_pool import parse_trec_run

EVAL_DIR = Path(__file__).resolve().parent
EXPECTED_ITEMS = 731
VALID_GRADES = {"0", "1", "2"}
TOP_K = 5
SYSTEMS = (
    "bm25",
    "snowflake_arctic_neural",
    "feature_hashed_vector",
    "archipelago_graph_assisted",
)


def _read_rows(path: Path, grade_field: str) -> dict[str, dict[str, str]]:
    """Read a complete worksheet with unique item IDs and valid human metadata."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_ITEMS:
        raise ValueError(f"{path.name}: expected {EXPECTED_ITEMS} rows")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        item_id = row["item_id"]
        if item_id in result:
            raise ValueError(f"{path.name}: duplicate item")
        if row.get(grade_field, "").strip() not in VALID_GRADES:
            raise ValueError(f"{path.name}: missing or invalid grade for {item_id}")
        if grade_field == "relevance_grade":
            if not row.get("reviewer_id", "").strip() or not row.get("review_date", "").strip():
                raise ValueError(f"{path.name}: missing human provenance for {item_id}")
        else:
            if (
                not row.get("adjudicator_id", "").strip()
                or not row.get("adjudication_date", "").strip()
            ):
                raise ValueError(f"{path.name}: missing adjudicator provenance for {item_id}")
        result[item_id] = row
    return result


def _weighted_kappa(a: list[int], b: list[int]) -> float:
    """Compute quadratic-weighted Cohen kappa for ordinal grades."""
    n = len(a)
    obs = sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) / (n * 4)
    hist_a = [a.count(i) / n for i in range(3)]
    hist_b = [b.count(i) / n for i in range(3)]
    expected = sum(hist_a[i] * hist_b[j] * (i - j) ** 2 / 4 for i in range(3) for j in range(3))
    return 1.0 if expected == 0 and obs == 0 else 1.0 - obs / expected


def _ordinal_alpha(a: list[int], b: list[int]) -> float:
    """Compute two-rater Krippendorff alpha using squared ordinal distance."""
    values = a + b
    n = len(values)
    observed = sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) / len(a)
    counts = [values.count(i) for i in range(3)]
    expected = sum(counts[i] * counts[j] * (i - j) ** 2 for i in range(3) for j in range(3)) / (
        n * (n - 1)
    )
    return 1.0 if expected == 0 and observed == 0 else 1.0 - observed / expected


def _metrics(ranked: list[str], qrels: dict[str, int]) -> dict[str, float]:
    """Compute passage metrics from adjudicated graded qrels."""
    top = ranked[:TOP_K]
    positives = sum(grade > 0 for grade in qrels.values())
    hits = [i for i, pid in enumerate(ranked, 1) if qrels.get(pid, 0) > 0]
    mrr = 1 / hits[0] if hits else 0.0
    dcg = sum((2 ** qrels.get(pid, 0) - 1) / math.log2(i + 1) for i, pid in enumerate(top, 1))
    ideal = sorted(qrels.values(), reverse=True)[:TOP_K]
    idcg = sum((2**grade - 1) / math.log2(i + 1) for i, grade in enumerate(ideal, 1))
    hit_count = sum(qrels.get(pid, 0) > 0 for pid in top)
    return {
        "mrr": mrr,
        "ndcg@5": dcg / idcg if idcg else 0.0,
        "recall@5": hit_count / positives if positives else 0.0,
        "precision@5": hit_count / TOP_K,
    }


def analyze(packet_dir: Path, output_path: Path, eval_dir: Path = EVAL_DIR) -> dict[str, Any]:
    """Require authentic completed sheets, compute agreement, then human-qrel metrics."""
    packet_dir = packet_dir.resolve()
    sealed = json.loads((packet_dir / "private" / "sealed_key.json").read_text())
    mapping = sealed["items"]
    if len(mapping) != EXPECTED_ITEMS:
        raise ValueError("Sealed pool size mismatch")
    a = _read_rows(packet_dir / "reviewer_A_packet.csv", "relevance_grade")
    b = _read_rows(packet_dir / "reviewer_B_packet.csv", "relevance_grade")
    if set(a) != set(mapping) or set(b) != set(mapping):
        raise ValueError("Reviewer packet IDs do not match sealed pool")
    if {row["reviewer_id"] for row in a.values()} & {row["reviewer_id"] for row in b.values()}:
        raise ValueError("Reviewers must have distinct identities")
    ids = sorted(mapping)
    for item_id in ids:
        expected = mapping[item_id]
        for sheet in (a, b):
            row = sheet[item_id]
            if (
                row["query_id"] != expected["query_id"]
                or row["blinded_candidate_id"] != expected["blinded_candidate_id"]
            ):
                raise ValueError("Packet identity mismatch")
    grades_a = [int(a[i]["relevance_grade"]) for i in ids]
    grades_b = [int(b[i]["relevance_grade"]) for i in ids]
    agreement = {
        "exact_agreement": sum(x == y for x, y in zip(grades_a, grades_b, strict=True))
        / EXPECTED_ITEMS,
        "quadratic_weighted_cohen_kappa": _weighted_kappa(grades_a, grades_b),
        "squared_distance_krippendorff_alpha": _ordinal_alpha(grades_a, grades_b),
    }
    adj = _read_rows(packet_dir / "adjudication_packet.csv", "adjudicated_relevance_grade")
    if set(adj) != set(mapping):
        raise ValueError("Adjudication packet IDs do not match sealed pool")
    qrels: dict[str, dict[str, int]] = {}
    for item_id in ids:
        entry = mapping[item_id]
        row = adj[item_id]
        if (
            row["query_id"] != entry["query_id"]
            or row["blinded_candidate_id"] != entry["blinded_candidate_id"]
        ):
            raise ValueError("Adjudication identity mismatch")
        if (
            row.get("reviewer_A_grade") != a[item_id]["relevance_grade"]
            or row.get("reviewer_B_grade") != b[item_id]["relevance_grade"]
        ):
            raise ValueError("Adjudication sheet has stale reviewer grades")
        if (
            grades_a[ids.index(item_id)] != grades_b[ids.index(item_id)]
            and not row.get("adjudication_rationale", "").strip()
        ):
            raise ValueError("Disagreement requires adjudication rationale")
        qrels.setdefault(entry["query_id"], {})[entry["passage_id"]] = int(
            row["adjudicated_relevance_grade"]
        )
    queries = json.loads((eval_dir / "queries_heldout_50.json").read_text())
    supported = [q["query_id"] for q in queries if q["is_supported"]]
    results: dict[str, Any] = {}
    for system in SYSTEMS:
        run = parse_trec_run(eval_dir / "ranked_runs" / f"{system}.run", depth=1000)
        by_query = [
            _metrics([pid for pid, _, _ in run.get(qid, [])], qrels.get(qid, {}))
            for qid in supported
        ]
        results[system] = {
            key: sum(row[key] for row in by_query) / len(by_query) for key in by_query[0]
        }
    report = {
        "status": "HUMAN_WORKSHEETS_COMPLETE",
        "items": EXPECTED_ITEMS,
        "supported_query_denominator": len(supported),
        "agreement_before_adjudication": agreement,
        "human_qrel_metrics": results,
    }
    if EVAL_DIR.parents[1] in output_path.resolve().parents:
        raise ValueError("Human results output must be outside the Git repository")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    """Run post-annotation analysis on completed local worksheets."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.packets, args.output)))


if __name__ == "__main__":
    main()

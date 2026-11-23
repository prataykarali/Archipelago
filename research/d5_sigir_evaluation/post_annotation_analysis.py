"""Validate completed human worksheets before computing agreement and retrieval metrics."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from build_blinded_pool import parse_trec_run

EVAL_DIR = Path(__file__).resolve().parent
EXPECTED_ITEMS = 731
VALID_GRADES = {"0", "1", "2"}
VALID_SUPPORT = {"FULLY_SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "IRRELEVANT"}
TOP_K = 5
SYSTEMS = (
    "bm25",
    "snowflake_arctic_neural",
    "feature_hashed_vector",
    "archipelago_graph_assisted",
)


def _read_rows(path: Path, grade_field: str | None = None) -> dict[str, dict[str, str]]:
    """Read a worksheet with unique item IDs, validating any submitted grades."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        item_id = row["item_id"]
        if item_id in result:
            raise ValueError(f"{path.name}: duplicate item")
        if grade_field:
            if row.get(grade_field, "").strip() not in VALID_GRADES:
                raise ValueError(f"{path.name}: missing or invalid grade for {item_id}")
            if grade_field == "relevance_grade":
                if not row.get("reviewer_id", "").strip() or not row.get("review_date", "").strip():
                    raise ValueError(f"{path.name}: missing human provenance for {item_id}")
                if row.get("confidence") not in {"HIGH", "MEDIUM", "LOW"}:
                    raise ValueError(f"{path.name}: missing confidence for {item_id}")
                if row.get("claim_supported") not in VALID_SUPPORT:
                    raise ValueError(f"{path.name}: missing claim support for {item_id}")
                if row["confidence"] == "LOW" and not row.get("notes", "").strip():
                    raise ValueError(f"{path.name}: LOW confidence requires notes for {item_id}")
                date.fromisoformat(row["review_date"])
        result[item_id] = row
    return result


def _weighted_kappa(a: list[int], b: list[int]) -> float:
    """Compute quadratic-weighted Cohen kappa for ordinal grades."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("Agreement requires paired ratings")
    obs = sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) / (n * 4)
    hist_a = [a.count(i) / n for i in range(3)]
    hist_b = [b.count(i) / n for i in range(3)]
    expected = sum(hist_a[i] * hist_b[j] * (i - j) ** 2 / 4 for i in range(3) for j in range(3))
    return 1.0 if expected == 0 and obs == 0 else 1.0 - obs / expected


def _ordinal_alpha(a: list[int], b: list[int]) -> float:
    """Compute Krippendorff ordinal alpha with pooled-frequency rank distance."""
    if not a or len(a) != len(b):
        raise ValueError("Agreement requires paired ratings")
    values = a + b
    n = len(values)
    counts = [values.count(i) for i in range(3)]

    def distance(x: int, y: int) -> float:
        lo, hi = sorted((x, y))
        return (
            (counts[lo] / 2 + sum(counts[lo + 1 : hi]) + counts[hi] / 2) ** 2 if lo != hi else 0.0
        )

    observed = sum(distance(x, y) for x, y in zip(a, b, strict=True)) / len(a)
    expected = sum(counts[i] * counts[j] * distance(i, j) for i in range(3) for j in range(3)) / (
        n * (n - 1)
    )
    return 1.0 if expected == 0 and observed == 0 else 1.0 - observed / expected


def _nominal_kappa(a: list[Any], b: list[Any]) -> float:
    """Compute unweighted Cohen kappa for paired categorical ratings."""
    if not a or len(a) != len(b):
        raise ValueError("Agreement requires paired ratings")
    categories = set(a) | set(b)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / len(a)
    expected = sum(a.count(c) * b.count(c) for c in categories) / len(a) ** 2
    return 1.0 if expected == 1 and observed == 1 else (observed - expected) / (1 - expected)


def _metrics(ranked: list[str], qrels: dict[str, int]) -> dict[str, float]:
    """Compute passage metrics from adjudicated graded qrels."""
    top = ranked[:TOP_K]
    positives = sum(grade > 0 for grade in qrels.values())
    hits = [i for i, pid in enumerate(top, 1) if qrels.get(pid, 0) > 0]
    mrr = 1 / hits[0] if hits else 0.0
    dcg = sum((2 ** qrels.get(pid, 0) - 1) / math.log2(i + 1) for i, pid in enumerate(top, 1))
    ideal = sorted(qrels.values(), reverse=True)[:TOP_K]
    idcg = sum((2**grade - 1) / math.log2(i + 1) for i, grade in enumerate(ideal, 1))
    hit_count = sum(qrels.get(pid, 0) > 0 for pid in top)
    return {
        "mrr@5": mrr,
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
    manifest = json.loads((packet_dir / "assignment_manifest.json").read_text())
    assignment = manifest["assignment"]
    if manifest["design"] not in {"full", "partial"} or set(assignment) != set(mapping):
        raise ValueError("Missing or invalid predeclared assignment")
    if set(assignment.values()) - {"A", "B", "AB"}:
        raise ValueError("Invalid reviewer assignment")
    overlap = {item for item, reviewers in assignment.items() if reviewers == "AB"}
    if manifest["design"] == "partial" and len(overlap) < 145:
        raise ValueError("Insufficient predeclared overlap")
    if manifest["design"] == "full" and len(overlap) != EXPECTED_ITEMS:
        raise ValueError("Full design requires full overlap")
    a = _read_rows(packet_dir / "reviewer_A_packet.csv", "relevance_grade")
    b = _read_rows(packet_dir / "reviewer_B_packet.csv", "relevance_grade")
    if set(a) != {i for i, owners in assignment.items() if "A" in owners} or set(b) != {
        i for i, owners in assignment.items() if "B" in owners
    }:
        raise ValueError("Reviewer packet IDs do not match predeclared assignment")
    if {row["reviewer_id"] for row in a.values()} & {row["reviewer_id"] for row in b.values()}:
        raise ValueError("Reviewers must have distinct identities")
    if (
        len({row["reviewer_id"] for row in a.values()}) != 1
        or len({row["reviewer_id"] for row in b.values()}) != 1
    ):
        raise ValueError("Each reviewer must use one consistent identity")
    ids = sorted(mapping)
    for item_id in ids:
        expected = mapping[item_id]
        for sheet in (a, b):
            if item_id not in sheet:
                continue
            row = sheet[item_id]
            if (
                row["query_id"] != expected["query_id"]
                or row["blinded_candidate_id"] != expected["blinded_candidate_id"]
            ):
                raise ValueError("Packet identity mismatch")
    paired_ids = sorted(overlap)
    grades_a = [int(a[i]["relevance_grade"]) for i in paired_ids]
    grades_b = [int(b[i]["relevance_grade"]) for i in paired_ids]
    supports_a = [a[i]["claim_supported"] for i in paired_ids]
    supports_b = [b[i]["claim_supported"] for i in paired_ids]
    agreement = {
        "exact_agreement": sum(x == y for x, y in zip(grades_a, grades_b, strict=True))
        / len(paired_ids),
        "unweighted_cohen_kappa": _nominal_kappa(grades_a, grades_b),
        "quadratic_weighted_cohen_kappa": _weighted_kappa(grades_a, grades_b),
        "krippendorff_ordinal_alpha": _ordinal_alpha(grades_a, grades_b),
        "binary_grade_ge_1_kappa": _nominal_kappa(
            [x >= 1 for x in grades_a], [x >= 1 for x in grades_b]
        ),
        "binary_grade_eq_2_kappa": _nominal_kappa(
            [x == 2 for x in grades_a], [x == 2 for x in grades_b]
        ),
        "claim_support_kappa": _nominal_kappa(supports_a, supports_b),
        "claim_support_confusion": {
            f"{x}|{y}": sum(
                a1 == x and b1 == y for a1, b1 in zip(supports_a, supports_b, strict=True)
            )
            for x in sorted(set(supports_a))
            for y in sorted(set(supports_b))
        },
    }
    adj = _read_rows(packet_dir / "adjudication_packet.csv")
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
        grade_a = a[item_id]["relevance_grade"] if item_id in a else ""
        grade_b = b[item_id]["relevance_grade"] if item_id in b else ""
        support_a = a[item_id]["claim_supported"] if item_id in a else ""
        support_b = b[item_id]["claim_supported"] if item_id in b else ""
        if row.get("reviewer_A_grade", "") not in {"", grade_a} or row.get(
            "reviewer_B_grade", ""
        ) not in {"", grade_b}:
            raise ValueError("Adjudication sheet has stale reviewer grades")
        if row.get("reviewer_A_claim_supported", "") not in {"", support_a} or row.get(
            "reviewer_B_claim_supported", ""
        ) not in {"", support_b}:
            raise ValueError("Adjudication sheet has stale claim support")
        disagreement = bool(grade_a and grade_b and (grade_a != grade_b or support_a != support_b))
        if disagreement:
            final_grade = row.get("adjudicated_relevance_grade", "").strip()
            final_support = row.get("adjudicated_claim_supported", "").strip()
            if (
                final_grade not in VALID_GRADES
                or final_support not in VALID_SUPPORT
                or not row.get("adjudicator_id", "").strip()
                or not row.get("adjudication_date", "").strip()
                or not row.get("adjudication_rationale", "").strip()
            ):
                raise ValueError("Disagreement requires completed human adjudication")
            date.fromisoformat(row["adjudication_date"])
        else:
            final_grade = grade_a or grade_b
            if row.get("adjudicated_relevance_grade", "").strip() not in {"", final_grade}:
                raise ValueError("Uncontested grade cannot be overridden")
            if row.get("adjudicated_claim_supported", "").strip() not in {
                "",
                support_a or support_b,
            }:
                raise ValueError("Uncontested claim support cannot be overridden")
        qrels.setdefault(entry["query_id"], {})[entry["passage_id"]] = int(final_grade)
    if (
        agreement["quadratic_weighted_cohen_kappa"] < 0.60
        or agreement["krippendorff_ordinal_alpha"] < 0.67
    ):
        raise ValueError("Agreement below predeclared threshold; human metrics withheld")
    receipt = json.loads((packet_dir / "human_submission_receipt.json").read_text())
    if (
        receipt.get("attestation")
        != "I verified these entries were made by the named human reviewers and adjudicator"
    ):
        raise ValueError("Human provenance attestation is missing")
    if receipt.get("reviewer_A_id") != next(
        iter({row["reviewer_id"] for row in a.values()})
    ) or receipt.get("reviewer_B_id") != next(iter({row["reviewer_id"] for row in b.values()})):
        raise ValueError("Human receipt reviewer identities do not match worksheets")
    adjudicator_ids = {
        row["adjudicator_id"] for row in adj.values() if row.get("adjudicator_id", "").strip()
    }
    if not receipt.get("adjudicator_id") or adjudicator_ids - {receipt["adjudicator_id"]}:
        raise ValueError("Human receipt adjudicator identity does not match worksheet")
    if receipt["adjudicator_id"] in {receipt["reviewer_A_id"], receipt["reviewer_B_id"]}:
        raise ValueError("Adjudicator must be distinct from reviewers")
    if not receipt.get("coordinator_name") or not receipt.get("verification_date"):
        raise ValueError("Human receipt lacks coordinator sign-off")
    date.fromisoformat(receipt["verification_date"])
    if any(
        token in str(receipt).lower()
        for token in ("coding_agent", "llm", "chatgpt", "placeholder", "tbd")
    ):
        raise ValueError("Human receipt contains invalid identity or placeholder")
    for name in (
        "assignment_manifest.json",
        "reviewer_A_packet.csv",
        "reviewer_B_packet.csv",
        "adjudication_packet.csv",
    ):
        actual = hashlib.sha256((packet_dir / name).read_bytes()).hexdigest()
        if receipt.get(name + "_sha256") != actual:
            raise ValueError(f"Human receipt checksum mismatch: {name}")
    queries = json.loads((eval_dir / "queries_heldout_50.json").read_text())
    supported = [q["query_id"] for q in queries if q["is_supported"]]
    results: dict[str, Any] = {}
    for system in SYSTEMS:
        run = parse_trec_run(eval_dir / "ranked_runs" / f"{system}.run", depth=1000)
        if any(
            any(pid not in qrels.get(qid, {}) for pid, _, _ in run.get(qid, [])[:TOP_K])
            for qid in supported
        ):
            raise ValueError("Top-5 run contains unjudged items; metrics withheld")
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
        "design": manifest["design"],
        "agreement_overlap_items": len(paired_ids),
        "single_coded_items": EXPECTED_ITEMS - len(paired_ids),
        "supported_query_denominator": len(supported),
        "agreement_before_adjudication": agreement,
        "human_qrel_metrics": results,
    }
    repository_root = EVAL_DIR.parents[1]
    if (repository_root / ".git").exists() and repository_root in output_path.resolve().parents:
        raise ValueError("Human results output must be outside the Git repository")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    qrels_path = output_path.parent / "passage_qrels_human_v1.json"
    if qrels_path.exists() or output_path.exists():
        raise FileExistsError("Refusing to overwrite frozen human outputs")
    qrels_path.write_text(
        json.dumps(
            {
                "provenance": "completed_human_worksheets",
                "design": manifest["design"],
                "qrels": qrels,
            },
            indent=2,
        )
    )
    output_path.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    """Run post-annotation analysis on completed local worksheets."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--eval-dir", type=Path, default=EVAL_DIR)
    args = parser.parse_args()
    print(json.dumps(analyze(args.packets, args.output, args.eval_dir)))


if __name__ == "__main__":
    main()

"""Create fresh system-blinded reviewer packets outside the public repository."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
EXPECTED_ITEMS = 731
ID_BYTES = 12
SECRET_BYTES = 32
REVIEWER_FIELDS = (
    "item_id",
    "query_id",
    "query_text",
    "blinded_candidate_id",
    "canonical_source_doc",
    "canonical_page_number",
    "section_title",
    "passage_text",
    "relevance_grade",
    "claim_supported",
    "reviewer_id",
    "review_date",
    "confidence",
    "notes",
)
HUMAN_FIELDS = (
    "relevance_grade",
    "claim_supported",
    "reviewer_id",
    "review_date",
    "confidence",
    "notes",
)


def prepare_packets(
    output_dir: Path, source_dir: Path = EVAL_DIR, design: str = "full"
) -> dict[str, Any]:
    """Write blank reviewer packets and a private mapping into an external directory."""
    output_dir = output_dir.resolve()
    if (REPO_ROOT / ".git").exists() and (
        output_dir == REPO_ROOT or REPO_ROOT in output_dir.parents
    ):
        raise ValueError("Output must be outside the Git repository")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Output directory must be new or empty")
    data = json.loads((source_dir / "human_annotation_worksheet.json").read_text())
    items = data["items"]
    if len(items) != EXPECTED_ITEMS:
        raise ValueError(f"Expected {EXPECTED_ITEMS} items, found {len(items)}")
    if design not in {"full", "partial"}:
        raise ValueError("design must be full or partial")
    queries = json.loads((source_dir / "queries_heldout_50.json").read_text())
    counts = {q["query_id"]: 0 for q in queries}
    for item in items:
        counts[item["query_id"]] += 1
    overlap_queries: set[str] = set()
    if design == "partial":
        # Freeze a query-stratified overlap before either reviewer receives a packet.
        for category, count in (
            ("core_concept", 4),
            ("relational", 4),
            ("unsupported_abstention", 2),
        ):
            candidates = [q["query_id"] for q in queries if q["category"] == category]
            overlap_queries.update(sorted(candidates, key=lambda q: (-counts[q], q))[:count])
        if sum(counts[q] for q in overlap_queries) < 145:
            raise ValueError("Predeclared overlap has fewer than 145 items")
    old_key = json.loads((source_dir / "worksheets" / "pool_key_SEALED.json").read_text())
    secret = secrets.token_bytes(SECRET_BYTES)
    rows: list[dict[str, Any]] = []
    mapping: dict[str, Any] = {}
    seen: set[str] = set()
    for item in items:
        legacy_item_id = item["item_id"]
        old_id = item["blinded_candidate_id"]
        digest = hmac.new(
            secret, f"{item['query_id']}::{item['passage_id']}".encode(), hashlib.sha256
        ).hexdigest()
        new_id = f"CAND-{digest[: ID_BYTES * 2]}"
        item_id = (
            "ITEM-"
            + hmac.new(secret, f"item::{legacy_item_id}".encode(), hashlib.sha256).hexdigest()[
                : ID_BYTES * 2
            ]
        )
        if new_id == old_id or new_id in seen:
            raise ValueError("Blinded ID collision or legacy ID reuse")
        seen.add(new_id)
        row = {field: item.get(field, "") for field in REVIEWER_FIELDS}
        row["item_id"] = item_id
        row["blinded_candidate_id"] = new_id
        for field in HUMAN_FIELDS:
            row[field] = ""
        rows.append(row)
        mapping[item_id] = {
            "query_id": item["query_id"],
            "blinded_candidate_id": new_id,
            "passage_id": item["passage_id"],
            "contributing_systems": old_key["entries"][legacy_item_id]["contributing_systems"],
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(output_dir, 0o700)
    private_dir = output_dir / "private"
    private_dir.mkdir(mode=0o700)
    key_path = private_dir / "sealed_key.json"
    key_path.write_text(json.dumps({"secret_hex": secret.hex(), "items": mapping}, indent=2))
    os.chmod(key_path, 0o600)
    assignment: dict[str, str] = {}
    for row in rows:
        if design == "full" or row["query_id"] in overlap_queries:
            assignment[row["item_id"]] = "AB"
        else:
            # Balance single-coded queries, without splitting a query across reviewers.
            remaining = sorted(q for q in counts if q not in overlap_queries)
            assignment[row["item_id"]] = "A" if remaining.index(row["query_id"]) % 2 == 0 else "B"
    manifest = {
        "design": design,
        "pool_size": EXPECTED_ITEMS,
        "overlap_queries": sorted(overlap_queries),
        "overlap_items": sum(v == "AB" for v in assignment.values()),
        "assignment": assignment,
    }
    (output_dir / "assignment_manifest.json").write_text(json.dumps(manifest, indent=2))
    for reviewer in ("A", "B"):
        packet = output_dir / f"reviewer_{reviewer}_packet.csv"
        with packet.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEWER_FIELDS)
            writer.writeheader()
            writer.writerows(row for row in rows if reviewer in assignment[row["item_id"]])
    adjudication = output_dir / "adjudication_packet.csv"
    fields = (
        "item_id",
        "query_id",
        "blinded_candidate_id",
        "reviewer_A_grade",
        "reviewer_B_grade",
        "reviewer_A_claim_supported",
        "reviewer_B_claim_supported",
        "adjudicated_relevance_grade",
        "adjudicated_claim_supported",
        "adjudicator_id",
        "adjudication_date",
        "adjudication_rationale",
    )
    with adjudication.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {
                "item_id": row["item_id"],
                "query_id": row["query_id"],
                "blinded_candidate_id": row["blinded_candidate_id"],
            }
            for row in rows
        )
    return {"items": len(rows), "unique_ids": len(seen), "output_dir": str(output_dir)}


def main() -> None:
    """Parse a local-only output path and generate packets."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--design", choices=("full", "partial"), default="full")
    parser.add_argument("--source-dir", type=Path, default=EVAL_DIR)
    args = parser.parse_args()
    print(json.dumps(prepare_packets(args.output, args.source_dir, args.design)))


if __name__ == "__main__":
    main()

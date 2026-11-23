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


def prepare_packets(output_dir: Path, source_dir: Path = EVAL_DIR) -> dict[str, Any]:
    """Write blank reviewer packets and a private mapping into an external directory."""
    output_dir = output_dir.resolve()
    if output_dir == REPO_ROOT or REPO_ROOT in output_dir.parents:
        raise ValueError("Output must be outside the Git repository")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Output directory must be new or empty")
    data = json.loads((source_dir / "human_annotation_worksheet.json").read_text())
    items = data["items"]
    if len(items) != EXPECTED_ITEMS:
        raise ValueError(f"Expected {EXPECTED_ITEMS} items, found {len(items)}")
    old_key = json.loads((source_dir / "worksheets" / "pool_key_SEALED.json").read_text())
    secret = secrets.token_bytes(SECRET_BYTES)
    rows: list[dict[str, Any]] = []
    mapping: dict[str, Any] = {}
    seen: set[str] = set()
    for item in items:
        item_id = item["item_id"]
        old_id = item["blinded_candidate_id"]
        digest = hmac.new(
            secret, f"{item['query_id']}::{item['passage_id']}".encode(), hashlib.sha256
        ).hexdigest()
        new_id = f"CAND-{digest[: ID_BYTES * 2]}"
        if new_id == old_id or new_id in seen:
            raise ValueError("Blinded ID collision or legacy ID reuse")
        seen.add(new_id)
        row = {field: item.get(field, "") for field in REVIEWER_FIELDS}
        row["blinded_candidate_id"] = new_id
        for field in HUMAN_FIELDS:
            row[field] = ""
        rows.append(row)
        mapping[item_id] = {
            "query_id": item["query_id"],
            "blinded_candidate_id": new_id,
            "passage_id": item["passage_id"],
            "contributing_systems": old_key["entries"][item_id]["contributing_systems"],
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(output_dir, 0o700)
    private_dir = output_dir / "private"
    private_dir.mkdir(mode=0o700)
    key_path = private_dir / "sealed_key.json"
    key_path.write_text(json.dumps({"secret_hex": secret.hex(), "items": mapping}, indent=2))
    os.chmod(key_path, 0o600)
    for reviewer in ("A", "B"):
        packet = output_dir / f"reviewer_{reviewer}_packet.csv"
        with packet.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEWER_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    adjudication = output_dir / "adjudication_packet.csv"
    fields = (
        "item_id",
        "query_id",
        "blinded_candidate_id",
        "reviewer_A_grade",
        "reviewer_B_grade",
        "adjudicated_relevance_grade",
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
    args = parser.parse_args()
    print(json.dumps(prepare_packets(args.output)))


if __name__ == "__main__":
    main()

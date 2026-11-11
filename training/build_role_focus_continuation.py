"""Rebalance verified research roles for a short QLoRA continuation pass."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Any

from archipelago.scholarly.extraction.abstract_fields import verify_abstract_fields
from archipelago.scholarly.extraction.slm_paper_fields import verify_candidates
from training.dual_ingest_manifest import PAPERS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "datasets" / "dual_ingest_multisource_v3"
OUTPUT = ROOT / "data" / "datasets" / "dual_ingest_role_focus_v4"
RARE_FIELDS = frozenset({"algorithms", "model_architecture", "datasets", "reported_results"})
ACADEMIC_POSITIVE_COUNT = 20
ACADEMIC_NEGATIVE_COUNT = 20
GENERAL_RESEARCH_COUNT = 20
SELECTION_SEED = 42
MAX_CONTINUATION_ROWS = 250


def _rows(path: Path) -> list[dict[str, Any]]:
    """Read one immutable source split."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _focus(row: dict[str, Any], field: dict[str, Any]) -> dict[str, Any] | None:
    """Create one source-verified target under the production task prompt."""
    if row["task"] == "research_abstract":
        source = row["messages"][1]["content"]
        sentence = next(
            (item for item in _sentences(source) if field["value"].casefold() in item.casefold()),
            "",
        )
        if not sentence or not verify_abstract_fields([field], sentence):
            return None
        user_content = sentence
        target = {key: field[key] for key in ("group", "field", "value")}
    else:
        source = json.loads(row["messages"][1]["content"])
        matching = [
            span
            for span in source["spans"]
            if span["pdf_page"] == field["pdf_page"]
            and span["section"] == field["section"]
            and field["evidence_text"].casefold() in span["text"].casefold()
        ]
        if not matching or not verify_candidates([field], matching[:1]):
            return None
        user_content = json.dumps({"registry": source["registry"], "spans": matching[:1]})
        target = field
    return {
        **{key: row[key] for key in ("paper_id", "provider", "source_url", "source_sha256")},
        "task": row["task"],
        "variant": f"role_focus_{field['field']}",
        "gold_fields": [target],
        "label_origin": "source_literal_role_focus",
        "messages": [
            row["messages"][0],
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps({"fields": [target]}, ensure_ascii=False)},
        ],
    }


def build(source: Path, output: Path) -> dict[str, Any]:
    """Keep the paper-isolated validation and test splits unchanged."""
    train = _rows(source / "train.jsonl")
    validation = _rows(source / "validation.jsonl")
    test = _rows(source / "test.jsonl")
    rng = random.Random(SELECTION_SEED)
    selected: list[dict[str, Any]] = []
    rare = [
        row
        for row in train
        if row["task"].startswith("research_")
        and row["variant"] == "complete"
        and any(field["field"] in RARE_FIELDS for field in row["gold_fields"])
    ]
    selected.extend(rare)
    for row in rare:
        for field in row["gold_fields"]:
            if field["field"] in RARE_FIELDS:
                focused = _focus(row, field)
                if focused is not None:
                    selected.append(focused)
    reviewed = {paper.arxiv_id for paper in PAPERS if paper.split == "train"}
    selected.extend(row for row in rare if row["paper_id"] in reviewed)
    positives = [
        row for row in train if row["task"] == "academic_okf" and row["variant"] == "complete"
    ]
    negatives = [row for row in train if row["task"] == "academic_okf" and not row["gold_concepts"]]
    selected.extend(rng.sample(positives, min(ACADEMIC_POSITIVE_COUNT, len(positives))))
    selected.extend(rng.sample(negatives, min(ACADEMIC_NEGATIVE_COUNT, len(negatives))))
    general = [
        row
        for row in train
        if row["task"].startswith("research_") and row["variant"] == "complete" and row not in rare
    ]
    selected.extend(rng.sample(general, min(GENERAL_RESEARCH_COUNT, len(general))))
    if len(selected) > MAX_CONTINUATION_ROWS:
        raise ValueError("Role-focused continuation set exceeded its cap")
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", selected), ("validation", validation), ("test", test)):
        (output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )
    if (output / "test.jsonl").read_bytes() != (source / "test.jsonl").read_bytes():
        raise ValueError("Held-out test changed")
    digest = hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()
    report = {
        "source_manifest_sha256": digest,
        "train_rows": len(selected),
        "validation_rows": len(validation),
        "test_rows": len(test),
        "role_focus_rows": sum(row["variant"].startswith("role_focus_") for row in selected),
        "test_used_in_training": False,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    """Write a small continuation set from existing real papers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()

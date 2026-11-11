"""Add hard negatives and concise evidence tasks without touching held-out papers."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from okf.academic_prompt import academic_messages

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "datasets" / "dual_ingest_multisource_v2"
OUTPUT = ROOT / "data" / "datasets" / "dual_ingest_multisource_v3"
SPLITS = ("train", "validation", "test")
TRAINABLE_SPLITS = ("train", "validation")
MAX_EXAMPLES = 1000
NEGATIVE_TITLES = ("References", "Index", "Copyright and publication information")


def _rows(path: Path) -> list[dict[str, Any]]:
    """Read one immutable source split."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _negative_row(paper: dict[str, Any], index: int) -> dict[str, Any]:
    """Teach abstention on a citation rather than an explanatory passage."""
    title = NEGATIVE_TITLES[index % len(NEGATIVE_TITLES)]
    source_title = json.loads(paper["messages"][1]["content"])["title"]
    citation = (
        f"{title.upper()}\n\n"
        f"[1] {source_title}. Source: {paper['source_url']}. "
        "This entry provides bibliographic metadata only. "
        "It does not explain, define, or teach the cited method."
    )
    return {
        "task": "academic_okf",
        "paper_id": paper["paper_id"],
        "variant": f"negative_{index % len(NEGATIVE_TITLES)}",
        "provider": paper["provider"],
        "source_url": paper["source_url"],
        "source_sha256": paper["source_sha256"],
        "gold_concepts": [],
        "label_origin": "bibliographic_hard_negative",
        "messages": [
            *academic_messages(citation, title),
            {"role": "assistant", "content": "[]"},
        ],
    }


def _focused_abstract_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Ask for one literal fact from a real source sentence."""
    fields = row["gold_fields"]
    if not fields:
        return None
    field = fields[0]
    source = row["messages"][1]["content"]
    sentence = next(
        (
            part.strip()
            for part in source.split(". ")
            if field["value"].casefold() in part.casefold()
        ),
        "",
    )
    if not sentence:
        return None
    if not sentence.endswith("."):
        sentence += "."
    if field["value"].casefold() not in sentence.casefold():
        return None
    return {
        **{key: row[key] for key in ("paper_id", "provider", "source_url", "source_sha256")},
        "task": "research_abstract",
        "variant": "focused_fact",
        "gold_fields": [field],
        "label_origin": "source_literal_single_fact",
        "messages": [
            row["messages"][0],
            {"role": "user", "content": sentence},
            {"role": "assistant", "content": json.dumps({"fields": [field]}, ensure_ascii=False)},
        ],
    }


def _focused_quote_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Train a short valid page-linked response to one real source span."""
    fields = row["gold_fields"]
    if not fields:
        return None
    field = fields[0]
    source = json.loads(row["messages"][1]["content"])
    matching = [
        span
        for span in source["spans"]
        if span["pdf_page"] == field["pdf_page"]
        and span["section"] == field["section"]
        and field["evidence_text"].casefold() in span["text"].casefold()
    ]
    if not matching:
        return None
    return {
        **{key: row[key] for key in ("paper_id", "provider", "source_url", "source_sha256")},
        "task": "research_quote_spans",
        "variant": "focused_quote",
        "gold_fields": [field],
        "label_origin": "source_literal_single_span",
        "messages": [
            row["messages"][0],
            {
                "role": "user",
                "content": json.dumps({"registry": source["registry"], "spans": matching[:1]}),
            },
            {"role": "assistant", "content": json.dumps({"fields": [field]}, ensure_ascii=False)},
        ],
    }


def build(source: Path, output: Path) -> dict[str, Any]:
    """Write new train/validation rows and copy the held-out test exactly."""
    output.mkdir(parents=True, exist_ok=True)
    rows_by_split = {split: _rows(source / f"{split}.jsonl") for split in SPLITS}
    ids = {split: {row["paper_id"] for row in rows} for split, rows in rows_by_split.items()}
    if any(ids[left] & ids[right] for left in SPLITS for right in SPLITS if left < right):
        raise ValueError("Paper-level leakage in input dataset")
    added: Counter[str] = Counter()
    for split in TRAINABLE_SPLITS:
        by_paper: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows_by_split[split]:
            if row["variant"] == "complete":
                by_paper.setdefault(row["paper_id"], {})[row["task"]] = row
        for index, tasks in enumerate(by_paper.values()):
            if set(tasks) != {"academic_okf", "research_abstract", "research_quote_spans"}:
                raise ValueError("Incomplete task group for a paper")
            additions = (
                _negative_row(tasks["academic_okf"], index),
                _focused_abstract_row(tasks["research_abstract"]),
                _focused_quote_row(tasks["research_quote_spans"]),
            )
            for addition in additions:
                if addition is not None:
                    rows_by_split[split].append(addition)
                    added[addition["task"]] += 1
    if sum(map(len, rows_by_split.values())) > MAX_EXAMPLES:
        raise ValueError("Augmented corpus exceeded its example budget")
    for split, rows in rows_by_split.items():
        (output / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )
    if (output / "test.jsonl").read_bytes() != (source / "test.jsonl").read_bytes():
        raise ValueError("Held-out test changed")
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    augmentation: dict[str, Any] = {
        "policy": "train_and_validation_only; test copied byte-for-byte",
        "added_by_task": dict(added),
        "total_rows": {split: len(rows) for split, rows in rows_by_split.items()},
    }
    manifest["augmentation"] = augmentation
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return augmentation


def main() -> None:
    """Augment the immutable multi-source corpus."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()

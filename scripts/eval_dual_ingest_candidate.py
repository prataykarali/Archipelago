"""Score a candidate adapter on papers never used for training or validation."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from peft import PeftModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from archipelago.eval.extract_eval import prf, summarize, validate_schema
from archipelago.scholarly.extraction.abstract_fields import verify_abstract_fields
from archipelago.scholarly.extraction.slm_paper_fields import verify_candidates
from okf.academic_prompt import academic_messages
from training.dual_ingest_manifest import PAPERS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "datasets" / "dual_ingest_multisource_v2"
DEFAULT_ADAPTER = ROOT / "models" / "dual_ingest_candidate_v2"
ACADEMIC_PROBES = ROOT / "tests" / "fixtures" / "extraction_probes.jsonl"
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
MAX_GENERATION_TOKENS = 500


def _fields(value: object) -> list[dict[str, Any]]:
    """Read only the fields array from a strict JSON object."""
    return (
        value["fields"] if isinstance(value, dict) and isinstance(value.get("fields"), list) else []
    )


def _field_key(field: dict[str, Any]) -> tuple[str, str, str]:
    """Normalize field identity without treating a quote as semantic proof."""
    return (
        str(field.get("group", "")),
        str(field.get("field", "")),
        str(field.get("value", "")).casefold(),
    )


def _score_sets(predicted: set[Any], gold: set[Any]) -> dict[str, float]:
    """Compute precision, recall, and F1 for one nonempty gold record."""
    hits = len(predicted & gold)
    precision = hits / len(predicted) if predicted else 0.0
    recall = hits / len(gold) if gold else float(not predicted)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _score_row(row: dict[str, Any], raw: str) -> dict[str, Any]:
    """Apply the same validators used by the two ingestion paths."""
    try:
        payload = json.loads(raw)
        valid_json = True
    except json.JSONDecodeError:
        payload = None
        valid_json = False
    task = row["task"]
    if task == "academic_okf":
        concepts = payload if isinstance(payload, list) else []
        names = [str(item.get("concept_name", "")) for item in concepts if isinstance(item, dict)]
        scores = prf(names, row["gold_concepts"])
        accepted = validate_schema(concepts) and bool(concepts)
        return {
            "valid_json": valid_json,
            "schema_valid": accepted,
            "predicted": names,
            "gold": row["gold_concepts"],
            "precision": scores["precision"],
            "recall": scores["recall"],
            "f1": scores["f1"],
        }
    candidates = _fields(payload)
    if task == "research_abstract":
        source = row["messages"][1]["content"]
        verified = verify_abstract_fields(candidates, source)
    else:
        spans = json.loads(row["messages"][1]["content"])["spans"]
        verified = verify_candidates(candidates, spans)
    predicted = {_field_key(field) for field in verified}
    gold = {_field_key(field) for field in row["gold_fields"]}
    predicted_roles = {(group, field) for group, field, _ in predicted}
    gold_roles = {(group, field) for group, field, _ in gold}
    return {
        "valid_json": valid_json,
        "raw_candidate_count": len(candidates),
        "accepted_count": len(verified),
        "predicted": sorted(predicted),
        "gold": sorted(gold),
        "role_f1": _score_sets(predicted_roles, gold_roles)["f1"],
        **_score_sets(predicted, gold),
    }


def evaluate(dataset_dir: Path, adapter_dir: Path) -> dict[str, Any]:
    """Generate on held-out papers and report per-task factual performance."""
    rows = [
        json.loads(line)
        for line in (dataset_dir / "test.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    train_ids = {
        json.loads(line)["paper_id"]
        for line in (dataset_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()
    }
    validation_ids = {
        json.loads(line)["paper_id"]
        for line in (dataset_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines()
    }
    test_ids = {row["paper_id"] for row in rows}
    if train_ids & test_ids or validation_ids & test_ids:
        raise ValueError("Held-out paper leaked into training or validation")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, local_files_only=True)
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else "cpu",
        local_files_only=True,
    )
    model = PeftModel.from_pretrained(base, str(adapter_dir), local_files_only=True)
    model.eval()
    cases = []
    reviewed_ids = {paper.arxiv_id for paper in PAPERS if paper.split == "test"}
    for index, row in enumerate(rows, start=1):
        prompt = tokenizer.apply_chat_template(
            row["messages"][:-1], tokenize=False, add_generation_prompt=True
        )
        encoded = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **encoded,
                max_new_tokens=MAX_GENERATION_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        raw = tokenizer.decode(
            output[0][encoded["input_ids"].shape[1] :], skip_special_tokens=True
        ).strip()
        score = _score_row(row, raw)
        cases.append(
            {
                "paper_id": row["paper_id"],
                "task": row["task"],
                "variant": row["variant"],
                "provider": row.get("provider", "arxiv"),
                "reviewed_label": row["paper_id"] in reviewed_ids,
                "response": raw,
                **score,
            }
        )
        print(
            f"{index}/{len(rows)} {row['paper_id']} {row['task']} F1={score['f1']:.3f}", flush=True
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[case["task"]].append(case)
    summary = {
        task: {
            "n": len(group),
            "valid_json_rate": sum(case["valid_json"] for case in group) / len(group),
            "mean_precision": sum(case["precision"] for case in group) / len(group),
            "mean_recall": sum(case["recall"] for case in group) / len(group),
            "mean_f1": sum(case["f1"] for case in group) / len(group),
            "f1_distribution": summarize([case["f1"] for case in group]),
            **(
                {"schema_valid_rate": sum(case["schema_valid"] for case in group) / len(group)}
                if task == "academic_okf"
                else {
                    "verified_nonempty_rate": sum(case["accepted_count"] > 0 for case in group)
                    / len(group),
                    "mean_verified_fields": sum(case["accepted_count"] for case in group)
                    / len(group),
                    "role_f1_distribution": summarize([case["role_f1"] for case in group]),
                }
            ),
        }
        for task, group in grouped.items()
    }
    reviewed_summary = {
        task: summarize([case["f1"] for case in group if case["reviewed_label"]])
        for task, group in grouped.items()
    }
    by_provider_task: dict[str, list[float]] = defaultdict(list)
    for case in cases:
        by_provider_task[f"{case['provider']}:{case['task']}"].append(case["f1"])
    provider_summary = {key: summarize(values) for key, values in sorted(by_provider_task.items())}
    academic_probes = []
    for probe in (
        json.loads(line) for line in ACADEMIC_PROBES.read_text(encoding="utf-8").splitlines()
    ):
        messages = academic_messages(
            probe["text"], probe.get("book_title", ""), probe.get("domain", "Computer Science")
        )
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **encoded,
                max_new_tokens=MAX_GENERATION_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        raw = tokenizer.decode(
            output[0][encoded["input_ids"].shape[1] :], skip_special_tokens=True
        ).strip()
        score = _score_row({"task": "academic_okf", "gold_concepts": probe["gold"]}, raw)
        academic_probes.append(
            {"probe_id": probe["probe_id"], "tag": probe["tag"], "response": raw, **score}
        )
        print(f"probe {probe['probe_id']} F1={score['f1']:.3f}", flush=True)
    return {
        "adapter": str(adapter_dir),
        "held_out_papers": sorted(test_ids),
        "summary": summary,
        "reviewed_label_f1": reviewed_summary,
        "provider_task_f1": provider_summary,
        "academic_operational_probes": {
            "f1_distribution": summarize([case["f1"] for case in academic_probes]),
            "empty_match_rate": sum(
                not case["predicted"] for case in academic_probes if not case["gold"]
            )
            / max(1, sum(not case["gold"] for case in academic_probes)),
            "cases": academic_probes,
        },
        "cases": cases,
    }


def main() -> None:
    """Save the complete per-paper result next to the trained adapter."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER)
    args = parser.parse_args()
    report = evaluate(args.dataset_dir, args.adapter_dir)
    path = args.adapter_dir / "held_out_eval.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()

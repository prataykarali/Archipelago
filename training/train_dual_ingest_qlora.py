"""Train one candidate adapter on separate academic and research ingestion tasks."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from datasets import Dataset
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "datasets" / "dual_ingest_multisource_v2"
DEFAULT_OUTPUT = ROOT / "models" / "dual_ingest_candidate_v2"
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
MAX_SEQUENCE_TOKENS = 1536
LORA_RANK = 8
LORA_ALPHA = 16
LEARNING_RATE = 0.0001
TRAIN_EPOCHS = 2
GRADIENT_ACCUMULATION = 4
TRAIN_BATCH_SIZE = 1
TRAIN_SEED = 42
LORA_DROPOUT = 0.05
WARMUP_RATIO = 0.05
BYTES_PER_MIB = 1024 * 1024


def _read_rows(path: Path) -> list[dict[str, Any]]:
    """Load a builder-produced split with a failing empty-data check."""
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows:
        raise ValueError(f"Empty training split: {path}")
    return rows


def _preflight(dataset_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """Enforce paper-level isolation before any model is loaded."""
    train = _read_rows(dataset_dir / "train.jsonl")
    validation = _read_rows(dataset_dir / "validation.jsonl")
    test = _read_rows(dataset_dir / "test.jsonl")
    identifiers = [{row["paper_id"] for row in split} for split in (train, validation, test)]
    if (
        identifiers[0] & identifiers[1]
        or identifiers[0] & identifiers[2]
        or identifiers[1] & identifiers[2]
    ):
        raise ValueError("Paper-level dataset leakage")
    expected_tasks = {"academic_okf", "research_abstract", "research_quote_spans"}
    for split in (train, validation, test):
        if {row["task"] for row in split} != expected_tasks:
            raise ValueError("A dataset split is missing an ingestion task")
    digest = hashlib.sha256((dataset_dir / "manifest.json").read_bytes()).hexdigest()
    return train, validation, digest


def _completion_dataset(rows: list[dict[str, Any]], tokenizer: Any) -> Dataset:
    """Mask the source prompt so training loss measures target output only."""
    examples = []
    for row in rows:
        messages = row["messages"]
        examples.append(
            {
                "prompt": tokenizer.apply_chat_template(
                    messages[:-1], tokenize=False, add_generation_prompt=True
                ),
                "completion": messages[-1]["content"] + tokenizer.eos_token,
            }
        )
    return Dataset.from_list(examples)


def train(
    dataset_dir: Path,
    output_dir: Path,
    epochs: int,
    *,
    init_adapter: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Fit a local candidate adapter without touching deployed Ollama models."""
    train_rows, validation_rows, dataset_digest = _preflight(dataset_dir)
    result: dict[str, Any] = {
        "base_model": BASE_MODEL,
        "dataset_manifest_sha256": dataset_digest,
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "test_rows_used_in_training": 0,
        "epochs": epochs,
        "output_dir": str(output_dir),
        "init_adapter": str(init_adapter) if init_adapter else None,
    }
    if init_adapter is not None and not (init_adapter / "adapter_model.safetensors").is_file():
        raise FileNotFoundError(f"No adapter in {init_adapter}")
    if dry_run:
        return result
    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA training requires the local CUDA GPU")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=quantization,
        device_map="auto",
        dtype=torch.float16,
        local_files_only=True,
    )
    base = prepare_model_for_kbit_training(base)
    if init_adapter is not None:
        adapter = PeftModel.from_pretrained(base, str(init_adapter), is_trainable=True)
    else:
        adapter = get_peft_model(
            base,
            LoraConfig(
                r=LORA_RANK,
                lora_alpha=LORA_ALPHA,
                lora_dropout=LORA_DROPOUT,
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            ),
        )
    config = SFTConfig(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=TRAIN_BATCH_SIZE,
        per_device_eval_batch_size=TRAIN_BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=WARMUP_RATIO,
        max_length=MAX_SEQUENCE_TOKENS,
        completion_only_loss=True,
        gradient_checkpointing=True,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        optim="paged_adamw_8bit",
        eval_strategy="epoch",
        save_strategy="no",
        logging_steps=1,
        report_to="none",
        seed=TRAIN_SEED,
        data_seed=TRAIN_SEED,
    )
    trainer = SFTTrainer(
        model=adapter,
        args=config,
        train_dataset=_completion_dataset(train_rows, tokenizer),
        eval_dataset=_completion_dataset(validation_rows, tokenizer),
        processing_class=tokenizer,
    )
    train_result = trainer.train()
    evaluation = trainer.evaluate()
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    result.update(
        {
            "finished_at": datetime.now(UTC).isoformat(),
            "train_loss": train_result.training_loss,
            "validation_loss": evaluation.get("eval_loss"),
            "peak_gpu_memory_mib": round(torch.cuda.max_memory_allocated() / BYTES_PER_MIB),
        }
    )
    (output_dir / "dual_ingest_training_report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    """Run checked QLoRA training or a no-model preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=TRAIN_EPOCHS)
    parser.add_argument("--init-adapter", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("epochs must be positive")
    print(
        json.dumps(
            train(
                args.dataset_dir,
                args.output_dir,
                args.epochs,
                init_adapter=args.init_adapter,
                dry_run=args.dry_run,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

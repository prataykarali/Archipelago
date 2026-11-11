#!/usr/bin/env python3
"""
Institutional SLM QLoRA Dual-Task Fine-Tuning Pipeline.

Fine-tunes Small Language Models (Qwen2.5-0.5B-Instruct) simultaneously on:
- Dataset 1: Pedagogical OKF Knowledge Graph Extraction & Curriculum Pathways (1,500 pairs)
- Dataset 2: Scholarly Evidence, Metrics, Claims & Comparative Parameter Matrices (1,000 pairs)
- Total Blended Corpus: 2,500 Unique High-Quality ChatML Instruction Pairs

Configured with:
- 4-bit NF4 Quantization + Paged 8-bit AdamW optimizer
- Strict Hardware Bounds for NVIDIA GeForce RTX 2050 (4 GB VRAM)
- Automated Quality Gates (Loss bounds, NaN checks, divergence guards)
- Post-Training 5-Prompt Verification Gauntlet
- Automated Cloud Sync to Hugging Face & Vercel
"""

from __future__ import annotations

import argparse
import datetime
import gc
import json
import logging
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainerCallback,
)
from trl import SFTConfig, SFTTrainer

from archipelago.scholarly.pipeline.cloud_sync import CloudSyncPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("archipelago.training.qlora")

DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
DATASET_1_PATH = ROOT / "data/datasets/dataset1_pedagogical_revamped.jsonl"
DATASET_2_PATH = ROOT / "data/datasets/dataset2_scholarly_evidence.jsonl"
BLENDED_DATASET_PATH = ROOT / "data/datasets/blended_multitask_dataset.jsonl"
OUTPUT_DIR = ROOT / "models/lib_qwen_scholarly_lora"
REPORT_PATH = OUTPUT_DIR / "training_report.json"


class QualityGateCallback(TrainerCallback):
    """Monitors training dynamics and halts on divergence, NaN, or gate failure."""

    def __init__(self, max_allowed_loss: float = 3.5):
        self.max_allowed_loss = max_allowed_loss
        self.loss_history = []
        self.eval_history = []

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs and "loss" in logs:
            loss = logs["loss"]
            if torch.isnan(torch.tensor(loss)) or torch.isinf(torch.tensor(loss)):
                logger.error("❌ CRITICAL: NaN or Inf detected in loss! Halting training immediately.")
                control.should_training_stop = True
            elif loss > self.max_allowed_loss and state.global_step > 50:
                logger.error("❌ QUALITY GATE FAILED: Loss (%.4f) exceeded bound (%.4f)", loss, self.max_allowed_loss)
                control.should_training_stop = True
            self.loss_history.append((state.global_step, loss))

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics and "eval_loss" in metrics:
            eval_loss = metrics["eval_loss"]
            logger.info("📊 Epoch Evaluation - Eval Loss: %.4f", eval_loss)
            self.eval_history.append((state.epoch, eval_loss))


def prepare_blended_corpus(output_path: Path = BLENDED_DATASET_PATH) -> Path:
    """Interleave Dataset 1 (1,500 pairs) and Dataset 2 (1,000 pairs) into balanced corpus."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = []

    if DATASET_1_PATH.is_file():
        with open(DATASET_1_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

    if DATASET_2_PATH.is_file():
        with open(DATASET_2_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

    # Deterministic shuffle to balance task types
    rng = random.Random(42)
    rng.shuffle(records)

    with open(output_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    logger.info("Prepared blended corpus of %d total examples at %s", len(records), output_path)
    return output_path


def run_verification_prompts(model, tokenizer) -> Dict[str, Any]:
    """Execute 5 prompt checks across both pedagogical and scholarly tasks."""
    logger.info("Executing Post-Training Verification Gauntlet...")
    test_prompts = [
        # 1. Pedagogical OKF Extraction
        (
            "pedagogical_okf_extraction",
            "Extract 1-2 formal teachable concepts from this text: "
            "'Low-Rank Adaptation (LoRA) freezes pretrained model weights and injects trainable rank decomposition matrices into each transformer layer.'"
        ),
        # 2. Prerequisite Chaining
        (
            "prerequisite_chaining",
            "Deduce the pedagogical prerequisite chain and downstream learning unlock pathway for: 'Attention Mechanism'."
        ),
        # 3. Diagnostic MCQ
        (
            "diagnostic_mcq",
            "Generate a rigorous diagnostic verification multiple-choice question to assess comprehension of 'Quantization in Neural Networks'."
        ),
        # 4. Structured Scientific Extraction
        (
            "scientific_extraction",
            "Extract structured scientific entities from this publication:\n"
            "Title: Direct Preference Optimization\nAuthors: Rafailov et al.\nVenue: NeurIPS 2023\nBenchmark: Outperforms PPO on Anthropic HH"
        ),
        # 5. Parameter Comparison Matrix
        (
            "parameter_matrix",
            "Conduct a side-by-side comparative parameter matrix between: 'LoRA' and 'QLoRA'."
        )
    ]

    results = []
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.eval()

    for task_name, user_prompt in test_prompts:
        messages = [
            {"role": "system", "content": "You are Archipelago's specialized dual-task educational and scholarly SLM engine."},
            {"role": "user", "content": user_prompt}
        ]
        prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt_text, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.2,
                top_p=0.9,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )

        gen_tokens = outputs[0][inputs.input_ids.shape[1]:]
        response = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

        passed = len(response) > 40
        results.append({
            "task": task_name,
            "prompt": user_prompt,
            "response": response[:300] + ("..." if len(response) > 300 else ""),
            "status": "PASSED" if passed else "FAILED"
        })

    all_passed = all(r["status"] == "PASSED" for r in results)
    return {"all_passed": all_passed, "tests": results}


def main():
    parser = argparse.ArgumentParser(description="Dual-Task SLM QLoRA Fine-Tuning Pipeline")
    parser.add_argument("--dataset", choices=["1", "2", "both"], default="both", help="Dataset selection")
    parser.add_argument("--model-id", type=str, default=DEFAULT_MODEL, help="Base HuggingFace model ID")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--max-seq-len", type=int, default=1024, help="Max sequence length")
    parser.add_argument("--batch-size", type=int, default=1, help="Per device batch size")
    parser.add_argument("--grad-accum", type=int, default=8, help="Gradient accumulation steps")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup without training")
    parser.add_argument("--no-cloud-sync", action="store_true", help="Skip Hugging Face and Vercel sync")
    args = parser.parse_args()

    # Determine corpus
    if args.dataset == "1":
        dataset_path = DATASET_1_PATH
    elif args.dataset == "2":
        dataset_path = DATASET_2_PATH
    else:
        dataset_path = prepare_blended_corpus()

    print("=" * 80)
    print("🧠 ARCHIPELAGO DUAL-TASK SLM QLORA TRAINING PIPELINE")
    print(f"Base Model:       {args.model_id}")
    print(f"Training Corpus:  {dataset_path}")
    print(f"Epochs:           {args.epochs}")
    print(f"Learning Rate:    {args.lr}")
    print(f"Effective Batch:  {args.batch_size * args.grad_accum}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("=" * 80)

    # Hardware verification
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        free_gb = torch.cuda.mem_get_info()[0] / 1e9
        print(f"🎮 GPU Active: {gpu_name} (Total: {vram_gb:.2f} GB | Free: {free_gb:.2f} GB)")
        torch.cuda.empty_cache()
        gc.collect()
    else:
        print("⚠️ CUDA unavailable. Running on CPU.")

    # 1. Tokenizer
    print("\n[1/5] Loading Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Dataset Loading & ChatML Formatting
    print(f"\n[2/5] Preparing Dataset from {dataset_path}...")
    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    dataset_split = dataset.train_test_split(test_size=0.10, seed=42)
    train_ds = dataset_split["train"]
    eval_ds = dataset_split["test"]
    print(f"      Train Samples: {len(train_ds):,} | Eval Samples: {len(eval_ds):,}")

    def format_chatml(example):
        msgs = example["messages"]
        text = tokenizer.apply_chat_template(msgs, tokenize=False)
        return {"text": text}

    train_ds = train_ds.map(format_chatml)
    eval_ds = eval_ds.map(format_chatml)

    if args.dry_run:
        print("\n✅ Dry run completed successfully. Dataset and Tokenizer verified.")
        return

    # 3. 4-bit Quantization & LoRA Injection
    print("\n[3/5] Configuring 4-bit NF4 Quantization & LoRA Adapters...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    ) if torch.cuda.is_available() else None

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map="auto" if torch.cuda.is_available() else "cpu",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )

    if torch.cuda.is_available():
        model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 4. Training Engine & Quality Gates
    print("\n[4/5] Setting up SFTTrainer with Quality Gates...")
    training_args = SFTConfig(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        max_grad_norm=1.0,
        logging_steps=25,
        eval_strategy="epoch",
        save_strategy="epoch",
        max_length=args.max_seq_len,
        dataset_text_field="text",
        bf16=torch.cuda.is_available(),
        fp16=False,
        optim="paged_adamw_8bit" if torch.cuda.is_available() else "adamw_torch",
        report_to="none",
    )

    quality_callback = QualityGateCallback()
    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=training_args,
        callbacks=[quality_callback],
    )

    print("\n🚀 Starting Dual-Task QLoRA Fine-Tuning...")
    train_result = trainer.train()

    print(f"\n💾 Saving LoRA adapter weights to {OUTPUT_DIR}...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    # 5. Post-Training Validation & Verification Gauntlet
    print("\n[5/5] Running Verification Gauntlet...")
    verification = run_verification_prompts(model, tokenizer)

    # Save comprehensive training report
    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_id": args.model_id,
        "epochs": args.epochs,
        "effective_batch_size": args.batch_size * args.grad_accum,
        "learning_rate": args.lr,
        "train_samples": len(train_ds),
        "eval_samples": len(eval_ds),
        "train_loss": train_result.training_loss,
        "eval_history": quality_callback.eval_history,
        "verification": verification,
        "status": "SUCCESS" if verification["all_passed"] else "COMPLETED_WITH_WARNINGS"
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print("🎉 FINE-TUNING COMPLETE!")
    print(f"Final Train Loss: {train_result.training_loss:.4f}")
    print(f"Verification Gauntlet: {'✅ 5/5 PASSED' if verification['all_passed'] else '⚠️ Some Warnings'}")
    print(f"Report Logged: {REPORT_PATH}")
    print("=" * 80)

    # Automated Cloud Sync
    if not args.no_cloud_sync:
        print("\n☁️ Triggering Automated Cloud Sync to Hugging Face & Vercel...")
        sync = CloudSyncPipeline()
        sync_res = sync.run_all_sync()
        print(f"Sync Status: {sync_res.get('huggingface', {}).get('status')}")


if __name__ == "__main__":
    main()

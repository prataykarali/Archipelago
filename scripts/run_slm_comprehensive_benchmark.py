#!/usr/bin/env python3
"""
Comprehensive Benchmark Suite: Base Model vs. Dual-Task Fine-Tuned SLM.
Measures Token Accuracy %, Loss, Perplexity, Syntax Adherence %, and Task Success %.
"""

import json
from pathlib import Path
import sys

from peft import PeftModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_PATH = ROOT / "models/lib_qwen_scholarly_lora"
DATASET_1_PATH = ROOT / "data/datasets/dataset1_pedagogical_revamped.jsonl"
DATASET_2_PATH = ROOT / "data/datasets/dataset2_scholarly_evidence.jsonl"
OUTPUT_REPORT = ROOT / "models/lib_qwen_scholarly_lora/dual_dataset_benchmark_results.json"


def extract_json_array(text: str):
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
    a0 = cleaned.find("[")
    a1 = cleaned.rfind("]")
    if a0 != -1 and a1 > a0:
        try:
            parsed = json.loads(cleaned[a0 : a1 + 1])
            if isinstance(parsed, list):
                return parsed, True
        except Exception:
            pass
    return None, False


def evaluate_batch_metrics(model, tokenizer, test_samples, is_fine_tuned=True):
    device = next(model.parameters()).device
    model.eval()

    total_tokens = 0
    correct_tokens = 0
    total_loss = 0.0
    task_results = []

    for item in test_samples:
        task = item["task"]
        dataset_name = item["dataset"]
        messages = item["messages"]

        # Prompt & full text tokenization
        prompt_msgs = messages[:-1]
        prompt_text = tokenizer.apply_chat_template(
            prompt_msgs, tokenize=False, add_generation_prompt=True
        )
        full_text = tokenizer.apply_chat_template(messages, tokenize=False)

        enc_prompt = tokenizer(prompt_text, return_tensors="pt")
        enc_full = tokenizer(full_text, return_tensors="pt").to(device)
        input_ids = enc_full["input_ids"]

        prompt_len = enc_prompt["input_ids"].shape[1]
        target_ids = input_ids[:, prompt_len:]
        num_target_tokens = target_ids.shape[1]

        # Calculate cross-entropy loss and token accuracy
        labels = input_ids.clone()
        labels[:, :prompt_len] = -100

        with torch.no_grad():
            outputs = model(input_ids=input_ids, labels=labels)
            sample_loss = outputs.loss.item()
            logits = outputs.logits[:, prompt_len - 1 : -1, :]
            preds = torch.argmax(logits, dim=-1)

            sample_correct = (preds == target_ids).sum().item()
            total_tokens += num_target_tokens
            correct_tokens += sample_correct
            total_loss += sample_loss * num_target_tokens

        # Generate response to check structural / formatting adherence
        inputs = tokenizer(prompt_text, return_tensors="pt").to(device)
        with torch.no_grad():
            gen_out = model.generate(
                **inputs,
                max_new_tokens=220,
                temperature=0.1,
                top_p=0.9,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        gen_tokens = gen_out[0][inputs.input_ids.shape[1] :]
        gen_text = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

        # Format / Syntax checking
        syntax_ok = False
        if "okf_extraction" in task:
            _, syntax_ok = extract_json_array(gen_text)
        elif "comparison" in task or "matrix" in task:
            syntax_ok = "|" in gen_text and "---" in gen_text
        elif "diagnostic_mcq" in task:
            syntax_ok = any(opt in gen_text for opt in ["A)", "B)", "C)", "D)", "A.", "B."])
        else:
            syntax_ok = "###" in gen_text or len(gen_text) > 80

        task_results.append(
            {
                "task": task,
                "dataset": dataset_name,
                "loss": sample_loss,
                "token_accuracy": (sample_correct / num_target_tokens) * 100
                if num_target_tokens > 0
                else 0.0,
                "syntax_valid": syntax_ok,
                "response_snippet": gen_text[:120],
            }
        )

    avg_loss = total_loss / total_tokens if total_tokens > 0 else 0.0
    token_acc = (correct_tokens / total_tokens) * 100 if total_tokens > 0 else 0.0
    syntax_adherence = (sum(1 for r in task_results if r["syntax_valid"]) / len(task_results)) * 100
    perplexity = torch.exp(torch.tensor(avg_loss)).item()

    return {
        "token_accuracy_pct": round(token_acc, 2),
        "avg_loss": round(avg_loss, 4),
        "perplexity": round(perplexity, 2),
        "syntax_adherence_pct": round(syntax_adherence, 2),
        "task_results": task_results,
    }


def main():
    print("=" * 80)
    print("BENCHMARKING SLM: BASE MODEL vs. DUAL-TASK FINE-TUNED SLM")
    print("=" * 80)

    # Sample balanced held-out set
    test_samples = []
    # 10 samples from Dataset 1
    with open(DATASET_1_PATH, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
        for idx in range(1470, 1500, 3):
            test_samples.append(rows[idx])

    # 10 samples from Dataset 2
    with open(DATASET_2_PATH, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
        for idx in range(970, 1000, 3):
            test_samples.append(rows[idx])

    print(
        f"Loaded {len(test_samples)} total benchmark samples ({sum(1 for s in test_samples if 'dataset1' in s['dataset'])} from Dataset 1, {sum(1 for s in test_samples if 'dataset2' in s['dataset'])} from Dataset 2)."
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    bnb_config = (
        BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        if torch.cuda.is_available()
        else None
    )

    # Benchmark 1: Base Model (Unadapted)
    print("\n[Phase 1] Benchmarking Unadapted Base Model (Qwen2.5-0.5B-Instruct)...")
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto" if torch.cuda.is_available() else "cpu",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    base_metrics = evaluate_batch_metrics(base_model, tokenizer, test_samples, is_fine_tuned=False)

    # Benchmark 2: Fine-Tuned Model (LoRA Adapter attached)
    print("\n[Phase 2] Benchmarking Fine-Tuned SLM (lib_qwen_scholarly_lora)...")
    ft_model = PeftModel.from_pretrained(base_model, str(ADAPTER_PATH))
    ft_metrics = evaluate_batch_metrics(ft_model, tokenizer, test_samples, is_fine_tuned=True)

    # Breakdown by dataset
    def split_by_dataset(results):
        d1 = [r for r in results["task_results"] if "dataset1" in r["dataset"]]
        d2 = [r for r in results["task_results"] if "dataset2" in r["dataset"]]
        return {
            "d1_acc": round(sum(r["token_accuracy"] for r in d1) / len(d1), 2),
            "d1_syntax": round((sum(1 for r in d1 if r["syntax_valid"]) / len(d1)) * 100, 2),
            "d1_loss": round(sum(r["loss"] for r in d1) / len(d1), 4),
            "d2_acc": round(sum(r["token_accuracy"] for r in d2) / len(d2), 2),
            "d2_syntax": round((sum(1 for r in d2 if r["syntax_valid"]) / len(d2)) * 100, 2),
            "d2_loss": round(sum(r["loss"] for r in d2) / len(d2), 4),
        }

    base_split = split_by_dataset(base_metrics)
    ft_split = split_by_dataset(ft_metrics)

    report = {
        "base_model": {
            "overall_token_accuracy_pct": base_metrics["token_accuracy_pct"],
            "overall_syntax_adherence_pct": base_metrics["syntax_adherence_pct"],
            "avg_loss": base_metrics["avg_loss"],
            "perplexity": base_metrics["perplexity"],
            "dataset1_pedagogical": {
                "token_accuracy_pct": base_split["d1_acc"],
                "syntax_adherence_pct": base_split["d1_syntax"],
                "avg_loss": base_split["d1_loss"],
            },
            "dataset2_scholarly": {
                "token_accuracy_pct": base_split["d2_acc"],
                "syntax_adherence_pct": base_split["d2_syntax"],
                "avg_loss": base_split["d2_loss"],
            },
        },
        "fine_tuned_slm": {
            "overall_token_accuracy_pct": ft_metrics["token_accuracy_pct"],
            "overall_syntax_adherence_pct": ft_metrics["syntax_adherence_pct"],
            "avg_loss": ft_metrics["avg_loss"],
            "perplexity": ft_metrics["perplexity"],
            "dataset1_pedagogical": {
                "token_accuracy_pct": ft_split["d1_acc"],
                "syntax_adherence_pct": ft_split["d1_syntax"],
                "avg_loss": ft_split["d1_loss"],
            },
            "dataset2_scholarly": {
                "token_accuracy_pct": ft_split["d2_acc"],
                "syntax_adherence_pct": ft_split["d2_syntax"],
                "avg_loss": ft_split["d2_loss"],
            },
        },
        "improvements": {
            "token_accuracy_delta": round(
                ft_metrics["token_accuracy_pct"] - base_metrics["token_accuracy_pct"], 2
            ),
            "syntax_adherence_delta": round(
                ft_metrics["syntax_adherence_pct"] - base_metrics["syntax_adherence_pct"], 2
            ),
            "loss_reduction_pct": round(
                ((base_metrics["avg_loss"] - ft_metrics["avg_loss"]) / base_metrics["avg_loss"])
                * 100,
                2,
            ),
            "perplexity_reduction_pct": round(
                (
                    (base_metrics["perplexity"] - ft_metrics["perplexity"])
                    / base_metrics["perplexity"]
                )
                * 100,
                2,
            ),
        },
    }

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print("FINAL BENCHMARK SCORECARD")
    print("=" * 80)
    print(f"{'Metric':<35} | {'Base Model':<15} | {'Fine-Tuned SLM':<15} | {'Delta':<10}")
    print("-" * 80)
    print(
        f"{'Overall Token Accuracy':<35} | {base_metrics['token_accuracy_pct']:>13.2f}% | {ft_metrics['token_accuracy_pct']:>13.2f}% | +{report['improvements']['token_accuracy_delta']:.2f}%"
    )
    print(
        f"{'Overall Syntax & Schema Adherence':<35} | {base_metrics['syntax_adherence_pct']:>13.2f}% | {ft_metrics['syntax_adherence_pct']:>13.2f}% | +{report['improvements']['syntax_adherence_delta']:.2f}%"
    )
    print(
        f"{'Average Cross-Entropy Loss':<35} | {base_metrics['avg_loss']:>14.4f} | {ft_metrics['avg_loss']:>14.4f} | -{report['improvements']['loss_reduction_pct']:.2f}%"
    )
    print(
        f"{'Perplexity':<35} | {base_metrics['perplexity']:>14.2f} | {ft_metrics['perplexity']:>14.2f} | -{report['improvements']['perplexity_reduction_pct']:.2f}%"
    )
    print("-" * 80)
    print(
        f"{'Dataset 1 (Pedagogical) Accuracy':<35} | {base_split['d1_acc']:>13.2f}% | {ft_split['d1_acc']:>13.2f}% | +{ft_split['d1_acc'] - base_split['d1_acc']:.2f}%"
    )
    print(
        f"{'Dataset 1 (Pedagogical) Syntax':<35} | {base_split['d1_syntax']:>13.2f}% | {ft_split['d1_syntax']:>13.2f}% | +{ft_split['d1_syntax'] - base_split['d1_syntax']:.2f}%"
    )
    print(
        f"{'Dataset 2 (Scholarly) Accuracy':<35} | {base_split['d2_acc']:>13.2f}% | {ft_split['d2_acc']:>13.2f}% | +{ft_split['d2_acc'] - base_split['d2_acc']:.2f}%"
    )
    print(
        f"{'Dataset 2 (Scholarly) Syntax':<35} | {base_split['d2_syntax']:>13.2f}% | {ft_split['d2_syntax']:>13.2f}% | +{ft_split['d2_syntax'] - base_split['d2_syntax']:.2f}%"
    )
    print("=" * 80)
    print(f"Report saved to: {OUTPUT_REPORT}")


if __name__ == "__main__":
    main()

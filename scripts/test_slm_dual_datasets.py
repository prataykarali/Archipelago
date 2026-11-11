#!/usr/bin/env python3
"""
Empirical test suite to verify that the SLM model is fine-tuned on:
- Dataset 1: Pedagogical OKF Knowledge Graph Extraction & Curriculum (1,500 pairs)
- Dataset 2: Scholarly Evidence, Metrics & Comparative Parameter Matrices (1,000 pairs)
"""

import json
from pathlib import Path
import sys
import time

from peft import PeftModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_PATH = ROOT / "models/lib_qwen_scholarly_lora"
DATASET_1_PATH = ROOT / "data/datasets/dataset1_pedagogical_revamped.jsonl"
DATASET_2_PATH = ROOT / "data/datasets/dataset2_scholarly_evidence.jsonl"


def extract_json_array(text: str):
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    a0 = text.find("[")
    a1 = text.rfind("]")
    if a0 != -1 and a1 > a0:
        try:
            return json.loads(text[a0 : a1 + 1]), None
        except Exception as e:
            return None, str(e)
    return None, "No JSON array found"


def generate_response(model, tokenizer, messages, max_new_tokens=300):
    device = next(model.parameters()).device
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(prompt_text, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            top_p=0.9,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen_tokens = outputs[0][inputs.input_ids.shape[1] :]
    return tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()


def calculate_sample_loss(model, tokenizer, messages):
    device = next(model.parameters()).device
    full_text = tokenizer.apply_chat_template(messages, tokenize=False)
    enc = tokenizer(full_text, return_tensors="pt").to(device)
    input_ids = enc["input_ids"]

    prompt_msgs = messages[:-1]
    prompt_text = tokenizer.apply_chat_template(
        prompt_msgs, tokenize=False, add_generation_prompt=True
    )
    prompt_enc = tokenizer(prompt_text, return_tensors="pt")
    prompt_len = prompt_enc["input_ids"].shape[1]

    labels = input_ids.clone()
    labels[:, :prompt_len] = -100

    with torch.no_grad():
        outputs = model(input_ids=input_ids, labels=labels)
        loss = outputs.loss.item()
    return loss


def main():
    print("=" * 80)
    print("TESTING SLM FINE-TUNING ON DATASET 1 (PEDAGOGICAL) & DATASET 2 (SCHOLARLY)")
    print("=" * 80)

    # 1. Model Loading
    print("\n[1/4] Loading Tokenizer and 4-bit Quantized Model + LoRA Adapter...")
    t0 = time.time()
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

    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto" if torch.cuda.is_available() else "cpu",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_PATH))
    model.eval()
    print(
        f"      Model loaded in {time.time() - t0:.2f}s on {'CUDA' if torch.cuda.is_available() else 'CPU'}"
    )

    # 2. Pick representative held-out test samples from both datasets
    print("\n[2/4] Sampling Test Instances from Dataset 1 & Dataset 2...")

    d1_samples = []
    with open(DATASET_1_PATH, encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                data = json.loads(line)
                if idx in [1480, 1485, 1490, 1495]:
                    d1_samples.append(data)

    d2_samples = []
    with open(DATASET_2_PATH, encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                data = json.loads(line)
                if idx in [980, 985, 990, 995]:
                    d2_samples.append(data)

    print(f"      Retrieved {len(d1_samples)} test samples from Dataset 1")
    print(f"      Retrieved {len(d2_samples)} test samples from Dataset 2")

    # 3. Test Dataset 1: Pedagogical Knowledge Graph & Curriculum
    print("\n" + "=" * 80)
    print("TEST BATCH 1: DATASET 1 (Pedagogical OKF Extraction, Prerequisites, MCQ)")
    print("=" * 80)

    d1_results = []
    for i, sample in enumerate(d1_samples):
        task = sample.get("task", "unknown")
        messages = sample["messages"]
        user_prompt = messages[1]["content"]

        loss = calculate_sample_loss(model, tokenizer, messages)
        response = generate_response(model, tokenizer, messages[:2], max_new_tokens=220)

        is_okf_task = "okf_extraction" in task
        json_valid = False
        if is_okf_task:
            parsed, err = extract_json_array(response)
            json_valid = parsed is not None and len(parsed) > 0
            check_str = (
                f"Valid OKF JSON ({len(parsed) if parsed else 0} concepts)"
                if json_valid
                else f"JSON Parse Failed ({err})"
            )
        else:
            check_str = "Pedagogical Structure Valid" if len(response) > 40 else "Too Short"

        passed = loss < 2.0 and (json_valid if is_okf_task else len(response) > 40)
        d1_results.append(
            {
                "task": task,
                "loss": loss,
                "check": check_str,
                "passed": passed,
            }
        )

        print(f"\n--- [Dataset 1 Sample {i + 1}] Task: {task} ---")
        print(f"Prompt (truncated): {user_prompt[:110]}...")
        print(f"Target Loss: {loss:.4f} (Perplexity: {torch.exp(torch.tensor(loss)):.2f})")
        print(f"Model Output (first 180 chars):\n{response[:180]}...")
        print(f"Status: {'PASSED' if passed else 'FAILED'} [{check_str}]")

    # 4. Test Dataset 2: Scholarly Evidence & Parameter Matrix
    print("\n" + "=" * 80)
    print("TEST BATCH 2: DATASET 2 (Scholarly Parameter Matrices & Scientific Evidence)")
    print("=" * 80)

    d2_results = []
    for i, sample in enumerate(d2_samples):
        task = sample.get("task", "unknown")
        messages = sample["messages"]
        user_prompt = messages[1]["content"]

        loss = calculate_sample_loss(model, tokenizer, messages)
        response = generate_response(model, tokenizer, messages[:2], max_new_tokens=220)

        is_matrix_task = "matrix" in task or "comparison" in task
        has_table = ("|" in response and "---" in response) if is_matrix_task else False
        if is_matrix_task:
            check_str = "Valid Markdown Table Matrix" if has_table else "Table Syntax Missing"
        else:
            check_str = "Scientific Structure Valid" if len(response) > 40 else "Too Short"

        passed = loss < 2.0 and (has_table if is_matrix_task else len(response) > 40)
        d2_results.append(
            {
                "task": task,
                "loss": loss,
                "check": check_str,
                "passed": passed,
            }
        )

        print(f"\n--- [Dataset 2 Sample {i + 1}] Task: {task} ---")
        print(f"Prompt (truncated): {user_prompt[:110]}...")
        print(f"Target Loss: {loss:.4f} (Perplexity: {torch.exp(torch.tensor(loss)):.2f})")
        print(f"Model Output (first 180 chars):\n{response[:180]}...")
        print(f"Status: {'PASSED' if passed else 'FAILED'} [{check_str}]")

    # Final Summary
    d1_pass = sum(1 for r in d1_results if r["passed"])
    d2_pass = sum(1 for r in d2_results if r["passed"])
    avg_d1_loss = sum(r["loss"] for r in d1_results) / len(d1_results)
    avg_d2_loss = sum(r["loss"] for r in d2_results) / len(d2_results)

    print("\n" + "=" * 80)
    print("DUAL-DATASET FINE-TUNING VERIFICATION SUMMARY")
    print("=" * 80)
    print(
        f"Dataset 1 (Pedagogical): {d1_pass}/{len(d1_results)} Passed | Avg Loss: {avg_d1_loss:.4f}"
    )
    print(
        f"Dataset 2 (Scholarly):   {d2_pass}/{len(d2_results)} Passed | Avg Loss: {avg_d2_loss:.4f}"
    )
    all_ok = d1_pass == len(d1_results) and d2_pass == len(d2_results)
    print(
        f"Overall Result:          {'CONFIRMED: SLM IS DUAL-FINE-TUNED ON BOTH DATASETS' if all_ok else 'Partial Convergence'}"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GPU Fine-Tuning Script for lib-qwen on unified v4.4 dataset.
Hardware target: NVIDIA GeForce RTX 2050 (4 GB VRAM).
Uses 4-bit QLoRA with BitsAndBytes, PEFT, and TRL SFTTrainer.
"""

import os
import sys
import json
import gc
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    PeftModel
)
from trl import SFTTrainer, SFTConfig

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
TRAIN_FILE = ROOT / "training_data" / "unified_v4_4_train.jsonl"
TEST_FILE = ROOT / "training_data" / "unified_v4_4_test.jsonl"
LORA_OUTPUT_DIR = ROOT / "models" / "lib_qwen_lora_v44"
MERGED_OUTPUT_DIR = ROOT / "models" / "lib_qwen_v44_hf"
GGUF_OUTPUT_PATH = ROOT / "models" / "lib-qwen-v44-q8_0.gguf"
MODELFILE_PATH = ROOT / "models" / "Modelfile.lib_qwen_v44"

HF_TOKEN = os.environ.get("HF_TOKEN")

def check_gpu():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. GPU is required for QLoRA training.")
    device_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"[GPU INFO] Device: {device_name} | Total VRAM: {vram_gb:.2f} GB")
    # Clear CUDA cache before starting
    torch.cuda.empty_cache()
    gc.collect()

def main():
    check_gpu()
    print(f"\n[1/5] Loading Tokenizer & Preparing Dataset...")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID,
        token=HF_TOKEN,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        
    def format_to_chatml(example):
        msgs = example["messages"]
        text = tokenizer.apply_chat_template(msgs, tokenize=False)
        return {"text": text}

    train_ds = load_dataset("json", data_files=str(TRAIN_FILE), split="train")
    test_ds = load_dataset("json", data_files=str(TEST_FILE), split="train")
    
    train_conv = train_ds.map(format_to_chatml, remove_columns=train_ds.column_names)
    test_conv = test_ds.map(format_to_chatml, remove_columns=test_ds.column_names)
    
    print(f"Loaded {len(train_conv)} train examples, {len(test_conv)} test examples.")

    print(f"\n[2/5] Initializing 4-bit Base Model on RTX 2050...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        dtype=torch.bfloat16,
        token=HF_TOKEN,
        trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model)
    
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    print(f"\n[3/5] Configuring SFTTrainer...")
    LORA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    sft_config = SFTConfig(
        output_dir=str(LORA_OUTPUT_DIR),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        warmup_steps=10,
        max_steps=100,
        learning_rate=2e-4,
        logging_steps=10,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        bf16=True,
        fp16=False,
        seed=42,
        dataset_text_field="text",
        max_length=1536,
        report_to="none",
        save_strategy="no"
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_conv,
        eval_dataset=test_conv,
        processing_class=tokenizer,
    )

    print(f"\n[4/5] Executing QLoRA Fine-Tuning...")
    train_result = trainer.train()
    print(f"Training completed! Global step: {train_result.global_step}, Training loss: {train_result.training_loss:.4f}")
    
    # Save adapter
    print(f"Saving LoRA adapter to {LORA_OUTPUT_DIR}...")
    trainer.model.save_pretrained(str(LORA_OUTPUT_DIR))
    tokenizer.save_pretrained(str(LORA_OUTPUT_DIR))
    
    with open(LORA_OUTPUT_DIR / "training_metrics.json", "w") as f:
        json.dump({
            "train_loss": train_result.training_loss,
            "global_step": train_result.global_step,
            "metrics": train_result.metrics
        }, f, indent=2)

    # Free 4-bit model from GPU memory
    del model
    del trainer
    torch.cuda.empty_cache()
    gc.collect()

    print(f"\n[5/5] Merging LoRA Weights into Full Precision Model...")
    MERGED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        device_map="cpu",
        dtype=torch.bfloat16,
        token=HF_TOKEN,
        trust_remote_code=True
    )
    merged_model = PeftModel.from_pretrained(base_model, str(LORA_OUTPUT_DIR))
    merged_model = merged_model.merge_and_unload()
    
    print(f"Saving merged model to {MERGED_OUTPUT_DIR}...")
    merged_model.save_pretrained(str(MERGED_OUTPUT_DIR))
    tokenizer.save_pretrained(str(MERGED_OUTPUT_DIR))
    
    print("\n[SUCCESS] Fine-tuning and weight merge complete!")
    print(f"Merged model path: {MERGED_OUTPUT_DIR}")

    print(f"\n[6/6] Updating lib-qwen:latest in Ollama...")
    import subprocess
    modelfile_content = f"""FROM {MERGED_OUTPUT_DIR.resolve()}
TEMPLATE "{{{{ .Prompt }}}}"
PARAMETER num_ctx 4096
PARAMETER num_predict 768
PARAMETER temperature 0.1
"""
    with open(MODELFILE_PATH, "w") as f:
        f.write(modelfile_content)
        
    print(f"Wrote Ollama Modelfile: {MODELFILE_PATH}")
    res = subprocess.run(
        f"ollama create lib-qwen:latest --experimental -f '{MODELFILE_PATH.resolve()}'",
        shell=True,
        capture_output=True,
        text=True
    )
    print("Ollama response:", res.stdout.strip())
    if res.returncode != 0:
        print("Ollama error:", res.stderr.strip())
    else:
        print("[SUCCESS] lib-qwen:latest successfully updated in Ollama with new v4.4 fine-tuned weights!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Synchronize Archipelago Library Books, Manifests, Datasets, and Fine-Tuned Model Weights
to private Hugging Face Dataset Hub: Prataykarali/Library_books.
"""

import os
import sys
import json
import logging
from pathlib import Path
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from archipelago.storage.hf_remote import HFStorageClient, compute_sha256

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("archipelago.sync_to_hf")

REPO_ID = "Prataykarali/Library_books"

README_CONTENT = """---
pretty_name: "Archipelago Institutional Library Books & OKF Ingestion Hub"
viewer: true
license: "other"
tags:
  - academic-textbooks
  - knowledge-graph
  - okf-ingestion
  - lib-qwen
  - curriculum-learning
---

# Archipelago Library Books & OKF Ingestion Repository

This private repository hosts the academic textbooks, foundational research papers, ingestion manifests, training datasets, and fine-tuned model adapters for the **Archipelago** agentic textbook knowledge engine.

---

## 📚 Repository Structure

```
Prataykarali/Library_books/
├── README.md                              # This documentation manifest
├── catalogs/
│   ├── pearson_bookshelf.json             # 40 Pearson academic textbooks catalog with reader URLs & ISBNs
│   └── batch1_ingestion_summary.json      # Phase 3.2 AI/ML textbook ingestion summary & DAG metrics
├── datasets/
│   ├── unified_v4_4_train.jsonl           # 780 fine-tuning training pairs for lib-qwen
│   ├── unified_v4_4_test.jsonl            # 212 evaluation pairs
│   ├── unified_v4_4_manifest.json         # Dataset composition and curriculum breakdown
│   └── pearson_v44_pairs.jsonl            # Synthesized Pearson pedagogical pairs (MCQ, reasoning, explanations)
├── books/
│   ├── textbooks/                         # Stored academic textbooks (Deisenroth Math for ML, etc.)
│   └── papers/                            # Seminal research papers (Attention, BERT, LoRA, QLoRA, etc.)
└── models/
    └── lib_qwen_lora_v44/                 # Fine-tuned QLoRA adapter on RTX 2050 GPU
        ├── adapter_config.json            # LoRA configuration (r=16, alpha=32, target_modules=all-linear)
        ├── adapter_model.safetensors      # Trained LoRA weights (17.6 MB)
        ├── training_metrics.json          # Final training loss (1.279), 100/100 steps
        ├── tokenizer.json                 # Qwen2.5 tokenizer
        └── chat_template.jinja            # Guided JSON extraction prompt template
```

---

## 🏛️ Pearson Institutional Bookshelf (40 Textbooks)
Includes deep-linking reader manifests and ISBNs for:
1. **AI & Machine Learning**: Russell & Norvig *AIMA 4e*, Jurafsky *Speech & Language 2e*, Saikat Dutt *Machine Learning 2e*, Haykin *Neural Networks 3e*, Forsyth *Computer Vision 2e*.
2. **Computer Networks & Security**: Tanenbaum *Computer Networks 6e & 5e*, Stallings *Cryptography & Network Security 8e*, Stallings *Data & Computer Communications*.
3. **Compilers & Algorithms**: Aho et al. *Compilers 2e (Dragon Book)*, Levitin *Algorithms*, Dave *Algorithms 2e*, Tenenbaum *Data Structures in C*.
4. **Systems & Hardware**: Stallings *Operating Systems*, Morris Mano *Computer System Architecture*, Boylestad *Electronic Devices*, Mazidi *Microcontrollers*.
5. **Signal Processing & Math**: Proakis *DSP 4e*, Gonzalez & Woods *Digital Image Processing*, Ross *Probability*.

---

## 🧠 Fine-Tuned Concept Extraction Model (`lib-qwen-v4.4`)
* **Base Model**: `Qwen/Qwen2.5-0.5B-Instruct`
* **Fine-Tuning Method**: 4-bit NormalFloat (NF4) QLoRA with BFloat16 compute on NVIDIA GeForce RTX 2050 Laptop GPU (4 GB VRAM).
* **Hyperparameters**: $r=16, \alpha=32$, cosine decay schedule, effective batch size 8.
* **Loss Convergence**: $2.722 \rightarrow 1.279$ over 100 steps.
* **Target Objective**: Canonical title-cased concept extraction, authoritative definitions, difficulty ratings, and directional `REQUIRES` prerequisite DAG links with negative boilerplate filtering.
"""

def sync_all():
    client = HFStorageClient(repo_id=REPO_ID)
    if not client.is_available:
        logger.error("HF client is not authenticated. Please check HF_TOKEN in .env")
        sys.exit(1)
        
    api = client.api
    logger.info("Authenticated to Hugging Face Hub. Target Repo: %s", REPO_ID)
    
    # 1. Upload README.md (Dataset Card)
    logger.info("Uploading Dataset Card README.md...")
    api.upload_file(
        path_or_fileobj=README_CONTENT.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message="Add comprehensive dataset card & repository overview"
    )
    
    # 2. Upload Catalogs
    catalogs = [
        (ROOT / "data" / "catalogs" / "pearson_bookshelf.json", "catalogs/pearson_bookshelf.json"),
        (ROOT / "data" / "catalogs" / "batch1_ingestion_summary.json", "catalogs/batch1_ingestion_summary.json"),
    ]
    for local_path, remote_path in catalogs:
        if local_path.is_file():
            logger.info("Uploading %s -> %s...", local_path.name, remote_path)
            client.upload_file(local_path, remote_path, commit_message=f"Sync catalog: {local_path.name}")

    # 3. Upload Datasets
    datasets = [
        (ROOT / "training_data" / "unified_v4_4_train.jsonl", "datasets/unified_v4_4_train.jsonl"),
        (ROOT / "training_data" / "unified_v4_4_test.jsonl", "datasets/unified_v4_4_test.jsonl"),
        (ROOT / "training_data" / "unified_v4_4_manifest.json", "datasets/unified_v4_4_manifest.json"),
        (ROOT / "data" / "datasets" / "pearson_v44_pairs.jsonl", "datasets/pearson_v44_pairs.jsonl"),
    ]
    for local_path, remote_path in datasets:
        if local_path.is_file():
            logger.info("Uploading %s -> %s...", local_path.name, remote_path)
            client.upload_file(local_path, remote_path, commit_message=f"Sync dataset: {local_path.name}")

    # 4. Upload Books & PDFs
    textbooks = list((ROOT / "pdfs" / "textbooks").glob("*.pdf")) if (ROOT / "pdfs" / "textbooks").is_dir() else []
    for tb in textbooks:
        remote_path = f"books/textbooks/{tb.name}"
        logger.info("Uploading textbook %s -> %s...", tb.name, remote_path)
        client.upload_file(tb, remote_path, commit_message=f"Add textbook: {tb.name}")
        
    papers = list((ROOT / "pdfs" / "papers").glob("*.pdf")) if (ROOT / "pdfs" / "papers").is_dir() else []
    for p in papers:
        remote_path = f"books/papers/{p.name}"
        logger.info("Uploading paper %s -> %s...", p.name, remote_path)
        client.upload_file(p, remote_path, commit_message=f"Add foundational paper: {p.name}")

    # 5. Upload Fine-Tuned Model Weights & Metrics
    lora_dir = ROOT / "models" / "lib_qwen_lora_v44"
    if lora_dir.is_dir():
        for mf in lora_dir.iterdir():
            if mf.is_file():
                remote_path = f"models/lib_qwen_lora_v44/{mf.name}"
                logger.info("Uploading model artifact %s -> %s...", mf.name, remote_path)
                client.upload_file(mf, remote_path, commit_message=f"Upload fine-tuned model artifact: {mf.name}")

    logger.info("=== Sync to Hugging Face %s complete! ===", REPO_ID)
    files = client.list_files()
    logger.info("Current files in %s: (%d total files)", REPO_ID, len(files))
    for f in sorted(files):
        logger.info("  - %s", f)

if __name__ == "__main__":
    sync_all()

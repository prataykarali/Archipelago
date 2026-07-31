#!/usr/bin/env python3
"""
Upload local `lib-qwen` model (1.5 GB) to Hugging Face Hub.

Run this ONCE to store your exact fine-tuned model in a free HF model repository.
Once uploaded, any free Cloud GPU (Google Colab, Modal, Kaggle, HF Spaces) can
automatically download and serve your model without manual file uploads!

Usage:
  python scripts/upload_model_hf.py --repo-id username/lib-qwen-v5 --token hf_...
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "lib-qwen"
if not MODEL_DIR.exists():
    MODEL_DIR = REPO_ROOT.parent / "lib-qwen"
if not MODEL_DIR.exists():
    MODEL_DIR = REPO_ROOT.parent / "aura-qwen"

def main():
    parser = argparse.ArgumentParser(description="Upload lib-qwen model to Hugging Face Hub")
    parser.add_argument("--repo-id", type=str, required=True, help="HF repo ID (e.g. username/lib-qwen-v5)")
    parser.add_argument("--token", type=str, required=True, help="Hugging Face User Access Token (write permission)")
    parser.add_argument("--private", action="store_true", help="Make repository private")
    args = parser.parse_args()

    if not MODEL_DIR.exists():
        print(f"❌ Error: Model directory not found at {MODEL_DIR}")
        sys.exit(1)

    print(f"📦 Preparing to upload `{MODEL_DIR.name}` (1.5 GB) to Hugging Face Hub: {args.repo_id}")

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("❌ Error: `huggingface_hub` package not found. Install via: pip install huggingface_hub")
        sys.exit(1)

    api = HfApi(token=args.token)
    
    print("  1. Creating repository on Hugging Face Hub...")
    try:
        create_repo(repo_id=args.repo_id, token=args.token, private=args.private, exist_ok=True)
        print("  ✓ Repository ready!")
    except Exception as exc:
        print(f"  ⚠️ Note: {exc}")

    print("  2. Uploading model files (safetensors, tokenizer, configs)...")
    api.upload_folder(
        folder_path=str(MODEL_DIR),
        repo_id=args.repo_id,
        repo_type="model",
    )

    print(f"\n🎉 SUCCESS! Your exact fine-tuned model is now hosted on Hugging Face Hub:")
    print(f"   👉 https://huggingface.co/{args.repo_id}\n")
    print(f"Any Cloud GPU script can now automatically pull this model using repo ID: `{args.repo_id}`!")

if __name__ == "__main__":
    main()

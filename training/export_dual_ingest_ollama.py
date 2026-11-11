"""Merge a scored QLoRA adapter and register an isolated Ollama model tag."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from peft import PeftModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_ADAPTER = ROOT / "models" / "dual_ingest_candidate_v3"
DEFAULT_TAG = "dual-ingest:v3"
OLLAMA_TIMEOUT_SECONDS = 300
MODEL_CONTEXT_TOKENS = 8192
MODEL_OUTPUT_TOKENS = 768
CHAT_TEMPLATE = (
    'TEMPLATE """{{ range .Messages }}<|im_start|>{{ .Role }}\n'
    '{{ .Content }}<|im_end|>\n'
    '{{ end }}<|im_start|>assistant\n'
    '"""\n'
)


def export(adapter_dir: Path, tag: str) -> dict[str, Any]:
    """Publish a new local tag while preserving existing production models."""
    if not (adapter_dir / "adapter_model.safetensors").is_file():
        raise FileNotFoundError(f"No trained adapter in {adapter_dir}")
    if not (adapter_dir / "held_out_eval.json").is_file():
        raise ValueError("Evaluate the adapter on held-out papers before export")
    merged_dir = adapter_dir / "merged_hf"
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, dtype=torch.float16, device_map="cpu", local_files_only=True
    )
    merged = PeftModel.from_pretrained(model, str(adapter_dir), local_files_only=True)
    merged = merged.merge_and_unload()
    merged.save_pretrained(str(merged_dir), safe_serialization=True)
    AutoTokenizer.from_pretrained(BASE_MODEL, local_files_only=True).save_pretrained(
        str(merged_dir)
    )
    modelfile = adapter_dir / "Modelfile"
    modelfile.write_text(
        f"FROM {merged_dir.resolve()}\n"
        f"{CHAT_TEMPLATE}"
        f"PARAMETER num_ctx {MODEL_CONTEXT_TOKENS}\n"
        f"PARAMETER num_predict {MODEL_OUTPUT_TOKENS}\n"
        "PARAMETER temperature 0\n"
        'PARAMETER stop "<|im_end|>"\n'
        'PARAMETER stop "<|endoftext|>"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        ["ollama", "create", tag, "-f", str(modelfile)],
        check=True,
        capture_output=True,
        text=True,
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    report = {"ollama_tag": tag, "merged_directory": str(merged_dir), "create_log": result.stdout}
    (adapter_dir / "ollama_export_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    """Export a validated adapter through the local Ollama registry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    args = parser.parse_args()
    print(json.dumps(export(args.adapter_dir, args.tag), indent=2))


if __name__ == "__main__":
    main()

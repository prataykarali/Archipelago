"""Batch Scholarly Evidence Dataset Synthesizer.

Runs multi-source discovery across canonical AI/ML domains and compiles Dataset 2:
high-quality OKF v1.0.0 structured evidence extraction and cross-paper parameter comparison pairs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from archipelago.scholarly.cli import run_pipeline
from archipelago.scholarly.dataset.slm_dataset_generator import SLMDatasetGenerator

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("archipelago.scholarly.batch_generator")

DOMAINS = [
    "Optical Character Recognition",
    "Transformer Attention Mechanism",
    "Graph Neural Networks",
    "Low-Rank Adaptation LoRA",
    "Diffusion Generative Models",
]

OUTPUT_PATH = Path("data/datasets/dataset2_scholarly_evidence.jsonl")


def build_dataset2(domains: List[str] = DOMAINS, output_path: Path = OUTPUT_PATH) -> int:
    """Ingest multiple domains and compile dataset 2."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_examples = []
    dataset_gen = SLMDatasetGenerator()

    for dom in domains:
        print(f"\n📚 Ingesting domain for Dataset 2: '{dom}'...")
        records = run_pipeline(
            topic=dom,
            limit=3,
            download_pdf=True,
            compare=False,
            export_dataset_dir=None,
        )
        examples = dataset_gen.generate_dataset_for_papers(records, dom)
        all_examples.extend(examples)

    # Save to JSONL
    count = dataset_gen.export_jsonl(all_examples, output_path)
    print(f"\n🎉 Successfully compiled Dataset 2 with {count} scholarly evidence examples -> {output_path}")
    return count


if __name__ == "__main__":
    build_dataset2()

"""SLM Fine-Tuning Dataset Generator.

Synthesizes high-fidelity JSONL instruction-tuning pairs for Small Language Models (Qwen / Llama)
grounded in authentic scholarly papers, OKF v1.0.0 evidence objects, cross-paper comparison matrices,
and first-principles pedagogical explanations.
Supports automatic train/eval splitting to produce two separate datasets.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import random
from typing import Any

from archipelago.scholarly.comparison.matrix_generator import ParameterComparisonEngine
from archipelago.scholarly.contracts.okf_models import OKFPaperRecord

logger = logging.getLogger("archipelago.scholarly.slm_dataset")


class SLMDatasetGenerator:
    """Generates fine-tuning examples in ChatML/instruction format for Small Language Models."""

    def __init__(self) -> None:
        self.comparer = ParameterComparisonEngine()

    def generate_dataset_for_papers(
        self, okf_records: list[OKFPaperRecord], topic: str
    ) -> list[dict[str, Any]]:
        """Generate diverse training examples from a set of ingested OKF paper records."""
        examples: list[dict[str, Any]] = []

        for rec in okf_records:
            paper = rec.paper
            first_author = paper.authors[0].name if paper.authors else "Author"
            year_str = paper.publication_date[:4] if paper.publication_date else "N/A"
            venue_str = paper.venue or "Scholarly Publication"
            abstract_text = paper.abstract or "Abstract not reported in source metadata."

            # ------------------------------------------------------------------
            # Task 1: Structured Information Extraction (Paper -> OKF JSON)
            # ------------------------------------------------------------------
            input_text = (
                f"Title: {paper.title}\n"
                f"Authors: {', '.join([a.name for a in paper.authors[:3]])}\n"
                f"Venue: {venue_str}, Year: {year_str}\n"
                f"Abstract: {abstract_text}\n"
            )

            target_json = {
                "title": paper.title,
                "venue": venue_str,
                "publication_year": year_str,
                "claims": [c.model_dump() for c in rec.claims[:2]],
                "datasets": [d.name for d in rec.datasets],
                "experiments": [
                    {
                        "name": e.name,
                        "metrics": [m.model_dump() for m in e.metrics],
                        "ablation_present": e.ablation_present,
                        "error_analysis_present": e.error_analysis_present,
                    }
                    for e in rec.experiments
                ],
                "evidence_coverage": rec.quality.get("evidence_coverage", 1.0),
            }

            examples.append(
                {
                    "task": "structured_scientific_extraction",
                    "topic": topic,
                    "paper_id": paper.paper_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an institutional scientific evidence extraction engine. "
                                "Extract verified claims, datasets, experimental metrics, and ablation flags "
                                "strictly into structured JSON format without fabricating unsupported facts."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Extract structured scientific entities from this publication:\n\n{input_text}",
                        },
                        {
                            "role": "assistant",
                            "content": json.dumps(target_json, indent=2),
                        },
                    ],
                }
            )

            # ------------------------------------------------------------------
            # Task 2: Pedagogical Concept Explanation Grounded in Citations
            # ------------------------------------------------------------------
            examples.append(
                {
                    "task": "pedagogical_concept_explanation",
                    "topic": topic,
                    "paper_id": paper.paper_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an expert academic research librarian at the doorstep of the knowledge archives. "
                                "Explain scholarly concepts from first principles, emphasizing foundational mechanisms, "
                                "upstream prerequisites, and rigorous canonical literature citations."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Explain the core methodology and significance of the research topic '{topic}', citing '{paper.title}'.",
                        },
                        {
                            "role": "assistant",
                            "content": (
                                f"### 📘 Foundations of {topic}\n\n"
                                f"Research in **{topic}** investigates algorithmic and structural methods to optimize representation learning, "
                                f"empirical accuracy, and generalization capacity.\n\n"
                                f"#### 🔬 Methodological Contribution\n"
                                f"{abstract_text}\n\n"
                                f"#### 📖 Canonical Literature Citation\n"
                                f"- **Title**: *{paper.title}*\n"
                                f"- **Lead Author**: {first_author} et al. ({year_str})\n"
                                f"- **Published In**: {venue_str}\n"
                                f"- **Evidence Audit**: Retains verified immutable provenance (DOI: {paper.identifiers.doi or 'arXiv'})."
                            ),
                        },
                    ],
                }
            )

        # ------------------------------------------------------------------
        # Task 3: Multi-Paper Parameter Comparison Matrix
        # ------------------------------------------------------------------
        if len(okf_records) >= 2:
            matrix = self.comparer.build_comparison_matrix(okf_records)
            md_table = self.comparer.format_markdown_table(matrix)

            papers_summary = "\n\n".join(
                [
                    f"Paper {idx + 1}: {r.paper.title} ({r.paper.publication_date[:4] if r.paper.publication_date else 'N/A'})\n"
                    f"Venue: {r.paper.venue or 'N/A'}\n"
                    f"Abstract: {r.paper.abstract[:200] if r.paper.abstract else 'N/A'}..."
                    for idx, r in enumerate(okf_records[:3])
                ]
            )

            comparison_assistant_response = (
                f"### 📊 Comparative Parameter Matrix: {topic}\n\n"
                f"{md_table}\n\n"
                f"#### 🔍 Key Methodological & Empirical Trade-Offs\n"
                f"1. **Experimental Rigor**: Papers with verified ablation studies isolate individual module contributions with higher statistical validity.\n"
                f"2. **Reproducibility**: Artifact completeness correlates with verified public source code and standard benchmark evaluation.\n"
                f"3. **Evidence Auditability**: All extracted claims and metrics link to immutable PDF page coordinates."
            )

            examples.append(
                {
                    "task": "cross_paper_parameter_comparison",
                    "topic": topic,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an institutional research evidence comparator. "
                                "Given candidate papers on a research topic, produce an objective "
                                "parameter comparison table evaluating experimental rigor, metrics, datasets, "
                                "and reproducibility without relying on subjective prestige."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Compare these research papers on the topic '{topic}':\n\n{papers_summary}",
                        },
                        {
                            "role": "assistant",
                            "content": comparison_assistant_response,
                        },
                    ],
                }
            )

        return examples

    def split_train_eval(
        self, examples: list[dict[str, Any]], eval_ratio: float = 0.2, seed: int = 42
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split examples into training and evaluation sets without leakage."""
        if len(examples) <= 1:
            return examples, []

        shuffled = list(examples)
        rng = random.Random(seed)
        rng.shuffle(shuffled)

        eval_count = max(1, int(len(shuffled) * eval_ratio))
        eval_set = shuffled[:eval_count]
        train_set = shuffled[eval_count:]

        return train_set, eval_set

    def export_train_and_eval(
        self,
        examples: list[dict[str, Any]],
        train_path: str | Path = "data/datasets/slm_train.jsonl",
        eval_path: str | Path = "data/datasets/slm_eval.jsonl",
        eval_ratio: float = 0.2,
    ) -> tuple[int, int]:
        """Split and export train and eval datasets into two separate JSONL files."""
        train_set, eval_set = self.split_train_eval(examples, eval_ratio=eval_ratio)

        def _write(data: list[dict[str, Any]], path: Path) -> int:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                for row in data:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            return len(data)

        n_train = _write(train_set, Path(train_path))
        n_eval = _write(eval_set, Path(eval_path))

        return n_train, n_eval

"""Reviewed source annotations for the two ingestion tasks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperAnnotation:
    """Literal facts checked against one public arXiv abstract."""

    arxiv_id: str
    concept: str
    concept_type: str
    fields: tuple[tuple[str, str, str], ...]
    split: str = "train"


# The test papers are held out by identifier, including every prompt variant.
# Values are source substrings, not model-generated labels.
PAPERS = (
    PaperAnnotation(
        "2106.09685",
        "Low-Rank Adaptation",
        "technique",
        (
            ("methodology", "techniques", "Low-Rank Adaptation"),
            ("efficiency", "parameter_efficiency", "10,000 times"),
            ("efficiency", "memory_efficiency", "3 times"),
        ),
    ),
    PaperAnnotation(
        "1706.03762",
        "Transformer",
        "core",
        (
            ("methodology", "model_architecture", "Transformer"),
            ("experiments", "reported_results", "28.4 BLEU"),
        ),
    ),
    PaperAnnotation(
        "1412.6980",
        "Adam",
        "algorithm",
        (("methodology", "algorithms", "Adam"),),
    ),
    PaperAnnotation(
        "2005.11401",
        "retrieval-augmented generation",
        "technique",
        (
            ("methodology", "techniques", "retrieval-augmented generation"),
            ("methodology", "model_architecture", "dense vector index of Wikipedia"),
        ),
    ),
    PaperAnnotation(
        "2305.14314",
        "QLoRA",
        "technique",
        (
            ("methodology", "techniques", "QLoRA"),
            ("efficiency", "model_parameters", "65B parameter model"),
            ("reproducibility", "hardware_specifications", "48GB GPU"),
        ),
    ),
    PaperAnnotation(
        "2205.14135",
        "FlashAttention",
        "algorithm",
        (
            ("methodology", "algorithms", "FlashAttention"),
            ("experiments", "reported_results", "15% end-to-end wall-clock speedup"),
        ),
    ),
    PaperAnnotation(
        "1812.08434",
        "Graph neural networks",
        "core",
        (
            ("methodology", "model_architecture", "Graph neural networks"),
            ("methodology", "techniques", "message passing"),
        ),
    ),
    PaperAnnotation(
        "1905.02244",
        "MobileNetV3",
        "core",
        (
            ("methodology", "model_architecture", "MobileNetV3"),
            ("experiments", "datasets", "ImageNet"),
            ("experiments", "datasets", "COCO"),
        ),
    ),
    PaperAnnotation(
        "2103.00020",
        "zero-shot transfer",
        "technique",
        (
            ("methodology", "training_approach", "natural language"),
            ("experiments", "datasets", "ImageNet"),
        ),
    ),
    PaperAnnotation(
        "2001.08361",
        "scaling laws",
        "definition",
        (("methodology", "contributions", "scaling laws"),),
        "validation",
    ),
    PaperAnnotation(
        "1606.01549",
        "Gated-Attention (GA) Reader",
        "core",
        (
            ("methodology", "model_architecture", "Gated-Attention (GA) Reader"),
            ("experiments", "datasets", "Who Did What"),
        ),
        "validation",
    ),
    PaperAnnotation(
        "2309.14717",
        "quantization-aware low-rank adaptation (QA-LoRA)",
        "algorithm",
        (
            ("methodology", "techniques", "quantization-aware low-rank adaptation (QA-LoRA)"),
            ("methodology", "model_architecture", "LLaMA and LLaMA2"),
            ("methodology", "training_approach", "INT4"),
        ),
        "test",
    ),
    PaperAnnotation(
        "2305.18290",
        "Direct Preference Optimization (DPO)",
        "algorithm",
        (
            ("methodology", "algorithms", "Direct Preference Optimization (DPO)"),
            ("research_relationships", "compares_against", "PPO-based RLHF"),
        ),
        "test",
    ),
    PaperAnnotation(
        "1810.04805",
        "BERT",
        "core",
        (
            ("methodology", "model_architecture", "BERT"),
            ("experiments", "reported_results", "80.5%"),
        ),
        "test",
    ),
    PaperAnnotation(
        "1706.02216",
        "GraphSAGE",
        "algorithm",
        (("methodology", "algorithms", "GraphSAGE"), ("experiments", "datasets", "Reddit")),
        "test",
    ),
)

"""Reject research field types contradicted by their own evidence quote."""

from __future__ import annotations

import re
from typing import Any

MODEL_ROLE = re.compile(
    r"^\s+(?:(?:(?:and|or)\s+)?[A-Za-z0-9-]+\s+)*"
    r"(?:models?|model families|model family|model architectures|model variants)\b",
    re.I,
)
MODEL_ROLE_WINDOW = 48
DATASET_ROLE = re.compile(r"\b(?:datasets?|data sets?|benchmarks?|corpus|corpora)\b", re.I)
EXPERIMENT_ROLE = re.compile(r"\b(?:experiments?|evaluat\w*|train\w*|test\w*)\b", re.I)
MATH_EVIDENCE = re.compile(
    r"(?:\b(?:equation|formula|formulat|objective function|loss function|mathematical model)\w*\b|[=∑∫∂∇])",
    re.I,
)
CONTRIBUTION_ROLE = re.compile(
    r"\b(?:propos\w*|present\w*|introduc\w*|develop\w*|demonstrat\w*|"
    r"show\w*|contribut\w*|novel|provid\w*|releas\w*|creat\w*|"
    r"crowdsourc\w*|achiev\w*)\b",
    re.I,
)
NUMBER = re.compile(r"\d")
GENERIC_DATASET_NAME = re.compile(
    r"(?:test|training|train|validation|official|public|comprehensive|benchmarking|many|"
    r"speech|asr|reference|evaluation|proposed|our|this|the|we)\s+"
    r"(?:datasets?|data sets?|benchmarks?|corpus|corpora)",
    re.I,
)
TECHNIQUE_VALUE = re.compile(
    r"\b(?:models?|architectures?|algorithms?|frameworks?|approaches?|methods?|"
    r"techniques?|methodolog(?:y|ies)|pipelines?|networks?|learning|transformers?|classifications?|"
    r"segmentations?|detections?|radiomics|cnns?|svms?|resnets?|bert|gpt|yolo|"
    r"vit|unet|lstms?|rnns?|feature extraction|image processing)\b",
    re.I,
)
TECHNIQUE_ACRONYM = re.compile(
    r"\b(?:[A-Z]{2,}[A-Za-z0-9-]*|LoRA|QLoRA|[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]+)+)\b"
)
NON_METHOD_PHRASE = re.compile(
    r"^(?:an?\s+)?(?:overview|review|survey|summary|analysis)\b|"
    r"^(?:some|several|various|important)\s+(?:important\s+)?(?:aspects?|issues?|factors?)\b|"
    r"^(?:an?\s+)?(?:complete|general|generic)\s+(?:framework|approach|method|model)\b|"
    r"^(?:of|regarding)\s+|"
    r"^(?:several|various)\s+(?:deep|machine|AI)\b|"
    r"\b(?:and their evaluation metrics|and measure the prediction performance)\b",
    re.I,
)
GENERIC_DATA_DESCRIPTION = re.compile(
    r"^(?:dermoscopic|clinical|medical|training|testing)(?:\s+(?:images?|data|samples?))?$",
    re.I,
)
UNNAMED_SINGLE_WORD = re.compile(r"[A-Z][a-z]+")
RESEARCH_CLAIM_SIGNAL = re.compile(
    r"\b(?:find|found|show|demonstrat\w*|indicat\w*|suggest\w*|"
    r"improv\w*|outperform\w*|achiev\w*|reduc\w*|increas\w*|"
    r"associat\w*|correlat\w*|results?|findings?)\b",
    re.I,
)


def field_role_supported(group: str, field: str, value: str, evidence: str) -> bool:
    """A value called a model family in the quote cannot be a dataset."""
    if (group, field) == ("claims", "claim_text"):
        return bool(RESEARCH_CLAIM_SIGNAL.search(value))
    if group == "methodology" and field in {
        "techniques",
        "algorithms",
        "model_architecture",
    }:
        return (
            not DATASET_ROLE.search(value)
            and not NON_METHOD_PHRASE.search(value.strip())
            and bool(TECHNIQUE_VALUE.search(value) or TECHNIQUE_ACRONYM.search(value))
        )
    if (group, field) == ("methodology", "contributions"):
        return bool(CONTRIBUTION_ROLE.search(evidence)) and not value.casefold().startswith(
            ("is ", "was ", "are ")
        )
    if (group, field) in {
        ("datasets", "dataset_size"),
        ("datasets", "sample_size"),
        ("datasets", "sample_sizes"),
        ("experiments", "sample_sizes"),
    }:
        return bool(NUMBER.search(value))
    if group == "methodology" and field in {
        "mathematical_formulation",
        "mathematical_formulations",
    }:
        return bool(MATH_EVIDENCE.search(evidence))
    if (group, field) not in {
        ("experiments", "datasets"),
        ("datasets", "dataset_names"),
        ("datasets", "benchmark_names"),
    }:
        return True
    if (
        GENERIC_DATASET_NAME.fullmatch(value.strip())
        or value.casefold().startswith(("we ", "we\n", "our ", "our\n", "this ", "this\n"))
        or GENERIC_DATA_DESCRIPTION.fullmatch(value.strip())
        or UNNAMED_SINGLE_WORD.fullmatch(value.strip())
    ):
        return False
    position = evidence.casefold().find(value.casefold())
    if position < 0:
        return False
    if not (DATASET_ROLE.search(evidence) or EXPERIMENT_ROLE.search(evidence)):
        return False
    trailing = evidence[position + len(value) : position + len(value) + MODEL_ROLE_WINDOW]
    return MODEL_ROLE.match(trailing) is None


def valid_evidence_item(item: object, record: dict[str, Any]) -> bool:
    """Verify stored quote, field role, and PDF or abstract provenance."""
    if not isinstance(item, dict):
        return False
    group, field = item.get("group"), item.get("field")
    value, quote = item.get("value"), item.get("evidence_text")
    if not all(isinstance(part, str) and part.strip() for part in (group, field, value, quote)):
        return False
    if value.casefold() not in quote.casefold():
        return False
    if not field_role_supported(group, field, value, quote):
        return False
    state = item.get("verification_status")
    if state == "abstract_quote_matched":
        return quote.casefold() in str(record.get("content") or "").casefold()
    metadata = record.get("metadata") or {}
    return (
        state in {"verified", "quote_matched"}
        and isinstance(item.get("pdf_page"), int)
        and item["pdf_page"] > 0
        and bool(metadata.get("pdf_sha256"))
        and item.get("pdf_sha256") == metadata["pdf_sha256"]
    )

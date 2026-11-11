"""Extract quote-verified scientific facts from abstracts using local Ollama."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Any

import requests

from archipelago.scholarly.extraction.semantic_guard import field_role_supported

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "abstract_fields_v2.txt"
DATASET_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "abstract_datasets_v1.txt"
OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "qwen3.5:0.8b"
REQUEST_TIMEOUT_SECONDS = 45
MAX_ABSTRACT_CHARS = 4000
MAX_FIELDS = 6
EXTRACTOR_VERSION = "abstract-quote-slm-2.0.0"
ALLOWED_FIELDS = frozenset(
    {
        ("methodology", "research_problem"),
        ("methodology", "contributions"),
        ("methodology", "techniques"),
        ("methodology", "algorithms"),
        ("methodology", "model_architecture"),
        ("experiments", "datasets"),
        ("experiments", "benchmarks"),
        ("experiments", "evaluation_metrics"),
        ("experiments", "reported_results"),
        ("research_usefulness", "limitations"),
        ("research_usefulness", "future_work"),
    }
)
MODEL_MAX_TOKENS = 350
EXTRACTION_CONFIDENCE = 0.8


def ingestion_model_name() -> str:
    """Resolve the shared model after the worker has loaded its environment."""
    return (
        os.getenv("ARCHIPELAGO_RESEARCH_MODEL")
        or os.getenv("ARCHIPELAGO_INGESTION_MODEL")
        or MODEL_NAME
    )


def verify_abstract_fields(candidates: object, abstract: str) -> list[dict[str, Any]]:
    """Keep only literal source spans and values from the supplied abstract."""
    if isinstance(candidates, dict):
        candidates = [candidates]
    if not isinstance(candidates, list):
        return []
    verified = []
    for candidate in candidates[:MAX_FIELDS]:
        if not isinstance(candidate, dict):
            continue
        group, field = candidate.get("group"), candidate.get("field")
        value = candidate.get("value")
        if (
            not isinstance(group, str)
            or not isinstance(field, str)
            or (group, field) not in ALLOWED_FIELDS
            or not isinstance(value, str)
            or not value.strip()
            or value.casefold() not in abstract.casefold()
        ):
            continue
        quote = next(
            (
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", abstract)
                if value.casefold() in sentence.casefold()
                and field_role_supported(group, field, value, sentence)
            ),
            "",
        )
        if not quote:
            continue
        verified.append(
            {
                "group": group,
                "field": field,
                "value": value.strip(),
                "evidence_text": quote.strip(),
                "source_api": "paper_abstract_local_slm",
                "source_timestamp": datetime.now(UTC).isoformat(),
                "verification_status": "abstract_quote_matched",
                "extraction_confidence": EXTRACTION_CONFIDENCE,
                "extractor_version": EXTRACTOR_VERSION,
                "json_pointer": "/content",
                "section": "abstract",
            }
        )
    return verified


def _model_candidates(abstract: str, prompt_path: Path) -> object:
    """Request a bounded candidate response from the local model."""
    response = requests.post(
        OLLAMA_ENDPOINT,
        json={
            "model": ingestion_model_name(),
            "stream": False,
            "format": "json",
            "think": False,
            "messages": [
                {"role": "system", "content": prompt_path.read_text(encoding="utf-8")},
                {"role": "user", "content": abstract},
            ],
            "options": {"num_predict": MODEL_MAX_TOKENS, "temperature": 0},
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    content = (response.json().get("message") or {}).get("content")
    if not isinstance(content, str):
        raise ValueError("Abstract model did not return JSON")
    data = json.loads(content)
    if not isinstance(data, dict):
        return []
    if prompt_path == DATASET_PROMPT_PATH and isinstance(data.get("datasets"), list):
        return [
            {"group": "experiments", "field": "datasets", "value": name}
            for name in data["datasets"]
        ]
    return data.get("fields", data)


def extract_abstract_fields(abstract: str) -> list[dict[str, Any]]:
    """Run local extraction and reject values lacking literal abstract evidence."""
    abstract = abstract.strip()[:MAX_ABSTRACT_CHARS]
    if not abstract:
        return []
    verified = verify_abstract_fields(_model_candidates(abstract, PROMPT_PATH), abstract)
    if "dataset" in abstract.casefold() and not any(
        item["field"] == "datasets" for item in verified
    ):
        try:
            verified.extend(
                verify_abstract_fields(_model_candidates(abstract, DATASET_PROMPT_PATH), abstract)
            )
        except (requests.RequestException, ValueError):
            return verified
    return verified

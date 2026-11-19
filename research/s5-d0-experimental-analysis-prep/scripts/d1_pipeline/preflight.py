"""Preflight validator orchestrator for S5-D1 evaluation (legacy v1 and A/C v2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from d1_pipeline.preflight_checks import (
    resolve_neg_control_records,
    validate_judgments,
    validate_negative_controls,
    validate_schema_and_provenance,
)
from d1_pipeline.preflight_models import (
    PoolEntry,
    PreflightError,
    PreflightFinding,
    PreflightResult,
    load_pool_manifest,
    sha256_file,
)

__all__ = [
    "PoolEntry",
    "PreflightError",
    "PreflightFinding",
    "PreflightResult",
    "load_pool_manifest",
    "sha256_file",
    "validate_d1_preflight",
]


def _load_passage_texts(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {
            str(item["passage_id"]): str(item["text"])
            for item in raw
            if isinstance(item, dict) and "passage_id" in item and "text" in item
        }
    raise ValueError("Unsupported corpus passages JSON format")


def validate_d1_preflight(
    *,
    gold_labels_path: Path,
    frozen_pool_path: Path,
    frozen_rankings_path: Path,
    neg_control_path: Path | None = None,
    corpus_passages_path: Path | None = None,
    schema_mode: str = "auto",
    is_synthetic: bool = False,
) -> PreflightResult:
    """Run all S5-D1 preflight integrity checks and return a structured result."""
    result = PreflightResult(passed=False, schema_mode=schema_mode, is_synthetic=is_synthetic)

    required_paths = [
        ("gold_labels_path", gold_labels_path),
        ("frozen_pool_path", frozen_pool_path),
        ("frozen_rankings_path", frozen_rankings_path),
    ]
    if neg_control_path is not None:
        required_paths.append(("neg_control_path", neg_control_path))
    if corpus_passages_path is not None:
        required_paths.append(("corpus_passages_path", corpus_passages_path))

    for label, path in required_paths:
        if not path.exists() or not path.is_file():
            result.errors.append(PreflightFinding("MISSING_SOURCE_FILE", f"Missing {label}: {path}"))
    if result.errors:
        return result

    try:
        pool_index, pool_version, pool_sha, pool_query_ids = load_pool_manifest(frozen_pool_path)
    except (OSError, ValueError, KeyError) as exc:
        result.errors.append(PreflightFinding("INVALID_GOLD_SCHEMA", f"Failed to parse pool: {exc}"))
        return result

    result.pool_version = pool_version
    result.pool_sha256 = pool_sha
    result.rankings_sha256 = sha256_file(frozen_rankings_path)
    result.gold_labels_sha256 = sha256_file(gold_labels_path)
    result.neg_control_sha256 = sha256_file(neg_control_path) if neg_control_path else result.gold_labels_sha256

    try:
        gold = json.loads(gold_labels_path.read_text(encoding="utf-8"))
        if not isinstance(gold, dict):
            raise ValueError("Gold labels root must be a JSON object")
    except (OSError, ValueError) as exc:
        result.errors.append(PreflightFinding("INVALID_GOLD_SCHEMA", f"Failed to parse gold JSON: {exc}"))
        return result

    neg_payload: dict[str, Any] | None = None
    if neg_control_path is not None:
        try:
            neg_payload = json.loads(neg_control_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            result.errors.append(
                PreflightFinding("UNVERIFIED_NEGATIVE_CONTROLS", f"Failed to parse neg-control JSON: {exc}")
            )
            return result

    passage_texts: dict[str, str] | None = None
    if corpus_passages_path is not None:
        try:
            passage_texts = _load_passage_texts(corpus_passages_path)
        except (OSError, ValueError) as exc:
            result.errors.append(PreflightFinding("MISSING_SOURCE_FILE", f"Failed to parse corpus passages: {exc}"))
            return result

    resolved_mode = validate_schema_and_provenance(gold, schema_mode, result.errors)
    result.schema_mode = resolved_mode

    if gold.get("pool_version") != pool_version:
        result.errors.append(
            PreflightFinding(
                "PAIR_ID_HASH_MISALIGNMENT",
                f"pool_version mismatch: expected {pool_version!r}, got {gold.get('pool_version')!r}",
            )
        )
    if gold.get("pool_sha256") != pool_sha:
        result.errors.append(
            PreflightFinding(
                "PAIR_ID_HASH_MISALIGNMENT",
                f"pool_sha256 mismatch: expected {pool_sha!r}, got {gold.get('pool_sha256')!r}",
            )
        )

    neg_records = resolve_neg_control_records(gold, neg_payload)
    validate_negative_controls(neg_records, pool_query_ids, resolved_mode, result)
    validate_judgments(gold, pool_index, passage_texts, result.errors)

    result.passed = len(result.errors) == 0
    return result

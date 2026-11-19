"""Pinned essential model verification and controlled CPU smoke test for S5-v3.1."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import numpy as np

EMBEDDING_DIM_EXPECTED = 768
UNIT_NORM_TOLERANCE = 1e-4
DETERMINISM_ATOL = 1e-5
HASH_CHUNK_BYTES = 65536
SMOKE_TEST_SENTENCES: tuple[str, str] = (
    "Neutral verification sentence one for deterministic embedding check.",
    "Neutral verification sentence two for vector norm and shape validation.",
)


@dataclass(frozen=True)
class ModelVerificationReport:
    """Deterministic verification result for the pinned Snowflake embedding model."""

    repo_id: str
    revision: str
    license_id: str
    pin_manifest_sha256: str
    local_path_relative: str
    verified_file_count: int
    total_weight_bytes: int
    model_safetensors_sha256: str
    all_files_verified: bool
    smoke_test: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "repo_id": self.repo_id,
            "revision": self.revision,
            "license": self.license_id,
            "pin_manifest_sha256": self.pin_manifest_sha256,
            "local_path_relative": self.local_path_relative,
            "verified_file_count": self.verified_file_count,
            "total_weight_bytes": self.total_weight_bytes,
            "model_safetensors_sha256": self.model_safetensors_sha256,
            "all_files_verified": self.all_files_verified,
            "smoke_test": dict(self.smoke_test),
        }


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file using fixed-size streaming reads."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_pinned_model_files(
    pin_manifest_path: Path,
    repo_root: Path,
) -> tuple[dict[str, Any], Path, str]:
    """Verify every pinned file's exact byte size and SHA-256 hash against the pin manifest.

    Raises FileNotFoundError or ValueError on any missing file or hash/size mismatch.
    """
    if not pin_manifest_path.exists():
        raise FileNotFoundError(f"Model pin manifest not found: {pin_manifest_path}")

    pin_sha256 = compute_file_sha256(pin_manifest_path)
    pin_data = json.loads(pin_manifest_path.read_text(encoding="utf-8"))
    model_dir = repo_root / str(pin_data["local_path"])
    if not model_dir.exists():
        raise FileNotFoundError(f"Pinned local model directory missing: {model_dir}")

    pinned_files: dict[str, dict[str, Any]] = pin_data.get("files", {})
    if not pinned_files:
        raise ValueError("Model pin manifest contains zero pinned files.")

    for rel_name, expected in sorted(pinned_files.items()):
        target = model_dir / rel_name
        if not target.exists():
            raise FileNotFoundError(f"Missing pinned model file: {target}")
        actual_bytes = target.stat().st_size
        expected_bytes = int(expected["bytes"])
        if actual_bytes != expected_bytes:
            raise ValueError(
                f"Byte size mismatch for {rel_name}: expected {expected_bytes}, got {actual_bytes}"
            )
        actual_sha = compute_file_sha256(target)
        expected_sha = str(expected["sha256"])
        if actual_sha != expected_sha:
            raise ValueError(
                f"SHA-256 mismatch for {rel_name}: expected {expected_sha}, got {actual_sha}"
            )

    return pin_data, model_dir, pin_sha256


def run_controlled_cpu_smoke_test(model_dir: Path) -> dict[str, Any]:
    """Run controlled offline CPU inference smoke test on neutral fixed sentences."""
    from sentence_transformers import SentenceTransformer

    t0 = time.perf_counter()
    model = SentenceTransformer(str(model_dir), device="cpu", local_files_only=True)
    load_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    emb_a = model.encode(
        list(SMOKE_TEST_SENTENCES),
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    encode_s = time.perf_counter() - t1

    emb_b = model.encode(
        list(SMOKE_TEST_SENTENCES),
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    arr_a = np.asarray(emb_a, dtype=np.float32)
    arr_b = np.asarray(emb_b, dtype=np.float32)

    if arr_a.shape != (len(SMOKE_TEST_SENTENCES), EMBEDDING_DIM_EXPECTED):
        raise ValueError(
            f"Unexpected smoke-test shape: {arr_a.shape}, "
            f"expected {(len(SMOKE_TEST_SENTENCES), EMBEDDING_DIM_EXPECTED)}"
        )
    if not bool(np.all(np.isfinite(arr_a))):
        raise ValueError("Non-finite values detected in Snowflake smoke-test embeddings.")

    norms = np.linalg.norm(arr_a, axis=1)
    unit_norm_ok = bool(np.all(np.abs(norms - 1.0) <= UNIT_NORM_TOLERANCE))
    if not unit_norm_ok:
        raise ValueError(f"Smoke-test embeddings are not unit-normalized: norms={norms.tolist()}")

    deterministic_ok = bool(np.allclose(arr_a, arr_b, atol=DETERMINISM_ATOL))
    if not deterministic_ok:
        raise ValueError("Smoke-test embeddings failed repeat-run determinism check.")

    return {
        "device": "cpu",
        "local_files_only": True,
        "input_count": len(SMOKE_TEST_SENTENCES),
        "output_shape": list(arr_a.shape),
        "dtype": str(arr_a.dtype),
        "all_finite": True,
        "unit_norm_verified": unit_norm_ok,
        "repeat_run_deterministic": deterministic_ok,
        "model_load_seconds": round(load_s, 4),
        "smoke_encode_seconds": round(encode_s, 4),
        "benchmark_query_or_label_used": False,
    }


def verify_essential_model(
    pin_manifest_path: Path,
    repo_root: Path,
    *,
    run_smoke_test: bool = True,
) -> ModelVerificationReport:
    """Verify all pinned model files and optionally run controlled CPU smoke test."""
    pin_data, model_dir, pin_sha256 = verify_pinned_model_files(pin_manifest_path, repo_root)
    files_map: dict[str, dict[str, Any]] = pin_data["files"]
    total_bytes = sum(int(meta["bytes"]) for meta in files_map.values())
    safetensors_sha = str(files_map["model.safetensors"]["sha256"])

    smoke_info = (
        run_controlled_cpu_smoke_test(model_dir)
        if run_smoke_test
        else {"skipped": True, "benchmark_query_or_label_used": False}
    )

    return ModelVerificationReport(
        repo_id=str(pin_data["repo_id"]),
        revision=str(pin_data["revision"]),
        license_id=str(pin_data["license"]),
        pin_manifest_sha256=pin_sha256,
        local_path_relative=str(pin_data["local_path"]),
        verified_file_count=len(files_map),
        total_weight_bytes=total_bytes,
        model_safetensors_sha256=safetensors_sha,
        all_files_verified=True,
        smoke_test=smoke_info,
    )

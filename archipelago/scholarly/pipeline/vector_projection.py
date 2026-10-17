"""Build a local, rebuildable research embedding matrix from canonical text."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

MODEL_ENV = "ARCHIPELAGO_RESEARCH_EMBEDDING_MODEL"
EMBED_BATCH_SIZE = 32


def build_vector_projection(inputs_path: Path) -> dict[str, Any]:
    """Encode canonical paper text locally; report absence without inventing vectors."""
    model_name = os.getenv(MODEL_ENV, "").strip()
    if not model_name:
        return {"state": "not_configured", "model": None, "count": 0, "path": None}
    from sentence_transformers import SentenceTransformer

    rows = [json.loads(line) for line in inputs_path.read_text(encoding="utf-8").splitlines()]
    rows = [row for row in rows if row.get("text")]
    if not rows:
        return {"state": "empty", "model": model_name, "count": 0, "path": None}
    model = SentenceTransformer(model_name, local_files_only=True, trust_remote_code=False)
    vectors = model.encode(
        [row["text"] for row in rows],
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(rows) or not np.isfinite(matrix).all():
        raise ValueError("Embedding model returned invalid research vectors")
    vector_path = inputs_path.with_suffix(".npz")
    np.savez_compressed(vector_path, paper_ids=[row["paper_id"] for row in rows], vectors=matrix)
    digest = hashlib.sha256(vector_path.read_bytes()).hexdigest()
    return {
        "state": "ready",
        "model": model_name,
        "count": len(rows),
        "dimensions": int(matrix.shape[1]),
        "path": str(vector_path),
        "sha256": digest,
    }

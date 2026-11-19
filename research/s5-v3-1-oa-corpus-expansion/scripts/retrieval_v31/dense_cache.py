"""Hash-pinned Snowflake dense embedding cache, dense retriever, and Hybrid RRF control."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import numpy as np
from retrieval_v3.lexical import BM25LexicalControl
from retrieval_v3.types import CorpusPassage, QueryProvenance, RankedPassage

from retrieval_v31.model_pin import EMBEDDING_DIM_EXPECTED, compute_file_sha256

ARCTIC_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DEFAULT_ENCODE_BATCH_SIZE = 32
DEFAULT_RRF_K = 60
DEFAULT_HYBRID_CANDIDATE_K = 50


def compute_corpus_identity_hashes(passages: Sequence[CorpusPassage]) -> dict[str, Any]:
    """Compute deterministic passage-ID and passage-text SHA-256 fingerprints."""
    pid_hasher = hashlib.sha256()
    text_hasher = hashlib.sha256()
    for p in passages:
        pid_hasher.update(p.passage_id.encode("utf-8"))
        pid_hasher.update(b"\n")
        text_hasher.update(p.text.encode("utf-8"))
        text_hasher.update(b"\n")
    return {
        "passage_count": len(passages),
        "passage_ids_sha256": pid_hasher.hexdigest(),
        "passage_texts_sha256": text_hasher.hexdigest(),
    }


def load_or_build_embedding_cache(
    passages: Sequence[CorpusPassage],
    cache_npy_path: Path,
    model_pin_sha256: str,
    model_revision: str,
    *,
    encode_fn: Callable[[list[str]], np.ndarray],
    force_rebuild: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Load and cryptographically verify dense embedding cache, or build & pin it."""
    meta_path = cache_npy_path.with_suffix(".meta.json")
    corpus_fp = compute_corpus_identity_hashes(passages)

    if not force_rebuild and cache_npy_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        verify_embedding_cache_integrity(
            cache_npy_path,
            meta,
            expected_passage_count=len(passages),
            expected_passage_ids_sha256=corpus_fp["passage_ids_sha256"],
            expected_passage_texts_sha256=corpus_fp["passage_texts_sha256"],
            expected_model_pin_sha256=model_pin_sha256,
        )
        embeddings = np.load(str(cache_npy_path))
        return np.asarray(embeddings, dtype=np.float32), meta

    cache_npy_path.parent.mkdir(parents=True, exist_ok=True)
    texts = [" ".join((p.text or "").split()) for p in passages]
    t0 = time.perf_counter()
    raw_emb = encode_fn(texts)
    encode_s = time.perf_counter() - t0
    embeddings = np.asarray(raw_emb, dtype=np.float32)

    if embeddings.ndim != 2 or embeddings.shape[0] != len(passages):
        raise ValueError(
            f"Encoded matrix shape mismatch: got {embeddings.shape}, expected ({len(passages)}, D)"
        )
    if not bool(np.all(np.isfinite(embeddings))):
        raise ValueError("Non-finite values in encoded corpus embeddings.")

    np.save(str(cache_npy_path), embeddings)
    emb_sha256 = compute_file_sha256(cache_npy_path)
    meta = {
        "schema_version": "s5v31_dense_cache_v1",
        "model_revision": model_revision,
        "model_pin_sha256": model_pin_sha256,
        "passage_count": len(passages),
        "passage_ids_sha256": corpus_fp["passage_ids_sha256"],
        "passage_texts_sha256": corpus_fp["passage_texts_sha256"],
        "embedding_matrix_sha256": emb_sha256,
        "embedding_matrix_shape": list(embeddings.shape),
        "dtype": str(embeddings.dtype),
        "encode_seconds": round(encode_s, 4),
        "throughput_passages_per_second": round(
            len(passages) / encode_s if encode_s > 0.0 else 0.0, 2
        ),
        "cache_file_bytes": cache_npy_path.stat().st_size,
    }
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return embeddings, meta


def verify_embedding_cache_integrity(
    cache_npy_path: Path,
    meta: dict[str, Any],
    *,
    expected_passage_count: int,
    expected_passage_ids_sha256: str,
    expected_passage_texts_sha256: str,
    expected_model_pin_sha256: str,
) -> None:
    """Fail-closed cryptographic verification of dense embedding cache against corpus & model."""
    if not cache_npy_path.exists():
        raise FileNotFoundError(f"Dense embedding cache missing: {cache_npy_path}")
    if int(meta.get("passage_count", -1)) != expected_passage_count:
        raise ValueError(
            f"Cache passage count mismatch: expected {expected_passage_count}, "
            f"got {meta.get('passage_count')}"
        )
    if meta.get("passage_ids_sha256") != expected_passage_ids_sha256:
        raise ValueError("Cache passage_ids_sha256 mismatch against active Corpus v3.1.")
    if meta.get("passage_texts_sha256") != expected_passage_texts_sha256:
        raise ValueError("Cache passage_texts_sha256 mismatch against active Corpus v3.1.")
    if meta.get("model_pin_sha256") != expected_model_pin_sha256:
        raise ValueError("Cache model_pin_sha256 mismatch against pinned Snowflake model.")

    actual_sha = compute_file_sha256(cache_npy_path)
    expected_sha = str(meta.get("embedding_matrix_sha256", ""))
    if actual_sha != expected_sha:
        raise ValueError(
            f"Dense embedding .npy SHA-256 mismatch: expected {expected_sha}, got {actual_sha}"
        )

    arr = np.load(str(cache_npy_path))
    expected_shape = tuple(meta.get("embedding_matrix_shape", []))
    if tuple(arr.shape) != expected_shape or arr.shape[0] != expected_passage_count:
        raise ValueError(f"Dense embedding shape mismatch: file={arr.shape}, meta={expected_shape}")


def make_snowflake_cpu_encoder(
    model_dir: Path,
    *,
    batch_size: int = DEFAULT_ENCODE_BATCH_SIZE,
) -> Callable[[list[str]], np.ndarray]:
    """Create a deterministic offline CPU encoder from the local pinned Snowflake directory."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(model_dir), device="cpu", local_files_only=True)

    def _encode(texts: list[str]) -> np.ndarray:
        arr = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(arr, dtype=np.float32)

    return _encode


class DenseSnowflakeRetriever:
    """Deterministic L2-normalized dot-product dense retriever over pinned Snowflake cache."""

    def __init__(
        self,
        passages: Sequence[CorpusPassage],
        doc_embeddings: np.ndarray,
        query_encoder: Callable[[list[str]], np.ndarray],
        *,
        query_prefix: str = ARCTIC_QUERY_PREFIX,
    ) -> None:
        self.passage_ids = [p.passage_id for p in passages]
        self.doc_embeddings = np.asarray(doc_embeddings, dtype=np.float32)
        self.query_encoder = query_encoder
        self.query_prefix = query_prefix
        if self.doc_embeddings.shape[0] != len(self.passage_ids):
            raise ValueError(
                f"Embedding rows ({self.doc_embeddings.shape[0]}) != passages ({len(self.passage_ids)})"
            )

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Encode query with Arctic prefix and return deterministic top_k (passage_id, score)."""
        q_emb = self.query_encoder([f"{self.query_prefix}{query}"])[0]
        sims = self.doc_embeddings @ q_emb
        ranked = [
            (pid, float(score)) for pid, score in zip(self.passage_ids, sims.tolist(), strict=True)
        ]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        return ranked[:top_k]

    def search_ranked(
        self, query: str, top_k: int
    ) -> tuple[tuple[RankedPassage, ...], QueryProvenance]:
        """Return RankedPassage tuple + QueryProvenance for unified diagnostics."""
        hits = self.search(query, top_k=top_k)
        ranked = tuple(
            RankedPassage(passage_id=pid, rank=idx, score=sc, source="dense_snowflake")
            for idx, (pid, sc) in enumerate(hits, start=1)
        )
        return ranked, QueryProvenance(
            routing_decision="dense_snowflake_control",
            graph_route_weight=0.0,
            lexical_route_weight=0.0,
        )


class HybridRRFControl:
    """Hybrid RRF (BM25 + Snowflake Dense, k=60) with full end-to-end execution."""

    def __init__(
        self,
        bm25: BM25LexicalControl,
        dense: DenseSnowflakeRetriever,
        *,
        rrf_k: int = DEFAULT_RRF_K,
        candidate_k: int = DEFAULT_HYBRID_CANDIDATE_K,
    ) -> None:
        self.bm25 = bm25
        self.dense = dense
        self.rrf_k = rrf_k
        self.candidate_k = candidate_k

    def search_ranked(
        self, query: str, top_k: int
    ) -> tuple[tuple[RankedPassage, ...], QueryProvenance]:
        """Run BM25 and Dense end-to-end and fuse via deterministic RRF."""
        bm25_hits = self.bm25.search(query, top_k=self.candidate_k)
        dense_hits = self.dense.search(query, top_k=self.candidate_k)

        scores: dict[str, float] = defaultdict(float)
        for rank_idx, (pid, _sc) in enumerate(bm25_hits, start=1):
            scores[pid] += 1.0 / (self.rrf_k + rank_idx)
        for rank_idx, (pid, _sc) in enumerate(dense_hits, start=1):
            scores[pid] += 1.0 / (self.rrf_k + rank_idx)

        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        ranked = tuple(
            RankedPassage(passage_id=pid, rank=idx, score=sc, source="hybrid_rrf")
            for idx, (pid, sc) in enumerate(ordered, start=1)
        )
        return ranked, QueryProvenance(
            routing_decision="hybrid_rrf_bm25_dense",
            graph_route_weight=0.0,
            lexical_route_weight=0.5,
        )


def expected_embedding_dim() -> int:
    """Return expected Snowflake Arctic Embed M v1.5 vector dimension."""
    return EMBEDDING_DIM_EXPECTED

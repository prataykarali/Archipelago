"""Offline retrieval baselines and evaluation metrics for Archipelago S3.

Implements:
- Fixed, deduplicated, provenance-verified corpus construction from KuzuDB
- Pure-Python BM25Okapi retriever (configurable k1, b)
- Dense retriever (Snowflake/snowflake-arctic-embed-m-v1.5 or injected encoder)
- Hybrid Reciprocal Rank Fusion (RRF)
- Standard IR evaluation metrics (Recall@k, Precision@k, MRR, nDCG@k)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Sequence

import numpy as np

from archipelago.eval.dataset_integrity import content_hash, normalize_doc_id

DEFAULT_BM25_K1 = 1.5
DEFAULT_BM25_B = 0.75
DEFAULT_RRF_K = 60
DEFAULT_DENSE_MODEL = "Snowflake/snowflake-arctic-embed-m-v1.5"
DEFAULT_ARCTIC_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Deterministic lowercase alphanumeric tokenizer."""
    return _TOKEN_RE.findall(text.lower())


def normalize_passage_text(text: str) -> str:
    """Normalize whitespace for consistent hashing and deduplication."""
    return " ".join((text or "").split())


@dataclass(frozen=True)
class Passage:
    """Provenance-verified passage in the fixed S3 offline corpus."""

    passage_id: str
    doc_id: str
    chunk_id: str
    page_number: int
    section_title: str
    text: str
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_fixed_corpus_from_kuzu(
    db_path: str | Path,
    *,
    corpus_version: str = "s3_fixed_corpus_v1",
) -> tuple[list[Passage], dict[str, Any]]:
    """Build a deterministic, deduplicated, provenance-verified passage corpus.

    Rejects orphan chunks (missing Document -[:HAS_CHUNK]-> Chunk provenance)
    and empty passages, deduplicates identical normalized passage text, and
    returns (passages, corpus_manifest).
    """
    import kuzu

    resolved_db = Path(db_path)
    db = kuzu.Database(str(resolved_db), read_only=True)
    conn = kuzu.Connection(db)

    total_res = conn.execute("MATCH (c:Chunk) RETURN count(c)")
    total_chunk_nodes = int(total_res.get_next()[0]) if total_res.has_next() else 0

    res = conn.execute(
        "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) "
        "RETURN d.id, c.chunk_id, c.page_number, c.section_title, c.text_passage"
    )
    linked_rows: list[tuple[str, str, int, str, str]] = []
    while res.has_next():
        doc_id_raw, chunk_id_raw, page_raw, section_raw, text_raw = res.get_next()
        linked_rows.append(
            (
                normalize_doc_id(str(doc_id_raw or "")),
                str(chunk_id_raw or "").strip(),
                int(page_raw) if page_raw is not None else -1,
                str(section_raw or "").strip(),
                str(text_raw or ""),
            )
        )

    missing_provenance_chunks = max(0, total_chunk_nodes - len(linked_rows))

    # Deterministic sort before deduplication so canonical first occurrence is stable
    linked_rows.sort(key=lambda r: (r[0], r[2], r[1], r[4]))

    empty_text_chunks = 0
    invalid_provenance_chunks = 0
    duplicate_passages_removed = 0
    seen_hashes: set[str] = set()
    seen_passage_ids: set[str] = set()
    passages: list[Passage] = []
    doc_passage_counts: Counter[str] = Counter()

    for doc_id, chunk_id, page_number, section_title, raw_text in linked_rows:
        norm_text = normalize_passage_text(raw_text)
        if not norm_text:
            empty_text_chunks += 1
            continue
        if not doc_id or not chunk_id:
            invalid_provenance_chunks += 1
            continue

        sha = content_hash(norm_text)
        if sha in seen_hashes:
            duplicate_passages_removed += 1
            continue
        seen_hashes.add(sha)

        base_pid = f"{doc_id}::{chunk_id}"
        pid = base_pid
        if pid in seen_passage_ids:
            pid = f"{base_pid}::p{page_number}::{sha[:8]}"
        seen_passage_ids.add(pid)

        passages.append(
            Passage(
                passage_id=pid,
                doc_id=doc_id,
                chunk_id=chunk_id,
                page_number=page_number,
                section_title=section_title,
                text=norm_text,
                content_sha256=sha,
            )
        )
        doc_passage_counts[doc_id] += 1

    passages.sort(key=lambda p: p.passage_id)
    corpus_digest = hashlib.sha256(
        json.dumps([p.to_dict() for p in passages], sort_keys=True).encode("utf-8")
    ).hexdigest()

    manifest = {
        "corpus_version": corpus_version,
        "db_path": str(resolved_db),
        "total_chunk_nodes": total_chunk_nodes,
        "linked_chunk_nodes": len(linked_rows),
        "missing_provenance_chunks": missing_provenance_chunks,
        "invalid_provenance_chunks": invalid_provenance_chunks,
        "empty_text_chunks": empty_text_chunks,
        "duplicate_passages_removed": duplicate_passages_removed,
        "unique_passages": len(passages),
        "unique_documents": len(doc_passage_counts),
        "corpus_sha256": corpus_digest,
        "parsing_config": {
            "source": "kuzu_document_has_chunk",
            "whitespace_normalization": "collapse_spaces",
            "deduplication": "exact_normalized_sha256",
            "passage_id_format": "{doc_id}::{chunk_id}",
        },
        "documents": dict(sorted(doc_passage_counts.items())),
    }
    return passages, manifest


class BM25Retriever:
    """Pure-Python Robertson/Sparck Jones BM25Okapi retriever."""

    def __init__(
        self,
        passages: Sequence[Passage],
        *,
        k1: float = DEFAULT_BM25_K1,
        b: float = DEFAULT_BM25_B,
        tokenizer: Callable[[str], list[str]] = tokenize,
    ) -> None:
        if k1 < 0:
            raise ValueError("k1 must be non-negative")
        if not 0.0 <= b <= 1.0:
            raise ValueError("b must be in [0.0, 1.0]")

        self.k1 = float(k1)
        self.b = float(b)
        self.tokenizer = tokenizer
        self.passages = list(passages)
        self.passage_ids = [p.passage_id for p in self.passages]
        self.n_docs = len(self.passages)

        self._doc_tf: list[Counter[str]] = []
        self._doc_len: list[int] = []
        df: Counter[str] = Counter()

        for passage in self.passages:
            tokens = self.tokenizer(passage.text)
            tf = Counter(tokens)
            self._doc_tf.append(tf)
            self._doc_len.append(len(tokens))
            for term in tf:
                df[term] += 1

        self.avgdl = (sum(self._doc_len) / self.n_docs) if self.n_docs > 0 else 0.0
        self._idf: dict[str, float] = {
            term: math.log((self.n_docs - freq + 0.5) / (freq + 0.5) + 1.0)
            for term, freq in df.items()
        }

    def score_all(self, query: str) -> list[tuple[str, float]]:
        if self.n_docs == 0:
            return []
        q_terms = self.tokenizer(query)
        scores = [0.0] * self.n_docs
        if q_terms and self.avgdl > 0.0:
            for idx, (tf, dl) in enumerate(zip(self._doc_tf, self._doc_len)):
                denom_norm = self.k1 * (1.0 - self.b + self.b * (dl / self.avgdl))
                doc_score = 0.0
                for term in q_terms:
                    freq = tf.get(term, 0)
                    if freq == 0:
                        continue
                    idf = self._idf.get(term, 0.0)
                    doc_score += idf * (freq * (self.k1 + 1.0)) / (freq + denom_norm)
                scores[idx] = doc_score

        ranked = list(zip(self.passage_ids, scores))
        ranked.sort(key=lambda item: (-item[1], item[0]))
        return ranked

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if top_k <= 0:
            return []
        return self.score_all(query)[:top_k]


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(matrix, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return arr / norms


class DenseRetriever:
    """Dense cosine-similarity retriever over fixed passages."""

    def __init__(
        self,
        passages: Sequence[Passage],
        *,
        model_name: str = DEFAULT_DENSE_MODEL,
        device: str = "cpu",
        encoder: Any = None,
        batch_size: int = 32,
        query_prefix: str = DEFAULT_ARCTIC_QUERY_PREFIX,
        local_files_only: bool = True,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.query_prefix = query_prefix
        self.passages = list(passages)
        self.passage_ids = [p.passage_id for p in self.passages]

        if encoder is not None:
            self._encoder = encoder
        else:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(
                model_name,
                device=device,
                local_files_only=local_files_only,
            )

        if self.passages:
            texts = [p.text for p in self.passages]
            raw_emb = self._encode(texts)
            self._doc_embeddings = _l2_normalize(raw_emb)
        else:
            self._doc_embeddings = np.zeros((0, 0), dtype=np.float32)

    def _encode(self, texts: list[str]) -> np.ndarray:
        if callable(self._encoder) and not hasattr(self._encoder, "encode"):
            return np.asarray(self._encoder(texts), dtype=np.float32)
        return np.asarray(
            self._encoder.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            ),
            dtype=np.float32,
        )

    def score_all(self, query: str) -> list[tuple[str, float]]:
        if not self.passages:
            return []
        q_text = f"{self.query_prefix}{query}" if self.query_prefix else query
        q_emb = _l2_normalize(self._encode([q_text]))[0]
        sims = self._doc_embeddings @ q_emb
        ranked = [(pid, float(score)) for pid, score in zip(self.passage_ids, sims.tolist())]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        return ranked

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if top_k <= 0:
            return []
        return self.score_all(query)[:top_k]


def rrf_fuse(
    rankings: Sequence[Sequence[tuple[str, float] | str]],
    *,
    k: int = DEFAULT_RRF_K,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: RRF(d) = sum_r 1 / (k + rank_r(d)), 1-based ranks.

    Deduplicates repeated passage IDs within each individual ranker (preserving
    the earliest/highest rank), handles missing documents across rankers, and
    breaks ties deterministically by passage_id.
    """
    if k <= 0:
        raise ValueError("RRF constant k must be positive")
    if top_k <= 0:
        return []

    fused: dict[str, float] = {}
    for ranking in rankings:
        seen_in_ranker: set[str] = set()
        rank = 0
        for entry in ranking:
            pid = entry[0] if isinstance(entry, tuple) else str(entry)
            if pid in seen_in_ranker:
                continue
            seen_in_ranker.add(pid)
            rank += 1
            fused[pid] = fused.get(pid, 0.0) + 1.0 / (k + rank)

    ordered = sorted(fused.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:top_k]


def _positive_rel_map(relevant: set[str] | dict[str, float]) -> dict[str, float]:
    if isinstance(relevant, dict):
        return {pid: float(grade) for pid, grade in relevant.items() if float(grade) > 0.0}
    return {pid: 1.0 for pid in relevant}


def recall_at_k(
    ranked_ids: Sequence[str],
    relevant: set[str] | dict[str, float],
    k: int,
) -> float | None:
    if k <= 0:
        raise ValueError("k must be positive")
    rel_map = _positive_rel_map(relevant)
    if not rel_map:
        return None
    hits = sum(1 for pid in ranked_ids[:k] if pid in rel_map)
    return hits / len(rel_map)


def precision_at_k(
    ranked_ids: Sequence[str],
    relevant: set[str] | dict[str, float],
    k: int,
) -> float | None:
    if k <= 0:
        raise ValueError("k must be positive")
    rel_map = _positive_rel_map(relevant)
    if not rel_map:
        return None
    hits = sum(1 for pid in ranked_ids[:k] if pid in rel_map)
    return hits / k


def reciprocal_rank(
    ranked_ids: Sequence[str],
    relevant: set[str] | dict[str, float],
) -> float | None:
    rel_map = _positive_rel_map(relevant)
    if not rel_map:
        return None
    for idx, pid in enumerate(ranked_ids, start=1):
        if pid in rel_map:
            return 1.0 / idx
    return 0.0


def mean_reciprocal_rank(
    ranked_lists: Sequence[Sequence[str]],
    relevant_lists: Sequence[set[str] | dict[str, float]],
) -> float | None:
    if len(ranked_lists) != len(relevant_lists):
        raise ValueError("ranked_lists and relevant_lists must have equal length")
    rr_values = [
        rr
        for ranked, rel in zip(ranked_lists, relevant_lists)
        if (rr := reciprocal_rank(ranked, rel)) is not None
    ]
    if not rr_values:
        return None
    return sum(rr_values) / len(rr_values)


def ndcg_at_k(
    ranked_ids: Sequence[str],
    relevant: set[str] | dict[str, float],
    k: int,
) -> float | None:
    if k <= 0:
        raise ValueError("k must be positive")
    rel_map = _positive_rel_map(relevant)
    if not rel_map:
        return None

    dcg = 0.0
    for idx, pid in enumerate(ranked_ids[:k], start=1):
        gain = rel_map.get(pid, 0.0)
        if gain > 0.0:
            dcg += (2.0**gain - 1.0) / math.log2(idx + 1)

    ideal_gains = sorted(rel_map.values(), reverse=True)[:k]
    idcg = sum(
        (2.0**gain - 1.0) / math.log2(idx + 1)
        for idx, gain in enumerate(ideal_gains, start=1)
    )
    return (dcg / idcg) if idcg > 0.0 else 0.0


def evaluate_rankings(
    rankings_by_query: dict[str, Sequence[str]],
    qrels_by_query: dict[str, set[str] | dict[str, float]],
    *,
    ks: Sequence[int] = (1, 3, 5, 10),
) -> dict[str, Any]:
    """Compute Recall@k, Precision@k, MRR, and nDCG@k when gold qrels exist."""
    evaluable_qids = [
        qid
        for qid, rel in qrels_by_query.items()
        if qid in rankings_by_query and _positive_rel_map(rel)
    ]
    if not evaluable_qids:
        return {
            "status": "NO_HUMAN_GOLD",
            "evaluated_queries": 0,
            "metrics": None,
        }

    ranked_lists = [list(rankings_by_query[qid]) for qid in evaluable_qids]
    rel_lists = [qrels_by_query[qid] for qid in evaluable_qids]

    metrics: dict[str, float] = {}
    mrr_val = mean_reciprocal_rank(ranked_lists, rel_lists)
    if mrr_val is not None:
        metrics["mrr"] = round(mrr_val, 6)

    for k in ks:
        recalls = [r for ranked, rel in zip(ranked_lists, rel_lists) if (r := recall_at_k(ranked, rel, k)) is not None]
        precisions = [p for ranked, rel in zip(ranked_lists, rel_lists) if (p := precision_at_k(ranked, rel, k)) is not None]
        ndcgs = [n for ranked, rel in zip(ranked_lists, rel_lists) if (n := ndcg_at_k(ranked, rel, k)) is not None]
        if recalls:
            metrics[f"recall@{k}"] = round(sum(recalls) / len(recalls), 6)
        if precisions:
            metrics[f"precision@{k}"] = round(sum(precisions) / len(precisions), 6)
        if ndcgs:
            metrics[f"ndcg@{k}"] = round(sum(ndcgs) / len(ndcgs), 6)

    return {
        "status": "EVALUATED",
        "evaluated_queries": len(evaluable_qids),
        "metrics": metrics,
    }

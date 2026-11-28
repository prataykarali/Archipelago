"""Honest BM25 lexical, genuine neural dense, and hybrid RRF passage retrieval.

Provides query-specific passage retrieval independent of concept-graph nodes.
Dense retrieval uses a real SentenceTransformer encoder (or caller-injected
neural encoder) and reports ``dense_available=False`` rather than faking dense
vectors with lexical hashes when neural weights are unavailable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path
import re
from typing import Any

import numpy as np

LOGGER = logging.getLogger(__name__)

DEFAULT_DENSE_MODEL = "BAAI/bge-small-en-v1.5"
ENV_DENSE_ENABLED = "ARCHIPELAGO_DENSE_RETRIEVAL"
ENV_DENSE_MODEL = "ARCHIPELAGO_DENSE_MODEL"

DEFAULT_BM25_K1 = 1.5
DEFAULT_BM25_B = 0.75
DEFAULT_RRF_K = 60
DEFAULT_TOP_K = 10
DEFAULT_CANDIDATE_MULTIPLIER = 4
MIN_TOKEN_LEN = 2
MIN_BM25_SCORE = 0.0
MIN_DENSE_COSINE = 0.05
PHRASE_MATCH_BOOST = 0.25
EXPLANATORY_CHUNK_BOOST = 0.12
INTRO_FLUFF_PENALTY = 0.35
NON_BODY_PENALTY = 0.50
NORM_EPSILON = 1e-12

METHOD_HYBRID_BM25_DENSE = "hybrid_bm25_dense_rrf"
METHOD_DENSE_NEURAL = "dense_neural"
METHOD_BM25_LEXICAL = "bm25_lexical"

_TOKEN_RE = re.compile(r"b\+|[a-z0-9][a-z0-9_+#-]*")
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "done",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "here",
        "him",
        "his",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "me",
        "might",
        "more",
        "most",
        "my",
        "no",
        "not",
        "of",
        "on",
        "one",
        "only",
        "or",
        "other",
        "our",
        "out",
        "over",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "up",
        "us",
        "use",
        "used",
        "using",
        "very",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)
_INTRO_SECTION_RE = re.compile(
    r"\b(?:table\s+of\s+contents|contents|references|bibliography|index|preface|"
    r"acknowledg(?:e)?ments|about\s+the\s+authors|dialogue\s+on\s+the\s+book|"
    r"front\s*matter|copyright)\b",
    re.I,
)
_EXPLANATORY_CUE_RE = re.compile(
    r"(?:\b(?:defined\s+as|theorem|lemma|derivation|likelihood|posterior|prior|"
    r"covariance|eigenvector|eigenvalue|variance|page\s+table|virtual\s+page\s+number|"
    r"physical\s+frame|offset|formula|equation|algorithm|complexity|invariant)\b|"
    r"[=∑∏∫≈≤≥±√]|p\s*\([a-z0-9|,\s]+\))",
    re.I,
)


def tokenize_retrieval(text: str) -> list[str]:
    """Tokenize text preserving short technical terms (e.g. B+, 3NF, PCA, MLE, TLB)."""
    raw = (text or "").lower().replace("b+", "b_plus")
    out: list[str] = []
    for tok in _TOKEN_RE.findall(raw):
        cleaned = tok.strip("_-")
        if len(cleaned) < MIN_TOKEN_LEN or cleaned in _STOPWORDS:
            continue
        out.append(cleaned)
    return out


def query_bigrams(text: str) -> list[str]:
    """Extract normalized adjacent bigrams from query tokens."""
    toks = tokenize_retrieval(text)
    if len(toks) < 2:
        return []
    return [f"{toks[idx]} {toks[idx + 1]}" for idx in range(len(toks) - 1)]


@dataclass(frozen=True)
class ScoredPassage:
    """One retrieved passage with transparent component scores and method label."""

    passage: dict[str, Any]
    score: float
    bm25_score: float
    dense_score: float | None
    method: str


@dataclass(frozen=True)
class RetrievalResult:
    """Result bundle from lexical, dense, or hybrid passage retrieval."""

    hits: list[ScoredPassage]
    method: str
    dense_available: bool
    dense_model: str | None
    corpus_version: str


class BM25PassageIndex:
    """Pure-Python Robertson/Sparck Jones BM25Okapi index over passage dicts."""

    def __init__(
        self,
        passages: Sequence[dict[str, Any]],
        *,
        k1: float = DEFAULT_BM25_K1,
        b: float = DEFAULT_BM25_B,
    ) -> None:
        self.passages = list(passages)
        self.k1 = k1
        self.b = b
        self.num_docs = len(self.passages)
        self._postings: dict[str, list[tuple[int, int]]] = {}
        self._doc_lens: list[int] = []
        self._idf: dict[str, float] = {}

        total_len = 0
        for idx, entry in enumerate(self.passages):
            text = str(entry.get("text") or entry.get("text_passage") or "")
            toks = tokenize_retrieval(text)
            doc_len = len(toks)
            self._doc_lens.append(doc_len)
            total_len += doc_len
            counts = Counter(toks)
            for term, tf in counts.items():
                self._postings.setdefault(term, []).append((idx, tf))

        self.avgdl = (total_len / self.num_docs) if self.num_docs > 0 else 1.0
        for term, plist in self._postings.items():
            df = len(plist)
            self._idf[term] = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))

    def score_candidates(
        self,
        query: str,
        *,
        allowed_indices: set[int] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[tuple[int, float]]:
        """Return ``(doc_idx, bm25_score)`` pairs sorted descending."""
        q_toks = tokenize_retrieval(query)
        if not q_toks or self.num_docs == 0:
            return []
        scores: dict[int, float] = {}
        for term in set(q_toks):
            plist = self._postings.get(term)
            if not plist:
                continue
            idf = self._idf[term]
            for doc_idx, tf in plist:
                if allowed_indices is not None and doc_idx not in allowed_indices:
                    continue
                dl = self._doc_lens[doc_idx]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / self.avgdl))
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * (tf * (self.k1 + 1.0)) / denom
        ranked = [(idx, sc) for idx, sc in scores.items() if sc > MIN_BM25_SCORE]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        return ranked[:top_k] if top_k > 0 else ranked


class DensePassageEncoder:
    """Genuine neural dense encoder wrapper (never fakes dense embeddings)."""

    def __init__(
        self,
        model_name: str | None = None,
        *,
        encode_fn: Callable[[list[str]], np.ndarray] | None = None,
        local_files_only: bool = True,
        cache_path: Path | None = None,
    ) -> None:
        self.model_name = (
            model_name or os.environ.get(ENV_DENSE_MODEL, "")
        ).strip() or DEFAULT_DENSE_MODEL
        self._encode_fn = encode_fn
        self._local_files_only = local_files_only
        self._cache_path = cache_path
        self._model: Any = None
        self._init_attempted = encode_fn is not None
        self._available = encode_fn is not None
        self._matrix: np.ndarray | None = None

    @property
    def is_available(self) -> bool:
        """True only when a genuine neural encoder is loaded or injected."""
        if not self._init_attempted:
            self._try_load_model()
        return self._available

    def _try_load_model(self) -> None:
        self._init_attempted = True
        env_flag = os.environ.get(ENV_DENSE_ENABLED, "auto").strip().lower()
        if env_flag in {"0", "false", "off", "disabled"}:
            self._available = False
            return
        try:
            from sentence_transformers import SentenceTransformer

            allow_download = env_flag in {"1", "true", "force"}
            self._model = SentenceTransformer(
                self.model_name,
                local_files_only=self._local_files_only and not allow_download,
            )
            self._available = True
        except Exception as exc:
            LOGGER.info(
                "Dense neural encoder %s unavailable (%s); lexical-only mode.", self.model_name, exc
            )
            self._available = False

    def encode(self, texts: Sequence[str]) -> np.ndarray | None:
        """Encode ``texts`` into L2-normalized float32 embeddings, or None if unavailable."""
        if not texts or not self.is_available:
            return None
        text_list = [str(t or "") for t in texts]
        if self._encode_fn is not None:
            vecs = np.asarray(self._encode_fn(text_list), dtype=np.float32)
        elif self._model is not None:
            vecs = np.asarray(
                self._model.encode(text_list, normalize_embeddings=True, show_progress_bar=False),
                dtype=np.float32,
            )
        else:
            return None
        if vecs.ndim == 1:
            vecs = vecs.reshape(1, -1)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.maximum(norms, NORM_EPSILON)
        return (vecs / norms).astype(np.float32, copy=False)

    def build_matrix(self, passages: Sequence[dict[str, Any]]) -> np.ndarray | None:
        """Build or load cached normalized dense passage matrix."""
        if not passages or not self.is_available:
            return None
        if self._matrix is not None and self._matrix.shape[0] == len(passages):
            return self._matrix
        if self._cache_path and self._cache_path.is_file():
            try:
                loaded = np.load(self._cache_path)
                if loaded.ndim == 2 and loaded.shape[0] == len(passages):
                    self._matrix = loaded.astype(np.float32, copy=False)
                    return self._matrix
            except (OSError, ValueError):
                LOGGER.warning("Ignoring corrupt dense cache at %s", self._cache_path)
        texts = [str(p.get("text") or p.get("text_passage") or "") for p in passages]
        mat = self.encode(texts)
        if mat is not None:
            self._matrix = mat
            if self._cache_path:
                try:
                    self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                    np.save(self._cache_path, mat)
                except OSError:
                    LOGGER.warning("Could not persist dense cache to %s", self._cache_path)
        return mat


def _structural_quality_multiplier(entry: dict[str, Any], bigrams: list[str]) -> float:
    """Compute query-specific explanatory vs. intro/TOC/reference reranking multiplier."""
    text = str(entry.get("text") or entry.get("text_passage") or "")
    text_lower = text.lower()
    section = str(entry.get("section_title") or "")
    structural = str(entry.get("structural_class") or "BODY").upper()
    doc_lower = str(entry.get("doc_id") or "").lower()

    mult = 1.0
    if structural != "BODY":
        mult -= NON_BODY_PENALTY
    if _INTRO_SECTION_RE.search(section) or "00_dialogue" in doc_lower:
        mult -= INTRO_FLUFF_PENALTY
    if bigrams and any(bg in text_lower for bg in bigrams):
        mult += PHRASE_MATCH_BOOST
    if _EXPLANATORY_CUE_RE.search(text):
        mult += EXPLANATORY_CHUNK_BOOST
    return max(0.1, mult)


class HybridPassageRetriever:
    """Graph-independent BM25 + genuine neural dense RRF passage retriever."""

    def __init__(
        self,
        passages: Sequence[dict[str, Any]],
        *,
        corpus_version: str = "unknown",
        dense_encoder: DensePassageEncoder | None = None,
        enable_dense: bool | None = None,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self.passages = list(passages)
        self.corpus_version = corpus_version
        self.rrf_k = rrf_k
        self.bm25 = BM25PassageIndex(self.passages)
        if enable_dense is False:
            self.dense_encoder: DensePassageEncoder | None = None
        elif dense_encoder is not None:
            self.dense_encoder = dense_encoder
        else:
            env_flag = os.environ.get(ENV_DENSE_ENABLED, "auto").strip().lower()
            if env_flag in {"0", "false", "off", "disabled"}:
                self.dense_encoder = None
            else:
                self.dense_encoder = DensePassageEncoder()
        self._dense_matrix: np.ndarray | None = None

    @property
    def dense_available(self) -> bool:
        """True only when a genuine neural dense encoder is active."""
        return bool(self.dense_encoder and self.dense_encoder.is_available)

    def _ensure_dense_matrix(self) -> np.ndarray | None:
        if not self.dense_available or self.dense_encoder is None:
            return None
        if self._dense_matrix is None:
            self._dense_matrix = self.dense_encoder.build_matrix(self.passages)
        return self._dense_matrix

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        allowed_indices: set[int] | None = None,
        mode: str = "hybrid",
    ) -> RetrievalResult:
        """Retrieve and rerank passages using honest lexical, dense, or hybrid RRF."""
        if not query or not query.strip() or not self.passages or top_k <= 0:
            return RetrievalResult(
                hits=[],
                method=METHOD_BM25_LEXICAL,
                dense_available=self.dense_available,
                dense_model=self.dense_encoder.model_name
                if self.dense_available and self.dense_encoder
                else None,
                corpus_version=self.corpus_version,
            )

        cand_limit = max(top_k * DEFAULT_CANDIDATE_MULTIPLIER, top_k)
        bigrams = query_bigrams(query)
        use_dense = mode in {"hybrid", "dense"} and self.dense_available
        bm25_ranked = (
            self.bm25.score_candidates(query, allowed_indices=allowed_indices, top_k=cand_limit)
            if mode in {"hybrid", "bm25"} or not use_dense
            else []
        )
        bm25_map = dict(bm25_ranked)

        dense_ranked: list[tuple[int, float]] = []
        dense_map: dict[int, float] = {}
        if use_dense and self.dense_encoder is not None:
            mat = self._ensure_dense_matrix()
            q_vec = self.dense_encoder.encode([query])
            if mat is not None and q_vec is not None:
                sims = (mat @ q_vec[0]).astype(np.float32)
                if allowed_indices is not None:
                    cand_idxs = sorted(allowed_indices)
                    pairs = [
                        (idx, float(sims[idx]))
                        for idx in cand_idxs
                        if float(sims[idx]) >= MIN_DENSE_COSINE
                    ]
                else:
                    pairs = [
                        (int(idx), float(sims[idx]))
                        for idx in np.argsort(-sims)[:cand_limit]
                        if float(sims[idx]) >= MIN_DENSE_COSINE
                    ]
                pairs.sort(key=lambda item: (-item[1], item[0]))
                dense_ranked = pairs[:cand_limit]
                dense_map = dict(dense_ranked)

        if mode == "dense" and not dense_ranked:
            return RetrievalResult(
                hits=[],
                method=METHOD_DENSE_NEURAL if use_dense else METHOD_BM25_LEXICAL,
                dense_available=use_dense,
                dense_model=self.dense_encoder.model_name
                if use_dense and self.dense_encoder
                else None,
                corpus_version=self.corpus_version,
            )

        if dense_ranked and bm25_ranked:
            method = METHOD_HYBRID_BM25_DENSE
            fused: dict[int, float] = {}
            for rank, (idx, _sc) in enumerate(bm25_ranked, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (self.rrf_k + rank)
            for rank, (idx, _sc) in enumerate(dense_ranked, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (self.rrf_k + rank)
            scored_indices = [
                (idx, sc * _structural_quality_multiplier(self.passages[idx], bigrams))
                for idx, sc in fused.items()
            ]
        elif dense_ranked:
            method = METHOD_DENSE_NEURAL
            scored_indices = [
                (idx, sc * _structural_quality_multiplier(self.passages[idx], bigrams))
                for idx, sc in dense_ranked
            ]
        else:
            method = METHOD_BM25_LEXICAL
            scored_indices = [
                (idx, sc * _structural_quality_multiplier(self.passages[idx], bigrams))
                for idx, sc in bm25_ranked
            ]

        scored_indices.sort(key=lambda item: (-item[1], item[0]))
        hits = [
            ScoredPassage(
                passage=self.passages[idx],
                score=round(final_score, 6),
                bm25_score=round(bm25_map.get(idx, 0.0), 6),
                dense_score=round(dense_map[idx], 6) if idx in dense_map else None,
                method=method,
            )
            for idx, final_score in scored_indices[:top_k]
        ]
        return RetrievalResult(
            hits=hits,
            method=method,
            dense_available=bool(dense_ranked),
            dense_model=self.dense_encoder.model_name
            if dense_ranked and self.dense_encoder
            else None,
            corpus_version=self.corpus_version,
        )

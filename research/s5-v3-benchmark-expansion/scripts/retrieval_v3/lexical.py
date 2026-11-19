"""Deterministic pure-Python BM25Okapi lexical control retriever for S5-v3."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
import math

from retrieval_v3.config import DEFAULT_BM25_B, DEFAULT_BM25_K1, DEFAULT_TOP_K
from retrieval_v3.normalization import tokenize_alnum
from retrieval_v3.types import CorpusPassage


class BM25LexicalControl:
    """Pure-Python Robertson/Sparck Jones BM25Okapi control with deterministic tie-breaking."""

    def __init__(
        self,
        passages: Sequence[CorpusPassage],
        *,
        k1: float = DEFAULT_BM25_K1,
        b: float = DEFAULT_BM25_B,
    ) -> None:
        self.passages = list(passages)
        self.k1 = k1
        self.b = b
        self._doc_count = len(self.passages)
        self._doc_term_freqs: list[Counter[str]] = []
        self._doc_lengths: list[int] = []
        self._doc_freq: Counter[str] = Counter()

        for passage in self.passages:
            tokens = tokenize_alnum(passage.text)
            tf = Counter(tokens)
            self._doc_term_freqs.append(tf)
            self._doc_lengths.append(len(tokens))
            for term in tf:
                self._doc_freq[term] += 1

        self._avg_doc_len = sum(self._doc_lengths) / self._doc_count if self._doc_count > 0 else 1.0

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        if df == 0 or self._doc_count == 0:
            return 0.0
        # Standard Robertson-Sparck Jones IDF with +1 floor for non-negativity
        return math.log(1.0 + (self._doc_count - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[tuple[str, float]]:
        """Score all passages and return top_k (passage_id, score) pairs deterministically."""
        if self._doc_count == 0 or top_k <= 0:
            return []

        query_terms = tokenize_alnum(query)
        if not query_terms:
            return []

        scored: list[tuple[str, float]] = []
        for idx, passage in enumerate(self.passages):
            tf_map = self._doc_term_freqs[idx]
            doc_len = self._doc_lengths[idx]
            norm_denom = self.k1 * (1.0 - self.b + self.b * (doc_len / self._avg_doc_len))
            score = 0.0
            for term in query_terms:
                tf = tf_map.get(term, 0)
                if tf == 0:
                    continue
                idf = self._idf(term)
                score += idf * ((tf * (self.k1 + 1.0)) / (tf + norm_denom))
            if score > 0.0:
                scored.append((passage.passage_id, score))

        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]

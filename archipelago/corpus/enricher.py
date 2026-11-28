"""Domain assignment, concept association, and lexical/dense indexing support.

Associates each validated passage with canonical domain labels and OKF graph
concepts (read-only from ``okf_graph.json``), and produces a compact lexical
inverted-index summary alongside dense-embedding readiness metadata.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from archipelago.corpus.catalog import SourceSpec
from archipelago.corpus.segmenter import PassageRecord

MIN_CONCEPT_LABEL_LEN = 4
MAX_CONCEPTS_PER_PASSAGE = 8
MIN_TOKEN_LEN = 3
TOP_LEXICAL_TERMS_LIMIT = 50
DENSE_EMBEDDING_MODEL = "Snowflake/snowflake-arctic-embed-m-v1.5"
DENSE_EMBEDDING_DIM = 768

_TOKEN_RE = re.compile(r"[a-z][a-z0-9_+-]{2,}")
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "with",
        "this",
        "from",
        "are",
        "was",
        "were",
        "have",
        "has",
        "had",
        "not",
        "but",
        "can",
        "will",
        "which",
        "their",
        "there",
        "when",
        "where",
        "into",
        "than",
        "then",
        "also",
        "such",
        "each",
        "more",
        "most",
        "other",
        "some",
        "only",
        "using",
        "used",
        "between",
        "about",
        "these",
        "those",
        "page",
        "section",
        "chapter",
        "figure",
        "table",
    }
)


@dataclass(frozen=True)
class ConceptMatcher:
    """Fast substring/word-boundary concept matcher built from okf_graph.json."""

    concept_terms: tuple[tuple[str, str], ...]  # (lowercased_label, concept_id)

    @classmethod
    def from_graph_path(cls, graph_path: Path) -> ConceptMatcher:
        """Load concept labels from ``okf_graph.json`` without mutating it."""
        if not graph_path.is_file():
            return cls(concept_terms=())
        payload = json.loads(graph_path.read_text(encoding="utf-8"))
        nodes = payload.get("nodes") or payload.get("concepts") or []
        entries: list[tuple[str, str]] = []
        iterable = nodes.values() if isinstance(nodes, dict) else nodes
        for node in iterable:
            if not isinstance(node, dict):
                continue
            cid = str(node.get("id") or "").strip()
            label = str(node.get("label") or "").strip().lower()
            if cid and len(label) >= MIN_CONCEPT_LABEL_LEN:
                entries.append((label, cid))
        # Longest labels first so specific concepts match before generic prefixes.
        entries.sort(key=lambda item: len(item[0]), reverse=True)
        return cls(concept_terms=tuple(entries))

    def match_concepts(self, text: str) -> list[str]:
        """Return up to ``MAX_CONCEPTS_PER_PASSAGE`` matched concept IDs."""
        lowered = text.lower()
        matched: list[str] = []
        seen: set[str] = set()
        for label, cid in self.concept_terms:
            if cid in seen:
                continue
            if label in lowered:
                matched.append(cid)
                seen.add(cid)
                if len(matched) >= MAX_CONCEPTS_PER_PASSAGE:
                    break
        return matched


def tokenize_lexical(text: str) -> list[str]:
    """Extract normalized lexical index tokens from passage text."""
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) >= MIN_TOKEN_LEN and tok not in _STOPWORDS
    ]


def build_jsonl_record(
    passage: PassageRecord,
    spec: SourceSpec,
    concept_ids: list[str],
    corpus_version: str,
) -> dict[str, Any]:
    """Build a runtime-compatible JSONL passage record with D14 metadata."""
    return {
        "corpus_version": corpus_version,
        "passage_id": passage.passage_id,
        "doc_id": passage.doc_id,
        "source_id": passage.source_id,
        "source_title": spec.title,
        "authors": spec.authors,
        "license": spec.license_name,
        "domain": spec.domain,
        "secondary_domains": list(spec.secondary_domains),
        "pdf_sha256": passage.pdf_sha256,
        "page_number": passage.page_number,
        "pdf_page_index": passage.pdf_page_index,
        "printed_page": passage.printed_page,
        "page_offset": passage.page_offset,
        "section_title": passage.section_title,
        "structural_class": passage.structural_class.value,
        "text_offset_start": passage.text_offset_start,
        "text_offset_end": passage.text_offset_end,
        "word_count": passage.word_count,
        "quality_score": passage.quality_score,
        "concept_ids": concept_ids,
        "text": passage.text,
    }


class LexicalIndexAccumulator:
    """Streaming lexical DF/TF accumulator for corpus_v3_d14 index statistics."""

    def __init__(self) -> None:
        self.doc_freq: Counter[str] = Counter()
        self.total_tokens: int = 0
        self.passage_count: int = 0
        self.concept_linked_passages: int = 0

    def add(self, text: str, concept_ids: list[str]) -> None:
        """Update lexical statistics with one passage."""
        tokens = tokenize_lexical(text)
        self.passage_count += 1
        self.total_tokens += len(tokens)
        if concept_ids:
            self.concept_linked_passages += 1
        for unique_tok in set(tokens):
            self.doc_freq[unique_tok] += 1

    def summary(self) -> dict[str, Any]:
        """Return serializable lexical and dense-index readiness metadata."""
        return {
            "lexical_index": {
                "tokenizer": "alnum_min3_stopword_filtered",
                "vocabulary_size": len(self.doc_freq),
                "total_tokens": self.total_tokens,
                "indexed_passages": self.passage_count,
                "concept_linked_passages": self.concept_linked_passages,
                "top_terms": [
                    {"term": term, "df": count}
                    for term, count in self.doc_freq.most_common(TOP_LEXICAL_TERMS_LIMIT)
                ],
            },
            "dense_index_contract": {
                "recommended_model": DENSE_EMBEDDING_MODEL,
                "embedding_dim": DENSE_EMBEDDING_DIM,
                "passage_id_field": "passage_id",
                "text_field": "text",
                "status": "READY_FOR_EMBEDDING",
            },
        }

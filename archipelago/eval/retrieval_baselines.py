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


_INDEX_DOC_RE = re.compile(r"(?:^|/)(?:index|about[-_]the[-_]authors|table[-_]of[-_]contents)[_/-]", re.IGNORECASE)
_INDEX_LINE_NUM_RE = re.compile(r"\b\d{1,4}(?:,\s*\d{1,4}){4,}")


def _is_index_only_passage(doc_id: str, section_title: str, text: str) -> bool:
    if _INDEX_DOC_RE.search(doc_id):
        return True
    sec = section_title.strip().lower()
    if sec in {"index", "subject index", "author index", "about the authors", "table of contents"}:
        return True
    if len(_INDEX_LINE_NUM_RE.findall(text)) >= 3 and len(text) < 2500:
        return True
    return False


def audit_corpus_quality(
    passages: Sequence[Passage],
    *,
    raw_doc_ids_by_canonical: dict[str, set[str]] | None = None,
    doc_provenance_by_canonical: dict[str, dict[str, Any]] | None = None,
    missing_provenance_chunks: int = 0,
    invalid_provenance_chunks: int = 0,
    empty_text_chunks: int = 0,
    duplicate_passages_removed: int = 0,
) -> dict[str, Any]:
    """Audit corpus quality without silently deleting flagged records.

    Detects:
    - index-only / frontmatter passages
    - missing or invalid page numbers (<= 0 or > document page_count)
    - duplicate document identities collapsing under normalize_doc_id
    - one-chunk source documents
    - text lacking independently verifiable PDF provenance (missing doc_hash or pdf_url)
    """
    doc_counts: Counter[str] = Counter(p.doc_id for p in passages)
    one_chunk_docs = sorted(did for did, cnt in doc_counts.items() if cnt == 1)

    invalid_page_passages: list[dict[str, Any]] = []
    index_only_passages: list[str] = []
    missing_pdf_prov_passages = 0
    missing_pdf_prov_docs: set[str] = set()

    for p in passages:
        doc_meta = (doc_provenance_by_canonical or {}).get(p.doc_id, {})
        page_count = doc_meta.get("page_count")
        if p.page_number is None or p.page_number < 1:
            invalid_page_passages.append(
                {"passage_id": p.passage_id, "page_number": p.page_number, "reason": "page_number_lt_1"}
            )
        elif isinstance(page_count, int) and page_count > 0 and p.page_number > page_count:
            invalid_page_passages.append(
                {
                    "passage_id": p.passage_id,
                    "page_number": p.page_number,
                    "page_count": page_count,
                    "reason": "page_number_exceeds_page_count",
                }
            )

        if _is_index_only_passage(p.doc_id, p.section_title, p.text):
            index_only_passages.append(p.passage_id)

        if doc_provenance_by_canonical is not None:
            has_hash = bool(doc_meta.get("doc_hash"))
            has_url = bool(doc_meta.get("pdf_url"))
            if not (has_hash and has_url):
                missing_pdf_prov_passages += 1
                missing_pdf_prov_docs.add(p.doc_id)

    duplicate_doc_identities = {
        canon: sorted(raw_ids)
        for canon, raw_ids in sorted((raw_doc_ids_by_canonical or {}).items())
        if len(raw_ids) > 1
    }

    return {
        "missing_provenance_chunks": missing_provenance_chunks,
        "invalid_provenance_chunks": invalid_provenance_chunks,
        "empty_text_chunks": empty_text_chunks,
        "duplicate_passages_removed": duplicate_passages_removed,
        "invalid_page_number_count": len(invalid_page_passages),
        "invalid_page_numbers": invalid_page_passages,
        "duplicate_document_identity_count": len(duplicate_doc_identities),
        "duplicate_document_identities": duplicate_doc_identities,
        "one_chunk_document_count": len(one_chunk_docs),
        "one_chunk_documents": one_chunk_docs,
        "index_only_passage_count": len(index_only_passages),
        "index_only_passages": index_only_passages,
        "missing_verifiable_pdf_provenance_passages": missing_pdf_prov_passages,
        "missing_verifiable_pdf_provenance_docs": sorted(missing_pdf_prov_docs),
        "inclusion_exclusion_policy": {
            "excluded_at_ingest": [
                "orphan_chunks_missing_document_edge",
                "empty_or_whitespace_passages",
                "missing_doc_id_or_chunk_id",
                "exact_normalized_sha256_duplicates",
            ],
            "retained_and_flagged_for_audit": [
                "index_only_passages",
                "one_chunk_documents",
                "passages_missing_doc_hash_or_pdf_url",
                "invalid_page_numbers",
            ],
            "rationale": (
                "Flagged records are retained in s3_fixed_corpus_v1 so baseline runs "
                "cannot silently cherry-pick the corpus; CIKM ablations may filter "
                "flagged subsets explicitly using this audit manifest."
            ),
        },
    }


def build_fixed_corpus_from_kuzu(
    db_path: str | Path,
    *,
    corpus_version: str = "s3_fixed_corpus_v1",
) -> tuple[list[Passage], dict[str, Any]]:
    """Build a deterministic, deduplicated, provenance-verified passage corpus.

    Rejects orphan chunks (missing Document -[:HAS_CHUNK]-> Chunk provenance)
    and empty passages, deduplicates identical normalized passage text, audits
    corpus quality without silent deletion, and returns (passages, corpus_manifest).
    """
    import kuzu

    resolved_db = Path(db_path)
    db = kuzu.Database(str(resolved_db), read_only=True)
    conn = kuzu.Connection(db)

    total_res = conn.execute("MATCH (c:Chunk) RETURN count(c)")
    total_chunk_nodes = int(total_res.get_next()[0]) if total_res.has_next() else 0

    res = conn.execute(
        "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) "
        "RETURN d.id, d.doc_hash, d.pdf_url, d.page_count, "
        "c.chunk_id, c.page_number, c.section_title, c.text_passage"
    )
    linked_rows: list[tuple[str, str, int, str, str]] = []
    raw_doc_ids_by_canonical: dict[str, set[str]] = {}
    doc_provenance_by_canonical: dict[str, dict[str, Any]] = {}

    while res.has_next():
        doc_id_raw, doc_hash_raw, pdf_url_raw, page_count_raw, chunk_id_raw, page_raw, section_raw, text_raw = res.get_next()
        raw_doc_str = str(doc_id_raw or "").strip()
        canon_doc_id = normalize_doc_id(raw_doc_str)
        if canon_doc_id:
            raw_doc_ids_by_canonical.setdefault(canon_doc_id, set()).add(raw_doc_str)
            meta = doc_provenance_by_canonical.setdefault(
                canon_doc_id,
                {"doc_hash": None, "pdf_url": None, "page_count": None},
            )
            if doc_hash_raw and not meta["doc_hash"]:
                meta["doc_hash"] = str(doc_hash_raw).strip()
            if pdf_url_raw and not meta["pdf_url"]:
                meta["pdf_url"] = str(pdf_url_raw).strip()
            if page_count_raw is not None and meta["page_count"] is None:
                meta["page_count"] = int(page_count_raw)

        linked_rows.append(
            (
                canon_doc_id,
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

    quality_audit = audit_corpus_quality(
        passages,
        raw_doc_ids_by_canonical=raw_doc_ids_by_canonical,
        doc_provenance_by_canonical=doc_provenance_by_canonical,
        missing_provenance_chunks=missing_provenance_chunks,
        invalid_provenance_chunks=invalid_provenance_chunks,
        empty_text_chunks=empty_text_chunks,
        duplicate_passages_removed=duplicate_passages_removed,
    )

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
        "corpus_quality_audit": quality_audit,
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


VALID_REVIEW_STATUSES = frozenset(
    {
        "UNVERIFIED_CANDIDATE",
        "SINGLE_ANNOTATED",
        "DOUBLE_ANNOTATED_DISAGREEMENT",
        "ADJUDICATED_GOLD",
    }
)

VALID_ANSWERABILITY_STATUSES = frozenset(
    {
        "ANSWERABLE",
        "PARTIALLY_ANSWERABLE",
        "UNANSWERABLE_OUT_OF_CORPUS",
        "PENDING_ANNOTATION",
    }
)


def _resolve_passage_from_ref(
    ref: Any,
    passage_by_id: dict[str, Passage],
    doc_chunk_index: dict[tuple[str, str], list[Passage]],
) -> tuple[str | None, str | None]:
    """Validate a gold_supporting_passages object and resolve its canonical passage_id."""
    if not isinstance(ref, dict):
        return None, "supporting_passage_not_object"

    raw_doc_id = ref.get("doc_id")
    raw_chunk_id = ref.get("chunk_id")
    page_num = ref.get("page_number")

    if not isinstance(raw_doc_id, str) or not raw_doc_id.strip():
        return None, "missing_or_invalid_doc_id"
    if not isinstance(raw_chunk_id, str) or not raw_chunk_id.strip():
        return None, "missing_or_invalid_chunk_id"
    if isinstance(page_num, bool) or not isinstance(page_num, int) or page_num < 1:
        return None, f"invalid_page_number:{page_num}"

    norm_doc = normalize_doc_id(raw_doc_id)
    chunk_id = raw_chunk_id.strip()
    direct_pid = f"{norm_doc}::{chunk_id}"
    if direct_pid in passage_by_id:
        p = passage_by_id[direct_pid]
        if p.page_number != page_num:
            return None, f"page_mismatch:{direct_pid}:expected_{p.page_number}_got_{page_num}"
        return direct_pid, None

    candidates = doc_chunk_index.get((norm_doc, chunk_id), [])
    for p in candidates:
        if p.page_number == page_num:
            return p.passage_id, None
    if candidates:
        return None, f"page_mismatch:{norm_doc}::{chunk_id}:got_{page_num}"
    return None, f"passage_not_found:{direct_pid}"


def build_qrels_from_records(
    queries: Sequence[dict[str, Any]],
    passage_by_id: dict[str, Passage],
) -> dict[str, Any]:
    """Build validated graded qrels (0/1/2) from schema-compliant benchmark records.

    Only records with ``review_status == 'ADJUDICATED_GOLD'`` are accepted as
    gold. ``UNANSWERABLE_OUT_OF_CORPUS`` queries are separated explicitly and
    never mixed into answerable qrels.
    """
    doc_chunk_index: dict[tuple[str, str], list[Passage]] = {}
    for p in passage_by_id.values():
        doc_chunk_index.setdefault((p.doc_id, p.chunk_id), []).append(p)

    answerable_qrels: dict[str, dict[str, float]] = {}
    unanswerable_query_ids: list[str] = []
    validation_errors: list[dict[str, Any]] = []
    adjudicated_count = 0

    for idx, q in enumerate(queries):
        qid = str(q.get("query_id") or f"row_{idx}")
        review_status = q.get("review_status")
        if review_status not in VALID_REVIEW_STATUSES:
            validation_errors.append(
                {
                    "query_id": qid,
                    "error": f"invalid_review_status:{review_status}",
                }
            )
            continue

        if review_status != "ADJUDICATED_GOLD":
            continue

        adjudicated_count += 1
        ans_status = q.get("answerability_status")
        if ans_status not in VALID_ANSWERABILITY_STATUSES:
            validation_errors.append(
                {
                    "query_id": qid,
                    "error": f"invalid_answerability_status:{ans_status}",
                }
            )
            continue

        is_unanswerable = (
            ans_status == "UNANSWERABLE_OUT_OF_CORPUS"
            or q.get("question_category") == "unanswerable_out_of_corpus"
        )

        supporting_refs = q.get("gold_supporting_passages") or []
        raw_labels = q.get("relevant_passage_labels") or {}

        if is_unanswerable:
            has_pos_label = (
                isinstance(raw_labels, dict)
                and any(not isinstance(v, bool) and isinstance(v, int) and v > 0 for v in raw_labels.values())
            )
            if supporting_refs or has_pos_label:
                validation_errors.append(
                    {
                        "query_id": qid,
                        "error": "unanswerable_query_has_positive_gold",
                    }
                )
            else:
                unanswerable_query_ids.append(qid)
            continue

        if not isinstance(supporting_refs, list):
            validation_errors.append({"query_id": qid, "error": "gold_supporting_passages_not_list"})
            continue
        if not isinstance(raw_labels, dict):
            validation_errors.append({"query_id": qid, "error": "relevant_passage_labels_not_object"})
            continue

        q_grades: dict[str, float] = {}
        query_has_error = False

        for pid_raw, grade in raw_labels.items():
            if isinstance(grade, bool) or not isinstance(grade, int) or grade not in (0, 1, 2):
                validation_errors.append(
                    {
                        "query_id": qid,
                        "error": f"invalid_relevance_grade:{pid_raw}={grade}",
                    }
                )
                query_has_error = True
                continue
            pid_str = str(pid_raw)
            if pid_str not in passage_by_id and "::" in pid_str:
                raw_d, raw_c = pid_str.split("::", 1)
                pid_str = f"{normalize_doc_id(raw_d)}::{raw_c.strip()}"
            if pid_str not in passage_by_id:
                validation_errors.append(
                    {
                        "query_id": qid,
                        "error": f"label_passage_not_found:{pid_raw}",
                    }
                )
                query_has_error = True
                continue
            q_grades[pid_str] = float(grade)

        for ref in supporting_refs:
            resolved_pid, err = _resolve_passage_from_ref(ref, passage_by_id, doc_chunk_index)
            if err is not None or resolved_pid is None:
                validation_errors.append({"query_id": qid, "error": err or "unresolved_passage"})
                query_has_error = True
                continue
            if resolved_pid not in q_grades:
                q_grades[resolved_pid] = 2.0

        if query_has_error:
            continue

        if not any(g > 0.0 for g in q_grades.values()):
            validation_errors.append(
                {
                    "query_id": qid,
                    "error": "adjudicated_answerable_query_missing_positive_relevance",
                }
            )
            continue

        answerable_qrels[qid] = q_grades

    return {
        "status": "ADJUDICATED_GOLD_AVAILABLE" if answerable_qrels else "NO_HUMAN_GOLD",
        "adjudicated_gold_queries": adjudicated_count,
        "evaluable_answerable_queries": len(answerable_qrels),
        "unanswerable_queries": len(unanswerable_query_ids),
        "unanswerable_query_ids": unanswerable_query_ids,
        "answerable_qrels": answerable_qrels,
        "validation_errors": validation_errors,
    }


def evaluate_retrieval_systems(
    passages: Sequence[Passage],
    queries: Sequence[dict[str, Any]],
    bm25: BM25Retriever,
    dense: DenseRetriever,
    *,
    rrf_k: int = DEFAULT_RRF_K,
    top_k: int = 10,
    ks: Sequence[int] = (1, 3, 5, 10),
) -> dict[str, Any]:
    """Run BM25, Dense, and Hybrid RRF over queries and evaluate against adjudicated qrels."""
    passage_by_id = {p.passage_id: p for p in passages}
    qrels_bundle = build_qrels_from_records(queries, passage_by_id)

    rankings_by_system: dict[str, dict[str, list[str]]] = {
        "bm25": {},
        "dense": {},
        "hybrid_rrf": {},
    }
    scored_results: dict[str, dict[str, list[tuple[str, float]]]] = {}
    bm25_lat_ms: list[float] = []
    dense_lat_ms: list[float] = []
    rrf_lat_ms: list[float] = []

    import time

    for q in queries:
        qid = q["query_id"]
        question = q["question"]

        t0 = time.perf_counter()
        bm25_full = bm25.score_all(question)
        bm25_lat_ms.append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        dense_full = dense.score_all(question)
        dense_lat_ms.append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        rrf_top = rrf_fuse([bm25_full, dense_full], k=rrf_k, top_k=top_k)
        rrf_lat_ms.append((time.perf_counter() - t0) * 1000.0)

        rankings_by_system["bm25"][qid] = [pid for pid, _ in bm25_full]
        rankings_by_system["dense"][qid] = [pid for pid, _ in dense_full]
        rankings_by_system["hybrid_rrf"][qid] = [pid for pid, _ in rrf_top]

        scored_results[qid] = {
            "bm25": bm25_full[:top_k],
            "dense": dense_full[:top_k],
            "hybrid_rrf": rrf_top,
        }

    answerable_qrels = qrels_bundle["answerable_qrels"]
    per_system_eval = {
        sys_name: evaluate_rankings(rankings_by_system[sys_name], answerable_qrels, ks=ks)
        for sys_name in ("bm25", "dense", "hybrid_rrf")
    }

    return {
        "qrels_bundle": qrels_bundle,
        "per_system_evaluation": per_system_eval,
        "scored_results": scored_results,
        "latencies_ms": {
            "bm25": bm25_lat_ms,
            "dense": dense_lat_ms,
            "hybrid_rrf": rrf_lat_ms,
        },
    }

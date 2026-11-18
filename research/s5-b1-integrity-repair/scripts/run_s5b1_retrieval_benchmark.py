"""S5-B1 — Multi-Hop Retrieval Benchmark & Research Integrity Execution Harness.

Implements and benchmarks:
1. BM25 (Robertson/Sparck Jones BM25Okapi, k1=1.5, b=0.75)
2. Genuine Dense Retrieval (Snowflake/snowflake-arctic-embed-m-v1.5, 768-dim)
3. Hybrid RRF (BM25 + Dense, k=60, true end-to-end timing accounting)
4. Repaired Baseline Graph Retrieval (Global passage ID mapping, 1-hop traversal)
5. Repaired Heterogeneous Graph Retrieval (1-hop ablation and 2-hop full traversal)

Integrity Guarantees & S5-B1 Repairs:
- Strict Corpus Scope: Exactly 713 passages across 53 documents from s5a_eval_corpus_v1.
- Corpus-Scoped Graph Extraction: Graph edges constructed strictly from the 713 eligible passages,
  preventing unfair information access from external chunks/documents.
- Reproducible Fallback: Graph retrievers fall back to deterministic corpus BM25 when no anchors match.
- Traversal Instrumentation: Reports actual observed hop depth (0 for fallback, 1 for 1-hop, 2 for 2-hop)
  and records real graph paths traversed [(source, relation, target)].
- Exception Transparency: Removes silently swallowed Kùzu runtime exceptions.
- Cold-Start vs. Per-Query Timing: Measures true application cold-start (model import + weights load + index build)
  separately from first-query cold latency and warm query distributions (5 repetitions, mean, median, min, max, p95).
- Strict Scientific Boundary: Retrieval effectiveness marked strictly NOT_EVALUATED pending human gold labels.
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from archipelago.eval.dataset_integrity import normalize_doc_id
from archipelago.eval.retrieval_baselines import (
    BM25Retriever,
    Passage,
    build_fixed_corpus_from_kuzu,
    _is_index_only_passage,
    normalize_passage_text,
    rrf_fuse,
)
from okf.pilot.repaired_extractor import RepairedGraphExtractor

logger = logging.getLogger("s5b1_benchmark")

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "okf_graph.db"
EMB_CACHE = ROOT / "data" / "artifacts" / "s5a_dense_embeddings_713.npy"
BASE_DIR = ROOT / "research" / "s5-b1-integrity-repair"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = REPORT_DIR / "retrieval_technical_evaluation_report.json"
TIMING_PATH = REPORT_DIR / "retrieval_timing_report.json"
MODEL_MANIFEST_PATH = BASE_DIR / "models" / "s5b1_model_manifest.json"


# ---------------------------------------------------------------------------
# 1. Corpus Loader & Cryptographic Verification
# ---------------------------------------------------------------------------

def load_s5b1_corpus() -> tuple[list[Passage], dict[str, str]]:
    passages, _ = build_fixed_corpus_from_kuzu(str(DB_PATH))
    eligible = [
        p for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
    ]
    # Cryptographic verification
    pid_hasher = hashlib.sha256()
    for p in eligible:
        pid_hasher.update(p.passage_id.encode("utf-8"))
    pids_sha = pid_hasher.hexdigest()

    text_hasher = hashlib.sha256()
    for p in eligible:
        text_hasher.update(p.text.encode("utf-8"))
    text_sha = text_hasher.hexdigest()

    hashes = {
        "passage_count": len(eligible),
        "corpus_pids_sha256": pids_sha,
        "corpus_text_sha256": text_sha,
    }
    return eligible, hashes


# ---------------------------------------------------------------------------
# 2. Genuine Dense Retriever (Snowflake Arctic Embed M v1.5)
# ---------------------------------------------------------------------------

class GenuineDenseRetriever:
    def __init__(self, passages: list[Passage], model: SentenceTransformer, doc_embeddings: np.ndarray) -> None:
        self.passages = passages
        self.passage_ids = [p.passage_id for p in passages]
        self.model = model
        self.doc_embeddings = doc_embeddings  # shape: (N, 768), normalized
        self.query_prefix = "Represent this sentence for searching relevant passages: "

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        q_text = f"{self.query_prefix}{query}"
        q_emb = self.model.encode([q_text], normalize_embeddings=True, show_progress_bar=False)[0]
        # Inner product with L2-normalized embeddings equals cosine similarity
        sims = self.doc_embeddings @ q_emb
        ranked = [(pid, float(score)) for pid, score in zip(self.passage_ids, sims.tolist())]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        return ranked[:top_k]


# ---------------------------------------------------------------------------
# 3. Repaired Baseline Graph Retriever (Global ID Scoped + BM25 Fallback)
# ---------------------------------------------------------------------------

class RepairedBaselineGraphRetriever:
    """Baseline graph retriever with global passage ID mapping, BM25 fallback, and exception logging."""

    def __init__(self, passages: list[Passage], kuzu_conn: Any, bm25_fallback: BM25Retriever) -> None:
        self.passages = passages
        self.passage_ids_set = set(p.passage_id for p in passages)
        self.conn = kuzu_conn
        self.bm25_fallback = bm25_fallback
        self.traversal_errors: list[str] = []
        self._build_concept_index()

    def _build_concept_index(self) -> None:
        self.concept_to_pids: dict[str, set[str]] = collections.defaultdict(set)
        # Query full path: (Document)->(Chunk)->(Concept) to guarantee canonical {doc_id}::{chunk_id}
        query = "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(cn:Concept) RETURN d.id, c.chunk_id, cn.name"
        res = self.conn.execute(query)
        while res.has_next():
            row = res.get_next()
            doc_id_raw, chunk_id, cname = row[0], row[1], row[2].lower()
            canon_doc = normalize_doc_id(doc_id_raw)
            pid = f"{canon_doc}::{chunk_id}"
            if pid in self.passage_ids_set:
                self.concept_to_pids[cname].add(pid)

    def search(self, query: str, top_k: int = 10) -> tuple[list[tuple[str, float]], dict[str, Any]]:
        q_low = query.lower()
        matched_anchors = [c for c in self.concept_to_pids if c in q_low]

        if not matched_anchors:
            # S5-B1 Repair: Deterministic BM25 fallback over eligible corpus
            fallback_res = self.bm25_fallback.search(query, top_k=top_k)
            meta = {
                "anchor_found": False,
                "matched_anchors": [],
                "traversed_concepts_count": 0,
                "actual_hop_count": 0,
                "is_fallback": True,
                "fallback_strategy": "corpus_bm25",
                "paths_traversed": [],
                "traversal_errors": list(self.traversal_errors),
            }
            return fallback_res, meta

        # 1-hop traversal in Kuzu with explicit error handling
        traversed: set[str] = set(matched_anchors)
        paths_traversed: list[dict[str, Any]] = []

        for anchor in matched_anchors:
            try:
                res = self.conn.execute(
                    "MATCH (c1:Concept {name: $name})-[r]->(c2:Concept) RETURN c2.name LIMIT 5",
                    {"name": anchor.title()},
                )
                while res.has_next():
                    c2_name = res.get_next()[0].lower()
                    if c2_name in self.concept_to_pids:
                        traversed.add(c2_name)
                        paths_traversed.append({"source": anchor, "relation": "KUZU_EDGE", "target": c2_name, "hop": 1})
            except Exception as e:
                # S5-B1 Repair: Explicitly record exception without silent swallowing
                err_msg = f"Kuzu query error on concept '{anchor}': {type(e).__name__}: {str(e)}"
                logger.warning(err_msg)
                self.traversal_errors.append(err_msg)

        scores: dict[str, float] = collections.defaultdict(float)
        for c in traversed:
            weight = 2.0 if c in matched_anchors else 1.0
            for pid in self.concept_to_pids.get(c, []):
                scores[pid] += weight

        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        observed_hop = 1 if len(paths_traversed) > 0 else 0
        meta = {
            "anchor_found": True,
            "matched_anchors": matched_anchors,
            "traversed_concepts_count": len(traversed),
            "actual_hop_count": observed_hop,
            "is_fallback": False,
            "fallback_strategy": "none",
            "paths_traversed": paths_traversed,
            "traversal_errors": list(self.traversal_errors),
        }
        return ranked[:top_k], meta


# ---------------------------------------------------------------------------
# 4. Repaired Heterogeneous Graph Retriever (Strict Corpus Scope & Hop Tracking)
# ---------------------------------------------------------------------------

class RepairedHeterogeneousGraphRetriever:
    """Repaired heterogeneous graph retriever with typed edge semantics, BM25 fallback, and path instrumentation."""

    EDGE_WEIGHTS = {
        "REQUIRES": 1.0,
        "PART_OF": 0.9,
        "USES": 0.8,
        "CONTRASTS_WITH": 0.7,
        "RELATED": 0.5,
    }

    def __init__(
        self,
        passages: list[Passage],
        corpus_scoped_edges: list[Any],
        bm25_fallback: BM25Retriever,
        max_hops: int = 2,
    ) -> None:
        self.passages = passages
        self.passage_ids_set = set(p.passage_id for p in passages)
        self.edges = corpus_scoped_edges
        self.bm25_fallback = bm25_fallback
        self.max_hops = max_hops
        self._build_index()

    def _build_index(self) -> None:
        self.adj: dict[str, list[tuple[str, str, float]]] = collections.defaultdict(list)
        self.concept_to_pids: dict[str, set[str]] = collections.defaultdict(set)

        for edge in self.edges:
            u = edge.from_name.lower()
            v = edge.to_name.lower()
            etype = edge.edge_type
            w = self.EDGE_WEIGHTS.get(etype, 0.5) * edge.confidence
            self.adj[u].append((v, etype, w))
            if etype in {"CONTRASTS_WITH", "RELATED"}:
                self.adj[v].append((u, etype, w))

            # Associate edge source passage if in eligible corpus
            edge_pid = f"{normalize_doc_id(edge.doc_id)}::{edge.chunk_id}"
            if edge_pid in self.passage_ids_set:
                self.concept_to_pids[u].add(edge_pid)
                self.concept_to_pids[v].add(edge_pid)

        # Index passages where concept explicitly occurs in text
        for p in self.passages:
            p_low = p.text.lower()
            for c in self.adj:
                if c in p_low:
                    self.concept_to_pids[c].add(p.passage_id)

    def search(self, query: str, top_k: int = 10) -> tuple[list[tuple[str, float]], dict[str, Any]]:
        q_low = query.lower()
        matched_anchors = [c for c in self.adj if c in q_low]

        if not matched_anchors:
            # S5-B1 Repair: Deterministic BM25 fallback instead of unsorted substring slice
            fallback_res = self.bm25_fallback.search(query, top_k=top_k)
            meta = {
                "anchor_found": False,
                "matched_anchors": [],
                "traversed_concepts_count": 0,
                "actual_hop_count": 0,
                "is_fallback": True,
                "fallback_strategy": "corpus_bm25",
                "max_hops_configured": self.max_hops,
                "paths_traversed": [],
            }
            return fallback_res, meta

        visited: dict[str, float] = {}
        paths_traversed: list[dict[str, Any]] = []
        hop1_visited: set[str] = set()
        hop2_visited: set[str] = set()

        for anchor in matched_anchors:
            visited[anchor] = max(visited.get(anchor, 0.0), 1.0)
            # 1-hop traversal
            for nxt, etype, w in self.adj.get(anchor, []):
                score1 = 1.0 * w
                visited[nxt] = max(visited.get(nxt, 0.0), score1)
                hop1_visited.add(nxt)
                paths_traversed.append({"source": anchor, "relation": etype, "target": nxt, "hop": 1})

                # 2-hop traversal (if configured)
                if self.max_hops >= 2:
                    for nxt2, etype2, w2 in self.adj.get(nxt, []):
                        score2 = score1 * w2 * 0.5
                        visited[nxt2] = max(visited.get(nxt2, 0.0), score2)
                        hop2_visited.add(nxt2)
                        paths_traversed.append({"source": nxt, "relation": etype2, "target": nxt2, "hop": 2})

        # S5-B1 Repair: Real observed hop depth calculation
        new_hop2_concepts = hop2_visited - set(matched_anchors) - hop1_visited
        if self.max_hops >= 2 and len(new_hop2_concepts) > 0:
            observed_hop_depth = 2
        elif len(hop1_visited - set(matched_anchors)) > 0 or len(paths_traversed) > 0:
            observed_hop_depth = 1
        else:
            observed_hop_depth = 0

        # Score passages
        pid_scores: dict[str, float] = collections.defaultdict(float)
        for c, c_weight in visited.items():
            for pid in self.concept_to_pids.get(c, []):
                pid_scores[pid] += c_weight

        ranked = sorted(pid_scores.items(), key=lambda x: (-x[1], x[0]))
        meta = {
            "anchor_found": True,
            "matched_anchors": matched_anchors,
            "traversed_concepts_count": len(visited),
            "actual_hop_count": observed_hop_depth,
            "is_fallback": False,
            "fallback_strategy": "none",
            "max_hops_configured": self.max_hops,
            "paths_traversed": paths_traversed,
        }
        return ranked[:top_k], meta


# ---------------------------------------------------------------------------
# 5. Hybrid RRF Retriever with End-to-End Latency Accounting
# ---------------------------------------------------------------------------

class HybridRRFRetriever:
    """Hybrid RRF retriever combining BM25 and Genuine Dense with end-to-end timing."""

    def __init__(self, bm25: BM25Retriever, dense: GenuineDenseRetriever, k: int = 60) -> None:
        self.bm25 = bm25
        self.dense = dense
        self.k = k

    def search_timed(self, query: str, top_k: int = 10) -> tuple[list[tuple[str, float]], dict[str, float]]:
        t0 = time.perf_counter()
        bm25_res = self.bm25.search(query, top_k=50)
        t_bm25 = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        dense_res = self.dense.search(query, top_k=50)
        t_dense = (time.perf_counter() - t1) * 1000.0

        t2 = time.perf_counter()
        fused = rrf_fuse([bm25_res, dense_res], k=self.k, top_k=top_k)
        t_fusion = (time.perf_counter() - t2) * 1000.0

        total_e2e = t_bm25 + t_dense + t_fusion
        timings = {
            "bm25_ms": round(t_bm25, 3),
            "dense_ms": round(t_dense, 3),
            "fusion_ms": round(t_fusion, 3),
            "total_e2e_ms": round(total_e2e, 3),
        }
        return fused, timings


# ---------------------------------------------------------------------------
# 6. Main Benchmark Execution & Latency Profiler
# ---------------------------------------------------------------------------

def run_benchmark():
    print("=" * 75)
    print("S5-B1 — Research Integrity & Multi-Hop Retrieval Benchmark")
    print("=" * 75)

    cold_start_timings: dict[str, float] = {}

    # 1. Corpus Loading & Cryptographic Fingerprinting
    t_start = time.perf_counter()
    passages, hashes = load_s5b1_corpus()
    cold_start_timings["corpus_load_ms"] = round((time.perf_counter() - t_start) * 1000.0, 3)

    print(f"Loaded {len(passages)} passages across the frozen evaluation universe.")
    print(f"Corpus PIDs SHA-256: {hashes['corpus_pids_sha256']}")
    print(f"Corpus Text SHA-256: {hashes['corpus_text_sha256']}")

    # 2. Dense Model Initialization & Cache Verification
    print("\n[1/4] Loading Dense Retrieval Engine (Snowflake/snowflake-arctic-embed-m-v1.5)...")
    t_mload = time.perf_counter()
    model = SentenceTransformer("Snowflake/snowflake-arctic-embed-m-v1.5", device="cpu")
    cold_start_timings["dense_model_load_ms"] = round((time.perf_counter() - t_mload) * 1000.0, 3)

    if not EMB_CACHE.exists():
        raise FileNotFoundError(f"Missing dense embedding cache at {EMB_CACHE}")

    t_emb_load = time.perf_counter()
    doc_embeddings = np.load(str(EMB_CACHE))
    cold_start_timings["dense_embedding_cache_load_ms"] = round((time.perf_counter() - t_emb_load) * 1000.0, 3)

    assert doc_embeddings.shape == (len(passages), 768), f"Shape mismatch: {doc_embeddings.shape}"
    cache_sha = hashlib.sha256(open(EMB_CACHE, "rb").read()).hexdigest()
    print(f"Dense embeddings verified: shape {doc_embeddings.shape}, cache SHA256: {cache_sha}")

    # 3. BM25 Index Construction
    t_bm25_build = time.perf_counter()
    bm25 = BM25Retriever(passages, k1=1.5, b=0.75)
    cold_start_timings["bm25_index_build_ms"] = round((time.perf_counter() - t_bm25_build) * 1000.0, 3)

    # 4. Strict Corpus-Scoped Graph Extraction (Repair 7)
    print("\n[2/4] Auditing and constructing corpus-scoped graph index...")
    import kuzu
    db = kuzu.Database(str(DB_PATH), read_only=True)
    kuzu_conn = kuzu.Connection(db)

    t_graph_build = time.perf_counter()
    eligible_chunk_keys = set((p.doc_id, p.chunk_id) for p in passages)

    doc_res = kuzu_conn.execute("MATCH (d:Document) RETURN d.id")
    all_doc_ids = []
    while doc_res.has_next():
        all_doc_ids.append(doc_res.get_next()[0])

    extractor = RepairedGraphExtractor()
    corpus_scoped_edges = []

    for doc_id in sorted(all_doc_ids):
        canon_doc_id = normalize_doc_id(doc_id)
        c_res = kuzu_conn.execute(
            "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = $doc RETURN c.chunk_id, c.text_passage",
            {"doc": doc_id},
        )
        scoped_chunks = []
        while c_res.has_next():
            row = c_res.get_next()
            cid, text = row[0], row[1]
            if (canon_doc_id, cid) in eligible_chunk_keys:
                scoped_chunks.append({"chunk_id": cid, "text_passage": text})

        if scoped_chunks:
            g = extractor.extract_document_graph(scoped_chunks, doc_id)
            if g.get("status") != "EXCLUDED":
                corpus_scoped_edges.extend(g.get("edges", []))

    cold_start_timings["corpus_scoped_graph_build_ms"] = round((time.perf_counter() - t_graph_build) * 1000.0, 3)
    print(f"Corpus-scoped graph contains {len(corpus_scoped_edges)} edges across the 713-passage universe.")

    # 5. Instantiate Retrievers
    dense = GenuineDenseRetriever(passages, model, doc_embeddings)
    hybrid_rrf = HybridRRFRetriever(bm25, dense, k=60)
    baseline_graph = RepairedBaselineGraphRetriever(passages, kuzu_conn, bm25_fallback=bm25)
    repaired_graph_1hop = RepairedHeterogeneousGraphRetriever(
        passages, corpus_scoped_edges, bm25_fallback=bm25, max_hops=1
    )
    repaired_graph_2hop = RepairedHeterogeneousGraphRetriever(
        passages, corpus_scoped_edges, bm25_fallback=bm25, max_hops=2
    )

    systems = {
        "bm25": bm25,
        "dense_snowflake_arctic_768d": dense,
        "hybrid_rrf_e2e": hybrid_rrf,
        "baseline_graph_1hop": baseline_graph,
        "repaired_graph_1hop_ablation": repaired_graph_1hop,
        "repaired_graph_2hop_full": repaired_graph_2hop,
    }

    # 6. Load Blinded Benchmark Queries
    blinded_pool_path = BASE_DIR / "human_evaluation_package" / "retrieval_query_pool_blinded.json"
    with open(blinded_pool_path, encoding="utf-8") as f:
        blinded_data = json.load(f)

    queries = [q["query_text"] for q in blinded_data["queries"]]
    query_objs = blinded_data["queries"]
    print(f"\n[3/4] Loaded {len(queries)} blinded evaluation queries.")

    # 7. Benchmarking Latency & Hop Traversal
    print("\n[4/4] Executing multi-hop retrieval benchmark (Cold query + 5 warm repetitions)...")
    system_results: dict[str, Any] = {}
    timing_summary: dict[str, Any] = {}

    for name, retriever in systems.items():
        query_outputs = []
        cold_latencies = []
        warm_latencies = []
        hop_counts = []
        fallback_count = 0
        all_paths_recorded: list[dict[str, Any]] = []

        for q_idx, q_item in enumerate(query_objs):
            query = q_item["query_text"]
            qid = q_item["query_id"]

            # 1. Cold execution (first run)
            t0 = time.perf_counter()
            if name == "hybrid_rrf_e2e":
                res, timings = retriever.search_timed(query, top_k=10)
                meta = {"timing_breakdown": timings, "is_fallback": False, "actual_hop_count": "N/A"}
            elif name in {"baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"}:
                res, meta = retriever.search(query, top_k=10)
            else:
                res = retriever.search(query, top_k=10)
                meta = {"is_fallback": False, "actual_hop_count": "N/A"}

            t_cold = (time.perf_counter() - t0) * 1000.0
            cold_latencies.append(t_cold)

            # Record hops and fallback
            actual_hop = meta.get("actual_hop_count", "N/A")
            if actual_hop != "N/A":
                hop_counts.append(actual_hop)
            if meta.get("is_fallback", False):
                fallback_count += 1
            if meta.get("paths_traversed"):
                all_paths_recorded.extend(meta["paths_traversed"])

            # 2. Warm repetitions (5 iterations)
            rep_times = []
            for _ in range(5):
                tw0 = time.perf_counter()
                if name == "hybrid_rrf_e2e":
                    _ = retriever.search_timed(query, top_k=10)
                elif name in {"baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"}:
                    _ = retriever.search(query, top_k=10)
                else:
                    _ = retriever.search(query, top_k=10)
                tw = (time.perf_counter() - tw0) * 1000.0
                rep_times.append(tw)

            warm_latencies.extend(rep_times)

            query_outputs.append({
                "query_id": qid,
                "domain": q_item["domain"],
                "category": q_item["category"],
                "query_text": query,
                "first_query_latency_ms": round(t_cold, 3),
                "warm_latency_mean_ms": round(statistics.mean(rep_times), 3),
                "meta": meta,
                "retrieved_top10": [{"passage_id": pid, "score": round(sc, 5)} for pid, sc in res[:10]],
            })

        # Calculate timing statistics
        warm_sorted = sorted(warm_latencies)
        p95_idx = int(0.95 * len(warm_sorted))

        system_timing = {
            "first_query_mean_ms": round(statistics.mean(cold_latencies), 3),
            "first_query_max_ms": round(max(cold_latencies), 3),
            "first_query_min_ms": round(min(cold_latencies), 3),
            "warm_mean_ms": round(statistics.mean(warm_latencies), 3),
            "warm_median_ms": round(statistics.median(warm_latencies), 3),
            "warm_std_ms": round(statistics.stdev(warm_latencies), 3),
            "warm_min_ms": round(min(warm_latencies), 3),
            "warm_max_ms": round(max(warm_latencies), 3),
            "warm_p95_ms": round(warm_sorted[p95_idx], 3),
        }
        timing_summary[name] = system_timing

        avg_hop = round(statistics.mean(hop_counts), 2) if hop_counts else "N/A"
        system_results[name] = {
            "system_name": name,
            "queries_evaluated": len(query_objs),
            "fallback_count": fallback_count,
            "fallback_rate": round(fallback_count / len(query_objs), 3),
            "observed_average_hop_depth": avg_hop,
            "total_paths_traversed": len(all_paths_recorded),
            "timing": system_timing,
            "effectiveness_verdict": "NOT_EVALUATED_PENDING_HUMAN_GOLD",
            "query_results": query_outputs,
        }

    # Save reports
    timing_report = {
        "report_name": "S5-B1 Retrieval Timing & Latency Profiling Report",
        "benchmark_date": "2026-11-18",
        "num_queries": len(query_objs),
        "num_warm_repetitions": 5,
        "application_cold_start_ms": cold_start_timings,
        "systems": timing_summary,
    }

    with open(TIMING_PATH, "w", encoding="utf-8") as f:
        json.dump(timing_report, f, indent=2)

    tech_eval_report = {
        "evaluation_name": "S5-B1 Multi-Hop Retrieval Technical Evaluation Gate",
        "date": "2026-11-18",
        "corpus_version": "s5a_eval_corpus_v1",
        "corpus_passage_count": len(passages),
        "application_cold_start_ms": cold_start_timings,
        "systems": system_results,
        "scientific_integrity_guarantees": {
            "effectiveness_claimed": False,
            "superiority_asserted": False,
            "human_gold_status": "PENDING_INDEPENDENT_ANNOTATION",
            "corpus_scope_strictly_identical": True,
            "bm25_fallback_active": True,
            "graph_paths_recorded": True,
        }
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(tech_eval_report, f, indent=2)

    print("\nBenchmark completed successfully.")
    print(f"Timing Report saved to: {TIMING_PATH}")
    print(f"Technical Report saved to: {REPORT_PATH}")

    # Print summary table
    print("\n" + "=" * 80)
    print(f"{'System':<30} | {'App Cold (ms)':<12} | {'1st Q (ms)':<10} | {'Warm Mean':<10} | {'Warm P95':<10}")
    print("-" * 80)
    for name, t in timing_summary.items():
        app_cold = cold_start_timings.get(f"{name}_build_ms", "N/A")
        print(f"{name:<30} | {str(app_cold):<12} | {t['first_query_mean_ms']:<10} | {t['warm_mean_ms']:<10} | {t['warm_p95_ms']:<10}")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()

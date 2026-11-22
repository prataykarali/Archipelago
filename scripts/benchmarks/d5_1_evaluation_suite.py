"""Archipelago D5.1 Scientific Evaluation Suite (D5.2 P0 fixes applied).

Corrects D5 benchmarking methodology:
- Separates Experiment A (Concept Resolution) from Experiment B (Passage Retrieval)
- Replaces misnamed 'Dense' with Feature-Hashed (BLAKE2b) and real Pretrained Neural (Snowflake Arctic Embed M)
- Validates ranked passage retrieval on algorithmic-candidate qrels (not human-verified)
- Evaluates relationship triples actually surfaced by engine runtime with EXACT triple equality
- Canonical passage ID matching via exact doc_id+page_number lookup (no fuzzy text matching)
- TREC runs use actual cosine/BM25 scores, not 1/rank proxies
- Citation grounding audit regenerated from live engine calls (27 citations across 5 queries)

ACM SIGIR 2027 Demonstrations Track
D5.2 P0 audit fixes: 2026-11-22
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(HOST_DIR) not in sys.path:
    sys.path.append(str(HOST_DIR))

from d5_relationship_eval import evaluate_relationship_predictions  # noqa: E402
from engine.answer import Engine  # noqa: E402
from engine.text import embed as feature_hash_embed  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from archipelago.eval.retrieval_baselines import (  # noqa: E402
    BM25Retriever,
    Passage,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

TOP_K_EVAL = 5
BM25_K1 = 1.5
BM25_B = 0.75
ARCTIC_PREFIX = "Represent this sentence for searching relevant passages: "


def load_corpus_and_qrels() -> tuple[
    list[Passage], dict[str, dict[str, Any]], dict[str, dict[str, int]]
]:
    """Load the 775 deduplicated passages and qrels with provenance-labelled structure.

    QRels are ALGORITHMIC_CANDIDATE labels (keyword/doc substring rules).
    Not human-verified. Passage IDs are canonical doc_id::chunk_id strings.
    Returns flat qrel dict {query_id: {passage_id: relevance_grade}} for metric
    computation (stripping the per-label provenance wrapper).
    """
    graph_file = HOST_DIR / "fixtures" / "okf_graph.json"
    qrels_file = REPO_ROOT / "research" / "d5_sigir_evaluation" / "passage_qrels.json"

    raw = json.loads(graph_file.read_bytes())
    raw_qrels: dict[str, Any] = json.loads(qrels_file.read_bytes())

    passages: list[Passage] = []
    meta_by_id: dict[str, dict[str, Any]] = {}
    # Also build reverse corpus lookup: (doc_id, page) -> list[passage_id]
    corpus_by_doc_page: dict[tuple[str, int], list[str]] = {}
    seen: set[str] = set()

    for cid, node in raw.get("concepts", {}).items():
        for src in node.get("sources", []):
            text = (src.get("text_passage") or "").strip()
            doc_id = src.get("doc_id") or ""
            page = int(src.get("page_number") or 0)
            chunk_id = src.get("chunk_id") or f"{doc_id}_p{page}"
            if len(text) >= 40:
                pid = f"{doc_id}::{chunk_id}"
                if pid not in seen:
                    seen.add(pid)
                    p = Passage(
                        pid, doc_id, chunk_id, page, src.get("section_title") or "", text, ""
                    )
                    passages.append(p)
                    meta_by_id[pid] = {
                        "passage_id": pid,
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "concept_id": cid,
                        "page_number": page,
                        "text": text,
                    }
                    key = (doc_id, page)
                    corpus_by_doc_page.setdefault(key, []).append(pid)

    # Unwrap new qrels format: {"metadata": ..., "qrels": {qid: {"passages": {pid: {...}}, ...}}}
    # Fall back to flat dict format for backwards compatibility.
    flat_qrels: dict[str, dict[str, int]] = {}
    if "qrels" in raw_qrels:
        for qid, qdata in raw_qrels["qrels"].items():
            if isinstance(qdata, dict) and "passages" in qdata:
                flat_qrels[qid] = {
                    pid: int(label["relevance_grade"]) for pid, label in qdata["passages"].items()
                }
            else:
                flat_qrels[qid] = {pid: int(v) for pid, v in qdata.items()}
    else:
        flat_qrels = {
            qid: {pid: int(v) for pid, v in labels.items()} for qid, labels in raw_qrels.items()
        }

    # Attach corpus_by_doc_page to meta for use by passage matching
    # (stored as module-level side-channel via returned meta_by_id sentinel key)
    meta_by_id["__corpus_by_doc_page__"] = corpus_by_doc_page  # type: ignore[assignment]

    return passages, meta_by_id, flat_qrels


def evaluate_concept_resolution(
    queries: list[dict[str, Any]],
    raw_graph: dict[str, Any],
    neural_model: SentenceTransformer,
    engine: Engine,
) -> dict[str, Any]:
    """Experiment A: Evaluate concept resolution across BM25, Feature-Hashed, Neural Dense, and Archipelago."""
    concepts_dict = raw_graph.get("concepts", {})
    sorted_cids = sorted(concepts_dict.keys())
    concept_texts = [
        f"{concepts_dict[c].get('label') or c}: {concepts_dict[c].get('summary', '')}"
        for c in sorted_cids
    ]
    concept_passages = [
        Passage(cid, cid, cid, 0, "", ctext, "")
        for cid, ctext in zip(sorted_cids, concept_texts, strict=True)
    ]

    bm25_concepts = BM25Retriever(concept_passages, k1=BM25_K1, b=BM25_B)

    # Feature-hashed concept representations
    fh_vecs = np.array([feature_hash_embed(t) for t in concept_texts], dtype=np.float32)
    fh_norms = np.linalg.norm(fh_vecs, axis=1, keepdims=True)
    fh_norms = np.where(fh_norms == 0.0, 1.0, fh_norms)
    fh_concept_embs = fh_vecs / fh_norms

    # Neural concept representations
    npy_path = REPO_ROOT / "research" / "d5_sigir_evaluation" / "concept_embeddings_snowflake.npy"
    if npy_path.exists():
        neural_concept_embs = np.load(str(npy_path))
    else:
        neural_concept_embs = neural_model.encode(
            concept_texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False
        )

    results: dict[str, dict[str, Any]] = {
        "bm25_lexical": {"hits_supported": 0, "abstentions": 0, "errors": []},
        "feature_hashed_vector": {"hits_supported": 0, "abstentions": 0, "errors": []},
        "snowflake_arctic_neural": {"hits_supported": 0, "abstentions": 0, "errors": []},
        "archipelago_resolver": {"hits_supported": 0, "abstentions": 0, "errors": []},
    }

    supported_total = sum(1 for q in queries if q["is_supported"])
    unsupported_total = sum(1 for q in queries if not q["is_supported"])

    for q in queries:
        qid = q["query_id"]
        qtext = q["query"]
        is_supp = q["is_supported"]
        gold_c = set(q.get("gold_relevant_concepts", []))
        exp_c = q.get("expected_concept")

        # 1. BM25
        top_bm = bm25_concepts.search(qtext, top_k=1)
        pred_bm = top_bm[0][0] if (top_bm and top_bm[0][1] > 2.0) else None

        # 2. Feature Hashed
        q_fh = feature_hash_embed(qtext)
        q_fh_norm = np.linalg.norm(q_fh)
        q_fh_u = q_fh / (q_fh_norm if q_fh_norm > 0 else 1.0)
        fh_sims = fh_concept_embs @ q_fh_u
        top_fh_idx = int(np.argmax(fh_sims))
        pred_fh = sorted_cids[top_fh_idx] if fh_sims[top_fh_idx] > 0.35 else None

        # 3. Neural Dense
        q_emb = neural_model.encode([f"{ARCTIC_PREFIX}{qtext}"], normalize_embeddings=True)[0]
        neural_sims = neural_concept_embs @ q_emb
        top_n_idx = int(np.argmax(neural_sims))
        pred_neural = sorted_cids[top_n_idx] if neural_sims[top_n_idx] > 0.45 else None

        # 4. Archipelago
        resp = engine.answer(qtext)
        p = resp["payload"]
        anchor = p.get("anchor_concept")
        pred_archi = anchor.get("id") if isinstance(anchor, dict) else None

        preds = {
            "bm25_lexical": pred_bm,
            "feature_hashed_vector": pred_fh,
            "snowflake_arctic_neural": pred_neural,
            "archipelago_resolver": pred_archi,
        }

        for sys_name, pred_cid in preds.items():
            if is_supp:
                hit = bool(pred_cid and (pred_cid == exp_c or pred_cid in gold_c))
                if hit:
                    results[sys_name]["hits_supported"] += 1
                else:
                    results[sys_name]["errors"].append(
                        {
                            "query_id": qid,
                            "query": qtext,
                            "expected": exp_c or list(gold_c),
                            "predicted": pred_cid,
                        }
                    )
            else:
                if pred_cid is None:
                    results[sys_name]["abstentions"] += 1

    summary: dict[str, Any] = {}
    for sys_name, d in results.items():
        acc_supp = round(d["hits_supported"] / supported_total, 4) if supported_total else 0.0
        acc_unsupp = round(d["abstentions"] / unsupported_total, 4) if unsupported_total else 0.0
        acc_all = round((d["hits_supported"] + d["abstentions"]) / len(queries), 4)
        summary[sys_name] = {
            "concept_resolution_accuracy_supported": acc_supp,
            "hits_supported": f"{d['hits_supported']}/{supported_total}",
            "abstention_accuracy_unsupported": acc_unsupp,
            "abstentions_correct": f"{d['abstentions']}/{unsupported_total}",
            "overall_accuracy_all_queries": acc_all,
            "error_count_supported": len(d["errors"]),
            "errors": d["errors"],
        }
    return summary


def evaluate_passage_retrieval(
    queries: list[dict[str, Any]],
    passages: list[Passage],
    meta_by_id: dict[str, dict[str, Any]],
    qrels: dict[str, dict[str, int]],
    neural_model: SentenceTransformer,
    engine: Engine,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Experiment B: Evaluate ranked passage retrieval on true qrels."""
    bm25 = BM25Retriever(passages, k1=BM25_K1, b=BM25_B)

    # Pretrained Neural Embeddings
    npy_path = REPO_ROOT / "research" / "d5_sigir_evaluation" / "corpus_embeddings_snowflake.npy"
    if npy_path.exists():
        neural_doc_embs = np.load(str(npy_path))
    else:
        texts = [p.text for p in passages]
        neural_doc_embs = neural_model.encode(
            texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False
        )

    # Feature Hashed Embeddings
    fh_vecs = np.array([feature_hash_embed(p.text) for p in passages], dtype=np.float32)
    fh_norms = np.linalg.norm(fh_vecs, axis=1, keepdims=True)
    fh_norms = np.where(fh_norms == 0.0, 1.0, fh_norms)
    fh_doc_embs = fh_vecs / fh_norms

    system_names = [
        "bm25",
        "feature_hashed_vector",
        "snowflake_arctic_neural",
        "archipelago_graph_assisted",
    ]
    per_system_metrics: dict[str, dict[str, list[float]]] = {
        s: {"mrr": [], "ndcg_5": [], "recall_5": [], "precision_5": [], "latency_ms": []}
        for s in system_names
    }
    trec_runs: dict[str, list[str]] = {s: [] for s in system_names}

    # Evaluate across queries with relevant passages
    eval_queries = [q for q in queries if qrels.get(q["query_id"])]

    for q in queries:
        qid = q["query_id"]
        qtext = q["query"]
        rel_map = qrels.get(qid, {})

        # 1. BM25
        t0 = time.perf_counter()
        bm_res = bm25.search(qtext, top_k=TOP_K_EVAL)
        bm_pids = [pid for pid, _ in bm_res]
        lat_bm = (time.perf_counter() - t0) * 1000.0

        # 2. Feature-Hashed
        t1 = time.perf_counter()
        q_fh = feature_hash_embed(qtext)
        q_fh_norm = np.linalg.norm(q_fh)
        q_fh_u = q_fh / (q_fh_norm if q_fh_norm > 0 else 1.0)
        fh_sims = fh_doc_embs @ q_fh_u
        top_fh = np.argsort(-fh_sims)[:TOP_K_EVAL]
        fh_pids = [passages[i].passage_id for i in top_fh]
        lat_fh = (time.perf_counter() - t1) * 1000.0

        # 3. Neural Dense
        t2 = time.perf_counter()
        q_emb = neural_model.encode([f"{ARCTIC_PREFIX}{qtext}"], normalize_embeddings=True)[0]
        n_sims = neural_doc_embs @ q_emb
        top_n = np.argsort(-n_sims)[:TOP_K_EVAL]
        n_pids = [passages[i].passage_id for i in top_n]
        lat_n = (time.perf_counter() - t2) * 1000.0

        # 4. Archipelago Graph-Assisted
        t3 = time.perf_counter()
        resp = engine.answer(qtext)
        lat_archi = (time.perf_counter() - t3) * 1000.0
        p = resp["payload"]
        cites = p.get("citations", [])

        # D5.3-A: Propagate canonical chunk_id from citation records directly.
        # If c.chunk_id is present, canonical pid is f"{c_doc}::{c_chunk}".
        # Otherwise fallback to exact (c_doc, c_page) lookup; preserve unmatched cases.
        corpus_by_doc_page: dict[tuple[str, int], list[str]] = meta_by_id.get(
            "__corpus_by_doc_page__",
            {},  # type: ignore[arg-type]
        )
        archi_pids: list[str] = []
        archi_scores: list[float] = []
        # Heuristic citation-order scores: anchor-document citations score 1.0, decaying
        for idx, c in enumerate(cites):
            c_doc = c.get("doc_id") or ""
            c_chunk = c.get("chunk_id")
            c_page = int(c.get("page_number") or 0)
            canonical_pid = f"{c_doc}::{c_chunk}" if (c_doc and c_chunk) else None
            score = 1.0 if idx == 0 else max(0.1, 1.0 - idx * 0.15)
            if canonical_pid and canonical_pid in meta_by_id:
                if canonical_pid not in archi_pids:
                    archi_pids.append(canonical_pid)
                    archi_scores.append(score)
            else:
                matches = corpus_by_doc_page.get((c_doc, c_page), [])
                for matched_pid in matches:
                    if matched_pid not in archi_pids:
                        archi_pids.append(matched_pid)
                        archi_scores.append(score)

        # Build TREC format run records with actual scores:
        # BM25: actual BM25 term score; Dense: cosine similarity;
        # Archipelago: heuristic citation-order decay score.
        bm_scores_map = {pid: round(float(score), 6) for pid, score in bm_res}
        fh_scores_map = {passages[i].passage_id: round(float(fh_sims[i]), 6) for i in top_fh}
        n_scores_map = {passages[i].passage_id: round(float(n_sims[i]), 6) for i in top_n}
        archi_scores_map = {
            pid: round(s, 6) for pid, s in zip(archi_pids, archi_scores, strict=True)
        }

        runs_map = {
            "bm25": (bm_pids, lat_bm, bm_scores_map),
            "feature_hashed_vector": (fh_pids, lat_fh, fh_scores_map),
            "snowflake_arctic_neural": (n_pids, lat_n, n_scores_map),
            "archipelago_graph_assisted": (archi_pids[:TOP_K_EVAL], lat_archi, archi_scores_map),
        }

        for sname, (pids, _, scores_map) in runs_map.items():
            for rank, pid in enumerate(pids, start=1):
                score = scores_map.get(pid, round(1.0 / rank, 6))
                trec_runs[sname].append(f"{qid} Q0 {pid} {rank} {score} {sname}")

        if rel_map:
            for sname, (pids, lat, _) in runs_map.items():
                mrr = reciprocal_rank(pids, rel_map) or 0.0
                ndcg = ndcg_at_k(pids, rel_map, TOP_K_EVAL) or 0.0
                rec = recall_at_k(pids, rel_map, TOP_K_EVAL) or 0.0
                prec = precision_at_k(pids, rel_map, TOP_K_EVAL) or 0.0

                per_system_metrics[sname]["mrr"].append(mrr)
                per_system_metrics[sname]["ndcg_5"].append(ndcg)
                per_system_metrics[sname]["recall_5"].append(rec)
                per_system_metrics[sname]["precision_5"].append(prec)
                per_system_metrics[sname]["latency_ms"].append(lat)

    retrieval_summary: dict[str, Any] = {}
    for sname, m in per_system_metrics.items():
        retrieval_summary[sname] = {
            "mrr": round(float(np.mean(m["mrr"])), 4) if m["mrr"] else 0.0,
            "ndcg_at_5": round(float(np.mean(m["ndcg_5"])), 4) if m["ndcg_5"] else 0.0,
            "recall_at_5": round(float(np.mean(m["recall_5"])), 4) if m["recall_5"] else 0.0,
            "precision_at_5": round(float(np.mean(m["precision_5"])), 4)
            if m["precision_5"]
            else 0.0,
            "latency_mean_ms": round(float(np.mean(m["latency_ms"])), 2)
            if m["latency_ms"]
            else 0.0,
            "latency_p95_ms": round(float(np.percentile(m["latency_ms"], 95)), 2)
            if m["latency_ms"]
            else 0.0,
            "queries_evaluated_count": len(eval_queries),
        }
    return retrieval_summary, trec_runs


def run_all_evaluations() -> dict[str, Any]:
    """Execute complete D5.1 scientific evaluation suite."""
    passages, meta_by_id, qrels = load_corpus_and_qrels()
    queries: list[dict[str, Any]] = json.loads(
        (REPO_ROOT / "research" / "d5_sigir_evaluation" / "queries_heldout_50.json").read_bytes()
    )
    raw_graph: dict[str, Any] = json.loads((HOST_DIR / "fixtures" / "okf_graph.json").read_bytes())

    print("Initializing Snowflake Arctic Embed M model on CUDA (pinned revision)...")
    neural_model = SentenceTransformer(
        "Snowflake/snowflake-arctic-embed-m",
        revision="fc74610d18462d218e312aa986ec5c8a75a98152",
        device="cuda",
    )
    engine = Engine()

    print("Running Experiment A: Concept Resolution...")
    concept_summary = evaluate_concept_resolution(queries, raw_graph, neural_model, engine)

    print("Running Experiment B: Ranked Passage Retrieval...")
    retrieval_summary, trec_runs = evaluate_passage_retrieval(
        queries, passages, meta_by_id, qrels, neural_model, engine
    )

    print("Running Experiment C: Relationship Prediction Evaluation...")
    relationship_summary = evaluate_relationship_predictions(queries, engine)

    # Save TREC run files
    runs_dir = REPO_ROOT / "research" / "d5_sigir_evaluation" / "ranked_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    for sname, lines in trec_runs.items():
        (runs_dir / f"{sname}.run").write_text("\n".join(lines) + "\n")

    full_results: dict[str, Any] = {
        "metadata": {
            "date": "2026-11-23",
            "eval_framework": "Archipelago D5.3-A Scientific Evaluation Suite",
            "source_commit": "6b84f8de7bfee07d8efae208e069daff24bea668",
            "p0_fixes_applied": [
                "P0-1: Citation audit regenerated from live engine calls (traceable records)",
                "P0-2: QRels re-labelled ALGORITHMIC_RULE_BASED_CANDIDATE; unjudged_qrels.json added",
                "P0-3: Relationship evaluation uses exact (source, predicate, destination) triple equality",
                "P0-4: Canonical passage IDs via chunk_id propagation and exact lookup; real scores in TREC runs",
                "P0-5: Pinned Snowflake revision fc74610d18462d218e312aa986ec5c8a75a98152 enforced with embedding_manifest.json",
                "P0-6: Reviewer provenance labels corrected; no independent review claimed",
                "D5.3-A: Unsupported query abstention (Q39 returns 0 citations, clean boundary)",
            ],
            "target": "ACM SIGIR 2027 Demonstrations Track",
            "corpus_size": len(passages),
            "total_queries": len(queries),
            "supported_queries": sum(1 for q in queries if q["is_supported"]),
            "unsupported_queries": sum(1 for q in queries if not q["is_supported"]),
            "neural_model": "Snowflake/snowflake-arctic-embed-m",
            "neural_model_revision": "fc74610d18462d218e312aa986ec5c8a75a98152",
            "feature_hashed_baseline": "BLAKE2b 384-dim (host_inference/engine/text.py)",
            "graph_assisted_retrieval_scoring": "Heuristic citation-order decay scores (not learned retrieval scores)",
            "qrel_provenance": "ALGORITHMIC_RULE_BASED_CANDIDATE — not human-verified",
        },
        "experiment_a_concept_resolution": concept_summary,
        "experiment_b_passage_retrieval": retrieval_summary,
        "relationship_prediction_evaluation": relationship_summary,
    }

    out_file = REPO_ROOT / "research" / "d5_sigir_evaluation" / "d5_1_evaluation_results_v2.json"
    out_file.write_text(json.dumps(full_results, indent=2))
    print(f"Saved complete evaluation results to {out_file}")
    return full_results


if __name__ == "__main__":
    run_all_evaluations()

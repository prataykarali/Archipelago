"""S5-v3.1 unified retrieval runner across BM25, Snowflake Dense, Hybrid RRF, and v3 Graph variants."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from retrieval_v3.config import (
    DEFAULT_BM25_B,
    DEFAULT_BM25_K1,
    DEFAULT_RRF_K,
    DEFAULT_TOP_K,
    RetrievalV3Config,
    build_standard_v3_variants,
)
from retrieval_v3.corpus_grounding import load_okf_graph
from retrieval_v3.engine import RetrievalV3Engine, aggregate_variant_diagnostics
from retrieval_v3.instrumentation import measure_call, summarize_telemetry
from retrieval_v3.lexical import BM25LexicalControl
from retrieval_v3.types import (
    CorpusPassage,
    QueryResult,
)

from retrieval_v31.dense_cache import (
    ARCTIC_QUERY_PREFIX,
    DEFAULT_HYBRID_CANDIDATE_K,
    DenseSnowflakeRetriever,
    HybridRRFControl,
    compute_corpus_identity_hashes,
    load_or_build_embedding_cache,
)
from retrieval_v31.model_pin import ModelVerificationReport
from retrieval_v31.pooling import compute_all_pool_diagnostics, compute_pool_sizes_at_depth

SCHEMA_VERSION_V31 = "s5v31-retrieval-v1.0"
CONTROL_SYSTEM_NAMES: tuple[str, ...] = (
    "v31_lexical_bm25",
    "v31_dense_snowflake",
    "v31_hybrid_rrf_bm25_dense",
)
GRAPH_V3_SYSTEM_NAMES: tuple[str, ...] = (
    "v31_graph_naive_substring",
    "v31_graph_1hop_no_backfill",
    "v31_graph_1hop_backfill",
    "v31_graph_2hop_backfill",
    "v31_graph_2hop_coverage_routed",
)
DETERMINISM_PROBE_COUNT = 3


def canonical_config_sha256(cfg_dict: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 over canonical JSON config dictionary."""
    raw = json.dumps(cfg_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_eligible_v31_passages(jsonl_path: Path) -> tuple[list[CorpusPassage], dict[str, Any]]:
    """Load eligible Corpus v3.1 passages deterministically from JSONL."""
    passages: list[CorpusPassage] = []
    total_rows = 0
    excluded_ineligible = 0

    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            total_rows += 1
            row = json.loads(stripped)
            if row.get("eligible_for_benchmark") is False or row.get("is_usable") is False:
                excluded_ineligible += 1
                continue
            passage_id = str(
                row.get("passage_id") or row.get("chunk_id") or row.get("id") or f"p_{line_no}"
            )
            source_doc_id = str(row.get("source_doc_id") or row.get("doc_id") or "unknown_doc")
            text = str(row.get("text") or row.get("passage_text") or "")
            page_start = int(row.get("page_start") or row.get("page_number") or 0)
            page_end = int(row.get("page_end") or page_start)
            provenance_class = str(row.get("provenance_class") or "unknown")
            source_sha256 = str(row.get("source_sha256") or row.get("passage_sha256") or "")
            passages.append(
                CorpusPassage(
                    passage_id=passage_id,
                    source_doc_id=source_doc_id,
                    text=text,
                    page_start=page_start,
                    page_end=page_end,
                    provenance_class=provenance_class,
                    source_sha256=source_sha256,
                )
            )

    passages.sort(key=lambda p: p.passage_id)
    fp = compute_corpus_identity_hashes(passages)
    stats = {
        "total_rows_read": total_rows,
        "eligible_passages_used": len(passages),
        "excluded_ineligible_rows": excluded_ineligible,
        "passage_ids_sha256": fp["passage_ids_sha256"],
        "passage_texts_sha256": fp["passage_texts_sha256"],
    }
    return passages, stats


def load_v31_queries(queries_path: Path) -> list[dict[str, str]]:
    """Load proposed S5-v3.1 queries (id, text, split, category) from JSON/JSONL."""
    raw_text = queries_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []
    if queries_path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    else:
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict) and isinstance(parsed.get("queries"), list):
            rows = parsed["queries"]
        else:
            raise ValueError(f"Unsupported query file structure in {queries_path}")

    queries: list[dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        qid = str(row.get("query_id") or row.get("id") or f"q_{idx:03d}")
        qtext = str(row.get("query_text") or row.get("query") or row.get("text") or "").strip()
        if not qtext:
            continue
        queries.append(
            {
                "query_id": qid,
                "query_text": qtext,
                "split": str(row.get("split") or "unspecified"),
                "category": str(row.get("category") or "unspecified"),
            }
        )
    return queries


def _build_v31_graph_configs(top_k: int) -> list[RetrievalV3Config]:
    name_map = {
        "v3_graph_naive_substring_ablation": "v31_graph_naive_substring",
        "v3_graph_1hop_no_backfill": "v31_graph_1hop_no_backfill",
        "v3_graph_1hop_backfill": "v31_graph_1hop_backfill",
        "v3_graph_2hop_backfill": "v31_graph_2hop_backfill",
        "v3_graph_2hop_coverage_routed": "v31_graph_2hop_coverage_routed",
    }
    configs: list[RetrievalV3Config] = []
    for base in build_standard_v3_variants():
        if base.variant_name in name_map:
            configs.append(
                replace(
                    base,
                    variant_name=name_map[base.variant_name],
                    top_k=top_k,
                    schema_version=SCHEMA_VERSION_V31,
                )
            )
    return configs


def _summarize_control_system(
    variant_name: str,
    config_dict: dict[str, Any],
    config_sha256: str,
    index_telemetry: dict[str, Any],
    query_results: Sequence[QueryResult],
    top_k: int,
) -> dict[str, Any]:
    n = len(query_results)
    short_after = sum(1 for qr in query_results if len(qr.results) < top_k)
    zero_after = sum(1 for qr in query_results if len(qr.results) == 0)
    return {
        "variant_name": variant_name,
        "config_sha256": config_sha256,
        "config": config_dict,
        "effectiveness_evaluation": "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS",
        "index_build_telemetry": index_telemetry,
        "corpus_graph_coverage": None,
        "query_count": n,
        "technical_diagnostics": {
            "short_list_after_backfill_count": short_after,
            "short_list_after_backfill_rate": round(short_after / n if n else 0.0, 6),
            "zero_result_after_count": zero_after,
        },
        "telemetry_summary": summarize_telemetry([qr.telemetry for qr in query_results]),
        "per_query_diagnostics": [qr.to_dict() for qr in query_results],
    }


def run_v31_verification_suite(
    passages: Sequence[CorpusPassage],
    graph_path: Path,
    queries: Sequence[dict[str, str]],
    model_report: ModelVerificationReport,
    cache_npy_path: Path,
    *,
    encode_fn: Callable[[list[str]], np.ndarray],
    top_k: int = DEFAULT_TOP_K,
    force_rebuild_cache: bool = False,
    measure_memory: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run all 8 S5-v3.1 systems on identical corpus scope; return (manifest, diagnostics)."""
    concepts, edges = load_okf_graph(graph_path)
    embeddings, cache_meta = load_or_build_embedding_cache(
        passages,
        cache_npy_path,
        model_report.pin_manifest_sha256,
        model_report.revision,
        encode_fn=encode_fn,
        force_rebuild=force_rebuild_cache,
    )

    bm25, bm25_build_tel = measure_call(
        lambda: BM25LexicalControl(passages, k1=DEFAULT_BM25_K1, b=DEFAULT_BM25_B),
        measure_memory=measure_memory,
    )
    dense = DenseSnowflakeRetriever(
        passages, embeddings, encode_fn, query_prefix=ARCTIC_QUERY_PREFIX
    )
    hybrid = HybridRRFControl(
        bm25, dense, rrf_k=DEFAULT_RRF_K, candidate_k=DEFAULT_HYBRID_CANDIDATE_K
    )

    results_by_system: dict[str, list[QueryResult]] = {}
    variant_reports: dict[str, Any] = {}
    config_hashes: dict[str, str] = {}

    # 1. BM25 Lexical Control
    bm25_cfg = {
        "variant_name": "v31_lexical_bm25",
        "mode": "lexical",
        "bm25_k1": DEFAULT_BM25_K1,
        "bm25_b": DEFAULT_BM25_B,
        "top_k": top_k,
        "schema_version": SCHEMA_VERSION_V31,
    }
    bm25_sha = canonical_config_sha256(bm25_cfg)
    config_hashes["v31_lexical_bm25"] = bm25_sha
    bm25_qrs: list[QueryResult] = []
    for q in queries:
        from retrieval_v3.types import QueryProvenance, RankedPassage

        def _run_bm25(
            qt: str = q["query_text"],
        ) -> tuple[tuple[RankedPassage, ...], QueryProvenance]:
            hits = bm25.search(qt, top_k=top_k)
            ranked = tuple(
                RankedPassage(passage_id=pid, rank=idx, score=sc, source="lexical")
                for idx, (pid, sc) in enumerate(hits, start=1)
            )
            return ranked, QueryProvenance(
                routing_decision="lexical_control", graph_route_weight=0.0, lexical_route_weight=1.0
            )

        (ranked, prov), tel = measure_call(_run_bm25, measure_memory=measure_memory)
        bm25_qrs.append(
            QueryResult(
                q["query_id"], q["query_text"], "v31_lexical_bm25", bm25_sha, ranked, prov, tel
            )
        )
    results_by_system["v31_lexical_bm25"] = bm25_qrs
    variant_reports["v31_lexical_bm25"] = _summarize_control_system(
        "v31_lexical_bm25", bm25_cfg, bm25_sha, bm25_build_tel.to_dict(), bm25_qrs, top_k
    )

    # 2. Snowflake Dense Control
    dense_cfg = {
        "variant_name": "v31_dense_snowflake",
        "mode": "dense",
        "model_repo_id": model_report.repo_id,
        "model_revision": model_report.revision,
        "model_pin_sha256": model_report.pin_manifest_sha256,
        "query_prefix": ARCTIC_QUERY_PREFIX,
        "top_k": top_k,
        "schema_version": SCHEMA_VERSION_V31,
    }
    dense_sha = canonical_config_sha256(dense_cfg)
    config_hashes["v31_dense_snowflake"] = dense_sha
    dense_qrs: list[QueryResult] = []
    for q in queries:
        (ranked, prov), tel = measure_call(
            lambda qt=q["query_text"]: dense.search_ranked(qt, top_k=top_k),
            measure_memory=measure_memory,
        )
        dense_qrs.append(
            QueryResult(
                q["query_id"], q["query_text"], "v31_dense_snowflake", dense_sha, ranked, prov, tel
            )
        )
    results_by_system["v31_dense_snowflake"] = dense_qrs
    variant_reports["v31_dense_snowflake"] = _summarize_control_system(
        "v31_dense_snowflake",
        dense_cfg,
        dense_sha,
        {
            "cache_encode_seconds": cache_meta["encode_seconds"],
            "cache_bytes": cache_meta["cache_file_bytes"],
        },
        dense_qrs,
        top_k,
    )

    # 3. Hybrid RRF Control (BM25 + Snowflake Dense)
    hybrid_cfg = {
        "variant_name": "v31_hybrid_rrf_bm25_dense",
        "mode": "hybrid_rrf",
        "rrf_k": DEFAULT_RRF_K,
        "candidate_k": DEFAULT_HYBRID_CANDIDATE_K,
        "constituents": ["v31_lexical_bm25", "v31_dense_snowflake"],
        "top_k": top_k,
        "schema_version": SCHEMA_VERSION_V31,
    }
    hybrid_sha = canonical_config_sha256(hybrid_cfg)
    config_hashes["v31_hybrid_rrf_bm25_dense"] = hybrid_sha
    hybrid_qrs: list[QueryResult] = []
    for q in queries:
        (ranked, prov), tel = measure_call(
            lambda qt=q["query_text"]: hybrid.search_ranked(qt, top_k=top_k),
            measure_memory=measure_memory,
        )
        hybrid_qrs.append(
            QueryResult(
                q["query_id"],
                q["query_text"],
                "v31_hybrid_rrf_bm25_dense",
                hybrid_sha,
                ranked,
                prov,
                tel,
            )
        )
    results_by_system["v31_hybrid_rrf_bm25_dense"] = hybrid_qrs
    variant_reports["v31_hybrid_rrf_bm25_dense"] = _summarize_control_system(
        "v31_hybrid_rrf_bm25_dense", hybrid_cfg, hybrid_sha, {}, hybrid_qrs, top_k
    )

    # 4-8. Improved v3 Graph Variants
    graph_engines: dict[str, RetrievalV3Engine] = {}
    for gcfg in _build_v31_graph_configs(top_k):
        engine = RetrievalV3Engine(gcfg, passages, concepts, edges, shared_lexical=bm25)
        graph_engines[gcfg.variant_name] = engine
        config_hashes[gcfg.variant_name] = engine.config_sha256
        g_qrs = [engine.search_query(q["query_id"], q["query_text"]) for q in queries]
        results_by_system[gcfg.variant_name] = g_qrs
        variant_reports[gcfg.variant_name] = aggregate_variant_diagnostics(engine, g_qrs)

    # Repeat-run determinism check on first N queries across all 8 systems
    probe_queries = list(queries[:DETERMINISM_PROBE_COUNT])
    determinism_checks: dict[str, bool] = {}
    for sys_name, first_qrs in results_by_system.items():
        first_by_qid = {qr.query_id: [r.passage_id for r in qr.results] for qr in first_qrs}
        all_match = True
        for q in probe_queries:
            if sys_name == "v31_lexical_bm25":
                rep_pids = [pid for pid, _ in bm25.search(q["query_text"], top_k=top_k)]
            elif sys_name == "v31_dense_snowflake":
                rep_pids = [pid for pid, _ in dense.search(q["query_text"], top_k=top_k)]
            elif sys_name == "v31_hybrid_rrf_bm25_dense":
                rep_ranked, _ = hybrid.search_ranked(q["query_text"], top_k=top_k)
                rep_pids = [r.passage_id for r in rep_ranked]
            else:
                rep_qr = graph_engines[sys_name].search_query(q["query_id"], q["query_text"])
                rep_pids = [r.passage_id for r in rep_qr.results]
            if rep_pids != first_by_qid[q["query_id"]]:
                all_match = False
                break
        determinism_checks[sys_name] = all_match

    # Relevance-agnostic depth-5 and depth-10 unique pooling statistics
    pooling_all = compute_all_pool_diagnostics(
        results_by_system,
        control_systems=CONTROL_SYSTEM_NAMES,
        graph_v3_systems=GRAPH_V3_SYSTEM_NAMES,
    )

    # Split-stratified pooling (dev vs test) if splits present
    split_qids: dict[str, set[str]] = {}
    for q in queries:
        split_qids.setdefault(q["split"], set()).add(q["query_id"])
    pooling_by_split: dict[str, Any] = {}
    for split_name, qid_set in sorted(split_qids.items()):
        sub_results = {
            s: [qr for qr in qrs if qr.query_id in qid_set] for s, qrs in results_by_system.items()
        }
        pooling_by_split[split_name] = {
            "depth_5": compute_pool_sizes_at_depth(sub_results, 5),
            "depth_10": compute_pool_sizes_at_depth(sub_results, 10),
        }

    manifest = {
        "schema_version": SCHEMA_VERSION_V31,
        "effectiveness_evaluation": "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS",
        "depends_on_v21_okf_graph_db": False,
        "frozen_v21_and_v3_artifacts_modified": False,
        "pretrained_model_disclosure": model_report.to_dict(),
        "graph_structure_disclosure": {
            "graph_path": "okf_graph.json",
            "concept_count": len(concepts),
            "edge_count": len(edges),
            "depends_on_kuzu_db": False,
        },
        "dense_embedding_cache": cache_meta,
        "system_count": len(config_hashes),
        "control_systems": list(CONTROL_SYSTEM_NAMES),
        "graph_v3_systems": list(GRAPH_V3_SYSTEM_NAMES),
        "variant_config_hashes": config_hashes,
        "determinism_verification": {
            "probe_query_count": len(probe_queries),
            "all_systems_deterministic": all(determinism_checks.values()),
            "per_system": determinism_checks,
        },
    }

    diagnostics = {
        "schema_version": SCHEMA_VERSION_V31,
        "effectiveness_evaluation": "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS",
        "scientific_boundary_notice": (
            "Strictly relevance-agnostic technical diagnostics and depth-5/depth-10 "
            "unique pool sizes. Zero human relevance judgments exist; zero effectiveness "
            "or superiority claims are made."
        ),
        "depends_on_v21_okf_graph_db": False,
        "query_count": len(queries),
        "pooling_diagnostics": pooling_all,
        "pooling_by_split": pooling_by_split,
        "determinism_verification": manifest["determinism_verification"],
        "variant_config_hashes": config_hashes,
        "variants": variant_reports,
    }
    return manifest, diagnostics

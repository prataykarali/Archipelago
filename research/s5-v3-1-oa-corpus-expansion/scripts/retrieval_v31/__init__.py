"""S5-v3.1 retrieval verification package (BM25, pinned Snowflake dense, Hybrid RRF, v3 Graph)."""

from __future__ import annotations

from retrieval_v31.dense_cache import (
    ARCTIC_QUERY_PREFIX,
    DenseSnowflakeRetriever,
    HybridRRFControl,
    compute_corpus_identity_hashes,
    load_or_build_embedding_cache,
    make_snowflake_cpu_encoder,
    verify_embedding_cache_integrity,
)
from retrieval_v31.model_pin import (
    ModelVerificationReport,
    compute_file_sha256,
    run_controlled_cpu_smoke_test,
    verify_essential_model,
    verify_pinned_model_files,
)
from retrieval_v31.pooling import compute_all_pool_diagnostics, compute_pool_sizes_at_depth
from retrieval_v31.runner import (
    CONTROL_SYSTEM_NAMES,
    GRAPH_V3_SYSTEM_NAMES,
    SCHEMA_VERSION_V31,
    load_eligible_v31_passages,
    load_v31_queries,
    run_v31_verification_suite,
)

__all__ = [
    "ARCTIC_QUERY_PREFIX",
    "CONTROL_SYSTEM_NAMES",
    "GRAPH_V3_SYSTEM_NAMES",
    "SCHEMA_VERSION_V31",
    "DenseSnowflakeRetriever",
    "HybridRRFControl",
    "ModelVerificationReport",
    "compute_all_pool_diagnostics",
    "compute_corpus_identity_hashes",
    "compute_file_sha256",
    "compute_pool_sizes_at_depth",
    "load_eligible_v31_passages",
    "load_or_build_embedding_cache",
    "load_v31_queries",
    "make_snowflake_cpu_encoder",
    "run_controlled_cpu_smoke_test",
    "run_v31_verification_suite",
    "verify_embedding_cache_integrity",
    "verify_essential_model",
    "verify_pinned_model_files",
]

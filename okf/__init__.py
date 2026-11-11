"""Archipelago OKF pipeline package.

Public API re-exports so `import okf` / `from okf import ...` exposes the same
names the monolithic okf_pipeline.py used to. Module layout:

    config        constants, prompts, schema vocabularies
    util          concept IDs + provenance record helpers
    canonicalize  name canonicalization and alias merging
    cleanup       junk filters, grounding, dedup, cycle breaking
    extraction    SLM extraction + local-model state (owns LOCAL_MODEL et al.)
    relations     second-pass relation extraction
    graph_db      KùzuDB ingestion and raw graph export
    exports       visualization / GraphRAG index / audit payloads
    evaluate      proxy accuracy metrics
    pipeline      orchestration (run_pipeline, add_document, finalize_and_build)
"""

from okf.canonicalize import (
    ALIAS_MAP,  # noqa: F401
    apply_canonicalization,  # noqa: F401
    build_canonical_map,  # noqa: F401
    canonicalize_name,  # noqa: F401
    is_same_concept_reference,  # noqa: F401
)
from okf.cleanup import (
    apply_grounding_filter,  # noqa: F401
    break_global_cycles,  # noqa: F401
    cleanup_and_canonicalize,  # noqa: F401
    dedupe_identical_records,  # noqa: F401
    is_valid_concept_name,  # noqa: F401
    merge_duplicate_results,  # noqa: F401
    prune_invalid_references,  # noqa: F401
    prune_unresolved_references,  # noqa: F401
)
from okf.config import (
    BASE_DIR,  # noqa: F401
    EXTRACTION_PROMPT_V15,  # noqa: F401
    MAX_CHARS_TO_SLM,  # noqa: F401
    MAX_PAGES_PER_DOC,  # noqa: F401
    MAX_RETRIES,  # noqa: F401
    MODEL_NAME,  # noqa: F401
    RELATION_PROMPT,  # noqa: F401
    VALID_DIFFICULTIES,  # noqa: F401
    VALID_RELATIONS,  # noqa: F401
    VALID_TYPES,  # noqa: F401
    infer_source_category,  # noqa: F401
)
from okf.evaluate import evaluate_extraction  # noqa: F401
from okf.exports import (
    audit_graph_export,  # noqa: F401
    build_graph_rag_index,  # noqa: F401
    build_visual_graph,  # noqa: F401
)
from okf.extraction import (
    extract_chunks_with_model,  # noqa: F401
    extract_okf_v15,  # noqa: F401
    is_local_mode,  # noqa: F401
    is_model_loaded,  # noqa: F401
    load_local_model,  # noqa: F401
    normalize_okf_item,  # noqa: F401
)
from okf.graph_db import (
    _kuzu_escape,  # noqa: F401
    export_graph,  # noqa: F401
    ingest_to_kuzu,  # noqa: F401
)
from okf.pipeline import (
    add_document,  # noqa: F401
    compute_doc_id,  # noqa: F401
    finalize_and_build,  # noqa: F401
    run_pipeline,  # noqa: F401
)
from okf.relations import (
    extract_relations_for_record,  # noqa: F401
    relation_pass,  # noqa: F401
    run_relations_only,  # noqa: F401
)
from okf.util import (
    _dedupe_dicts,  # noqa: F401
    _record_sources,  # noqa: F401
    _source_record,  # noqa: F401
    create_concept_id,  # noqa: F401
)

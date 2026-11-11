"""Second-pass relation extraction over cleaned+canonicalized records."""

from __future__ import annotations

import json  # noqa: F401
import sys  # noqa: F401
import time  # noqa: F401

from okf import extraction  # noqa: F401
from okf.cleanup import cleanup_and_canonicalize  # noqa: F401
from okf.config import BASE_DIR, MAX_CHARS_TO_SLM, RELATION_PROMPT  # noqa: F401
from okf.extraction import (
    _extract_json_payload,  # noqa: F401
    _generate_local,  # noqa: F401
    _normalize_related,  # noqa: F401
    _string_list,  # noqa: F401
    load_local_model,  # noqa: F401
)

from .part01_passage_candidates import (
    _passage_candidates,
    extract_relations_for_record,
    filter_relations,
    infer_prerequisite_direction,
    relation_pass,
    run_relations_only,
    validate_relation,
)
from .part02_build_validated_edges import (
    build_validated_edges,
)

__all__ = [
    "_passage_candidates",
    "build_validated_edges",
    "extract_relations_for_record",
    "filter_relations",
    "infer_prerequisite_direction",
    "relation_pass",
    "run_relations_only",
    "validate_relation",
]

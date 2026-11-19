"""Retained S5-v3 proposed queries (40 positive + 4 verified-absent NCs)."""

from __future__ import annotations

import json
from pathlib import Path

from .builder import QueryDraft
from .constants import CAT_NEGATIVE_CONTROL, DEFAULT_V3_PROPOSED_JSON

# The 4 S5-v3 negative controls from deferred CS domains (Raft, PostgreSQL MVCC,
# TCP BBR, Linux CFS) are NOT blindly retained as negative controls in v3.1
# because Corpus v3.1 now ingests OS, Databases, Networks, and Distributed Systems.
_RETAINED_V3_NC_IDS: frozenset[str] = frozenset(
    {"Q-S5V3-15", "Q-S5V3-45", "Q-S5V3-46", "Q-S5V3-48"}
)

_DOC_DOMAIN_MAP: dict[str, str] = {
    "local_oa_001": "Machine Learning",
    "local_oa_002": "NLP / LLMs",
    "local_oa_003": "Math for ML",
    "local_oa_004": "Robotics / Control",
}


def _infer_domain(raw_query: dict[str, object]) -> str:
    if raw_query.get("category") == CAT_NEGATIVE_CONTROL:
        return "Negative Control (Absent)"
    evs = raw_query.get("supporting_evidence", [])
    if isinstance(evs, list) and evs:
        docs = {str(e["source_doc_id"]) for e in evs if isinstance(e, dict)}
        if len(docs) > 1:
            return "Cross-Domain (ML/Math/NLP/Robotics)"
        only_doc = next(iter(docs))
        return _DOC_DOMAIN_MAP.get(only_doc, "Machine Learning")
    return "Machine Learning"


def get_retained_v3_drafts(
    v3_manifest_path: Path = Path(DEFAULT_V3_PROPOSED_JSON),
) -> list[QueryDraft]:
    """Load the 44 retained S5-v3 proposals without modifying the v3 file."""
    raw = json.loads(v3_manifest_path.read_text(encoding="utf-8"))
    drafts: list[QueryDraft] = []
    seq = 1
    for q in raw.get("queries", []):
        v3_id = str(q["query_id"])
        cat = str(q["category"])
        if cat == CAT_NEGATIVE_CONTROL and v3_id not in _RETAINED_V3_NC_IDS:
            continue
        sc = q["single_passage_shortcut_check"]
        ev_ids = tuple(str(e["passage_id"]) for e in q["supporting_evidence"])
        min_ids = tuple(str(pid) for pid in q["minimum_required_evidence_set"])
        drafts.append(
            QueryDraft(
                query_id=f"Q-S5V31-{seq:02d}",
                query_text=str(q["query_text"]),
                split=str(q["split"]),
                category=cat,
                domain=_infer_domain(q),
                domain_topic=str(q["domain_topic"]),
                exact_information_need=str(q["exact_information_need"]),
                evidence_passage_ids=ev_ids,
                minimum_required_evidence_ids=min_ids,
                answer_exists_in_eligible_corpus=bool(
                    q["answer_exists_in_eligible_corpus"]
                ),
                multi_document_truly_necessary=bool(
                    q["multi_document_truly_necessary"]
                ),
                shortcut_found=bool(sc["shortcut_found"]),
                shortcut_rationale=str(sc["rationale"]),
                origin_v3_query_id=v3_id,
                premise_audit_flags=tuple(
                    str(f) for f in q.get("premise_audit_flags", [])
                ),
            )
        )
        seq += 1
    return drafts

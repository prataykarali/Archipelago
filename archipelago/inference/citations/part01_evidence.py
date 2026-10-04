"""Citation evidence retrieval: printed-page mapping, labels, concept citation map."""

from __future__ import annotations

import itertools

from archipelago.inference import state as st
from archipelago.inference.aliases import _node_name
from archipelago.inference.graph_access import _default_graph_db
from archipelago.inference.neighborhood import get_concept_citations


def _resolve_printed_page(evidence):
    """Reverse-map a physical PDF page to its printed label, if a map exists.

    ``page_label_map`` maps printed labels to physical (1-based) PDF pages;
    return the label whose page matches, or None when no map exists or the
    page does not resolve.  We never guess a printed page.
    """
    label_map = evidence.get("page_label_map")
    page_number = evidence.get("page_number")
    if not isinstance(label_map, dict) or not isinstance(page_number, int):
        return None
    for label, pdf_page in label_map.items():
        try:
            if int(pdf_page) == page_number:
                return str(label)
        except (TypeError, ValueError):
            continue
    return None


def _page_display(evidence):
    """Render 'p. <printed>' only when a label map resolves; else 'PDF page <n>'."""
    printed = _resolve_printed_page(evidence)
    if printed is not None:
        return f"p. {printed}"
    page = evidence.get("page_number")
    if isinstance(page, int) and page > 0:
        return f"PDF page {page}"
    return ""


def _citation_label(topic_name, evidence_list):
    """Format provenance labels for ALL retrieved evidence; never invent a page."""
    if not evidence_list:
        return ""
    labels = []
    for evidence in evidence_list:
        evidence_id = evidence.get("evidence_id") or "S?"
        document = evidence.get("doc_id") or "Unknown document"
        page_display = _page_display(evidence)
        page_suffix = f", {page_display}" if page_display else ""
        labels.append(f"[{evidence_id}: {topic_name} | {document}{page_suffix}]")
    return " " + " ".join(labels)


def _normalize_legacy_citation(citation):
    """Lift a legacy get_concept_citations record into the evidence contract."""
    return {
        "chunk_id": None,
        "doc_id": citation.get("doc_id"),
        "page_number": citation.get("page_number"),
        "section_title": citation.get("section_title"),
        "text": citation.get("text_passage"),
        "text_offset_start": None,
        "text_offset_end": None,
        "block_bbox": None,
        "doc_title": None,
        "page_label_map": None,
    }


__all__ = [
    "_citation_label",
    "_evidence_for_concept",
    "_evidence_for_prerequisite",
    "_normalize_legacy_citation",
    "_page_display",
    "_resolve_printed_page",
    "build_concept_citation_map",
]


def _evidence_for_concept(graph_db, concept_id, concept_name):
    """Fetch evidence for one concept, falling back to the legacy Kuzu lookup."""
    if graph_db is not None:
        try:
            evidence = graph_db.get_evidence_for_concept(concept_name)
            if evidence:
                return evidence
        except Exception as e:
            print(f"Evidence retrieval error for concept '{concept_name}': {e}")
    return [
        _normalize_legacy_citation(c)
        for c in get_concept_citations(concept_id, limit=1, concept_names=[concept_name])
    ]


def _evidence_for_prerequisite(graph_db, prereq_name, target_name):
    """Fetch edge-level evidence for a prerequisite relation, if indexed.

    REQUIRES edges are stored target -> prerequisite (see get_graph_neighborhood),
    but the evidence API's source/target orientation is the edge author's call,
    so both orders are tried before giving up.
    """
    if graph_db is None:
        return None
    for source, target in ((target_name, prereq_name), (prereq_name, target_name)):
        try:
            evidence = graph_db.get_evidence_for_edge(source, target)
        except Exception as e:
            print(f"Evidence retrieval error for edge {source} -> {target}: {e}")
            return None
        if evidence:
            # Accept either a single evidence dict or a list of them.
            return [evidence] if isinstance(evidence, dict) else evidence
    return None


def build_concept_citation_map(target_concept, prereqs, unlocks, graph_db=None):
    """Return evidence keyed by concept id for all displayed roadmap steps.

    Evidence IDs (``S1``, ``S2``, ...) come from a single counter assigned in
    render order — prerequisites, then the target, then unlocks — so the IDs
    in the rendered text, the model contract, and the structured payloads all
    agree.  Prerequisite steps prefer edge-level evidence (the passage that
    grounds the REQUIRES relation itself) and fall back to concept-level
    evidence.  ``graph_db`` may be injected (e.g. a mock) for tests; it
    defaults to okf.graph_db, with the legacy Kuzu lookup as a last resort.
    """
    if graph_db is None:
        graph_db = _default_graph_db()

    # Accept both dict (with "id" key) and string (concept_id) for target_concept
    if isinstance(target_concept, str):
        target_id = target_concept
        target = st.CONCEPTS_DATA.get(target_concept) or {}
        target_name = target.get("label") or target.get("name") or target_concept.replace("_", " ")
    else:
        target_id = target_concept.get("id", "")
        target_name = _node_name(target_concept)

    counter = itertools.count(1)
    citation_map = {}

    def assign(concept_id, evidence_list):
        tagged = []
        for evidence in (evidence_list or [])[: st.EVIDENCE_PER_CONCEPT]:
            entry = dict(evidence)
            entry["evidence_id"] = f"S{next(counter)}"
            tagged.append(entry)
        citation_map[concept_id] = tagged

    for item in prereqs[: st.MAX_PREREQS_SHOWN]:
        concept_id = item.get("id")
        if not concept_id or concept_id in citation_map:
            continue
        name = _node_name(item)
        evidence = _evidence_for_prerequisite(graph_db, name, target_name)
        if not evidence:
            evidence = _evidence_for_concept(graph_db, concept_id, name)
        assign(concept_id, evidence)

    if target_id not in citation_map:
        assign(target_id, _evidence_for_concept(graph_db, target_id, target_name))

    for item in unlocks[: st.MAX_UNLOCKS_SHOWN]:
        concept_id = item.get("id")
        if not concept_id or concept_id in citation_map:
            continue
        assign(concept_id, _evidence_for_concept(graph_db, concept_id, _node_name(item)))

    return citation_map

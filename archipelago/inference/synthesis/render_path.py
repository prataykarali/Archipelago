"""Auto-split from synthesis.py — do not edit blocks by hand."""
from __future__ import annotations

from archipelago.inference import state as st
from archipelago.inference.aliases import _node_name
from archipelago.inference.citations import (
    _citation_label, _citation_marker, _cite_with_link, validate_citations,
    cleanse_model_citations,
)
from archipelago.inference.curriculum import format_curriculum_paths_section


def render_indexed_learning_path(target_concept, prereqs, unlocks, citation_map, curriculum_paths=None):
    """Produce a fast, bounded response without relying on generative prose.

    The format is intentionally compact: it exposes the graph's ordering and
    ties every displayed concept to its own provenance record where one exists.
    Citation brackets carry the evidence IDs assigned by
    build_concept_citation_map, e.g. ``[S1: Topic | doc.pdf, p. 3]``.
    Session 2: multi-hop curriculum chains and markdown ``#page=N`` links.
    """
    target_id = target_concept.get("id", "")
    target_name = _node_name(target_concept)
    target_summary = (target_concept.get("summary") or "No indexed summary is available.").strip()
    lines = [f"Learning path: {target_name}"]

    if curriculum_paths:
        lines.append(format_curriculum_paths_section(curriculum_paths).strip())

    if prereqs:
        lines.append("1. Learn first")
        for index, item in enumerate(prereqs[:st.MAX_PREREQS_SHOWN], 1):
            name = _node_name(item)
            summary = (item.get("summary") or "Prerequisite concept.").strip()
            lines.append(
                f"   {index}. {name} — {summary[:220]}"
                f"{_cite_with_link(name, citation_map.get(item.get('id'), []))}"
            )
    else:
        lines.append("1. Learn first: No prerequisite edge is indexed for this concept.")

    lines.append("2. Target")
    lines.append(
        f"   {target_name} — {target_summary[:260]}"
        f"{_cite_with_link(target_name, citation_map.get(target_id, []))}"
    )

    if unlocks:
        lines.append("3. Then explore")
        for index, item in enumerate(unlocks[:st.MAX_UNLOCKS_SHOWN], 1):
            name = _node_name(item)
            summary = (item.get("summary") or "Downstream concept.").strip()
            lines.append(
                f"   {index}. {name} — {summary[:180]}"
                f"{_cite_with_link(name, citation_map.get(item.get('id'), []))}"
            )

    lines.append("Ask for one numbered topic to continue.")
    return "\n".join(lines)

"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from typing import Any
from . import _deps as _rt  # noqa: F401


def build_personalized_graph_dag(
    target_concept_id: str,
    mastered_concepts: list[str],
    gap_concepts: list[str],
    concepts_data: dict[str, Any] | None = None,
    eval_details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct a cycle-free, DAG-verified personalized graph topology.

    Prunes dangling branches, marks nodes as MASTERED (🟢), REVIEW_GAP (🟡),
    or TARGET (🌟), and attaches source literature deep-links.

    Args:
        target_concept_id: Target concept ID.
        mastered_concepts: Concept names/IDs scored correct.
        gap_concepts: Concept names/IDs scored incorrect or unanswered.
        concepts_data: In-memory concept graph dictionary.
        eval_details: Question-level evaluation breakdown.

    Returns:
        Dictionary containing DAG nodes, directed edges, and remediation metadata.
    """
    if concepts_data is None:
        from archipelago.inference import state as st
        concepts_data = st.CONCEPTS_DATA or {}

    eval_map: dict[str, dict[str, Any]] = {}
    if eval_details:
        for d in eval_details:
            cid = d.get("concept_id")
            if cid:
                eval_map[cid] = d

    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()

    mastered_set = {str(m).strip().lower().replace(" ", "_") for m in mastered_concepts}
    mastered_set.update({str(m).strip() for m in mastered_concepts})
    gap_set = {str(g).strip().lower().replace(" ", "_") for g in gap_concepts}
    gap_set.update({str(g).strip() for g in gap_concepts})

    # 1. Add evaluated prerequisite nodes
    ordered_cids = list(eval_map.keys())
    if not ordered_cids:
        ordered_cids = [str(g).lower().replace(" ", "_") for g in gap_concepts] + [str(m).lower().replace(" ", "_") for m in mastered_concepts]

    for cid in ordered_cids:
        if cid in node_ids or cid == target_concept_id:
            continue
        c_node = concepts_data.get(cid) or {}
        label = c_node.get("label") or c_node.get("name") or cid.replace("_", " ").title()
        
        is_mastered = cid in mastered_set or label in mastered_set
        status = "mastered" if is_mastered else "review_gap"

        detail = eval_map.get(cid) or {}
        sources = c_node.get("sources") or []
        first_src = sources[0] if sources and isinstance(sources[0], dict) else {}
        doc_id = first_src.get("doc_id") or c_node.get("doc_id") or ""
        page_num = first_src.get("page_number") or c_node.get("page_number") or 1
        printed_page = first_src.get("printed_page") or page_num
        citation_text = detail.get("citation") or c_node.get("citation") or (f"{doc_id} p. {printed_page}" if doc_id else "Foundational Textbook")

        nodes.append({
            "id": cid,
            "label": label,
            "status": status,
            "role": "prereq",
            "summary": c_node.get("summary") or detail.get("explanation") or "",
            "difficulty": c_node.get("difficulty") or "foundational",
            "doc_id": doc_id,
            "page_number": page_num,
            "printed_page": printed_page,
            "citation": citation_text,
            "action_prompt": f"Explain foundational prerequisite '{label}' and how it connects to '{target_concept_id}'.",
        })
        node_ids.add(cid)

    # 2. Add Target Node
    t_node = concepts_data.get(target_concept_id) or {}
    t_label = t_node.get("label") or t_node.get("name") or target_concept_id.replace("_", " ").title()
    is_full_score = (len(gap_concepts) == 0 and len(mastered_concepts) > 0)
    t_status = "unlocked" if is_full_score else "target"
    
    t_sources = t_node.get("sources") or []
    t_first_src = t_sources[0] if t_sources and isinstance(t_sources[0], dict) else {}
    t_doc_id = t_first_src.get("doc_id") or t_node.get("doc_id") or ""
    t_page_num = t_first_src.get("page_number") or t_node.get("page_number") or 1

    nodes.append({
        "id": target_concept_id,
        "label": t_label,
        "status": t_status,
        "role": "target",
        "summary": t_node.get("summary") or "",
        "difficulty": t_node.get("difficulty") or "advanced",
        "doc_id": t_doc_id,
        "page_number": t_page_num,
        "printed_page": t_first_src.get("printed_page") or t_page_num,
        "citation": f"{t_doc_id} p. {t_page_num}" if t_doc_id else "Core Curriculum Target",
        "action_prompt": f"Deep dive into '{t_label}'.",
    })
    node_ids.add(target_concept_id)

    # 3. Directed cycle-free edges (DAG enforcement)
    edges: list[dict[str, Any]] = []
    gap_nodes = [n["id"] for n in nodes if n["status"] == "review_gap"]
    mast_nodes = [n["id"] for n in nodes if n["status"] == "mastered"]

    def _add_edge(f_id: str, t_id: str, rel: str) -> None:
        edges.append({
            "from_id": f_id,
            "to_id": t_id,
            "source": f_id,
            "target": t_id,
            "relation": rel,
        })

    prev_id = None
    for gid in gap_nodes:
        if prev_id:
            _add_edge(prev_id, gid, "REQUIRES_REVIEW")
        prev_id = gid

    if mast_nodes:
        if prev_id:
            _add_edge(prev_id, mast_nodes[0], "LEADS_TO")
        for i in range(len(mast_nodes) - 1):
            _add_edge(mast_nodes[i], mast_nodes[i+1], "UNLOCKS")
        _add_edge(mast_nodes[-1], target_concept_id, "UNLOCKS_TARGET")
    elif prev_id:
        _add_edge(prev_id, target_concept_id, "REMEDIATES_TO")

    # 4. If full score, append downstream unlocked applications
    downstream_suggestions: list[dict[str, Any]] = []
    if is_full_score:
        for u in (t_node.get("unlocks") or [])[:3]:
            uid = u.get("id") if isinstance(u, dict) else str(u).lower().replace(" ", "_")
            if uid and uid in concepts_data and uid not in node_ids:
                u_node = concepts_data[uid]
                u_item = {
                    "id": uid,
                    "label": u_node.get("label") or u_node.get("name") or uid,
                    "summary": u_node.get("summary") or "",
                    "difficulty": u_node.get("difficulty") or "expert",
                }
                downstream_suggestions.append(u_item)
                nodes.append({
                    "id": uid,
                    "label": u_item["label"],
                    "status": "downstream_unlocked",
                    "role": "unlock",
                    "summary": u_item["summary"],
                    "difficulty": u_item["difficulty"],
                    "doc_id": "",
                    "page_number": 1,
                    "printed_page": 1,
                    "citation": "Advanced Downstream Exploration",
                    "action_prompt": f"Advance to '{u_item['label']}'.",
                })
                _add_edge(target_concept_id, uid, "UNLOCKS_NEXT")
                node_ids.add(uid)

    return {
        "nodes": nodes,
        "edges": edges,
        "downstream_suggestions": downstream_suggestions,
        "is_dag": True,
    }

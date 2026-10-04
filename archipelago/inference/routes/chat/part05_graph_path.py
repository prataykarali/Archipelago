"""Chat route handler: graph RAG path (embedder ranking + traversal + synthesis)."""

from __future__ import annotations

import json

from flask import Response

from archipelago.inference import state as st
from archipelago.inference.aliases import _node_name
from archipelago.inference.citations import (
    _resolve_printed_page,
    build_citation_payloads,
    build_concept_citation_map,
    cleanse_model_citations,
)
from archipelago.inference.curriculum import (
    find_curriculum_chains,
    format_curriculum_paths_section,
)
from archipelago.inference.graph_lock import graph_lock
from archipelago.inference.neighborhood import get_graph_neighborhood
from archipelago.inference.routes.chat.part00_shared import with_holdings
from archipelago.inference.synthesis import (
    build_graph_notes,
    enforce_sterile_prose,
    format_natural_fallback,
    general_chat_reply,
    stream_synthesis_with_ollama,
)


def handle_graph_path(query, history, routing, wants_synthesis):
    """Graph path (strong or soft domain): traverse, cite, synthesize."""
    with graph_lock.read_lock():
        anchor_id = routing.get("anchor_id")
        related = routing.get("related") or []
        if not anchor_id or anchor_id not in st.CONCEPTS_DATA:
            # Soft path without a usable id → still try top related list
            if related and related[0]["id"] in st.CONCEPTS_DATA:
                anchor_id = related[0]["id"]
            else:

                def generate_orphan():
                    payload = {
                        "logs": [
                            {
                                "step": "Pass 1: Retrieval",
                                "status": "Empty graph",
                                "details": "No concepts loaded in st.CONCEPTS_DATA.",
                            }
                        ],
                        "citations": [],
                    }
                    yield json.dumps(payload) + "\n[STREAM_START]\n"
                    yield general_chat_reply(query, history)

                return Response(generate_orphan(), mimetype="text/plain")

        target_concept = st.CONCEPTS_DATA[anchor_id]
        prereqs, unlocks, _legacy_cites = get_graph_neighborhood(anchor_id, k=2)
        # Soft multi-anchor: pull light neighborhoods for top related peers
        related_nodes = []
        for r in related[: st.TOP_K_RELATED]:
            rid = r.get("id")
            if not rid or rid == anchor_id or rid not in st.CONCEPTS_DATA:
                continue
            node = st.CONCEPTS_DATA[rid]
            related_nodes.append(
                {
                    "id": rid,
                    "name": node.get("label") or node.get("name") or rid,
                    "summary": node.get("summary") or r.get("summary") or "",
                    "cos": r.get("cos"),
                }
            )

        citation_map = build_concept_citation_map(target_concept, prereqs, unlocks)
        citation_payloads = build_citation_payloads(target_concept, prereqs, unlocks, citation_map)
        # Curated reading suggestions are not retrieved evidence. Never add
        # demo pages to the graph citation contract.
        citation_payloads = [item for item in citation_payloads if item.get("doc_id")]
        evidence_ids = {
            payload["evidence_id"] for payload in citation_payloads if payload["evidence_id"]
        }
        # Session 2: multi-hop curriculum chains (≤3 hops) with book/page links
        curriculum_paths = find_curriculum_chains(
            anchor_id, max_hops=3, citation_map=citation_map, max_paths=4
        )
        notes = build_graph_notes(
            query,
            target_concept,
            prereqs,
            unlocks,
            related,
            citation_map,
            bare_markers=True,
        )
        if curriculum_paths:
            notes = notes + "\n" + format_curriculum_paths_section(curriculum_paths)
        is_partial = bool((routing.get("slots") or {}).get("partial")) or (
            routing.get("reason") == "partial_coverage_low_cos"
        )
        natural_fallback = format_natural_fallback(
            query,
            target_concept,
            prereqs,
            unlocks,
            related,
            citation_map,
            curriculum_paths=curriculum_paths,
            partial=is_partial,
        )
        natural_fallback = cleanse_model_citations(natural_fallback, citation_payloads)
        match_score = routing.get("score")
        step_logs = [
            {
                "step": "Pass 1: Embedder Ranking",
                "status": (
                    "Partial coverage"
                    if is_partial
                    else ("Success" if routing["route"] == "graph_strong" else "Soft domain match")
                ),
                "details": (
                    f"Route={routing['route']}; anchor=**{_node_name(target_concept)}** "
                    f"(score={match_score if isinstance(match_score, (int, float)) else match_score}); "
                    f"reason={routing.get('reason')}; top related="
                    f"{', '.join(r.get('label', '') for r in related[:3])}"
                ),
            },
            {
                "step": "Pass 2: Graph Traversal & Citations",
                "status": "Success",
                "details": (
                    f"Traversed {len(prereqs)} prerequisites and {len(unlocks)} unlocks; "
                    f"{len(citation_payloads)} evidence records; "
                    f"{len(related_nodes)} embedder neighbors; "
                    f"{len(curriculum_paths)} multi-hop curriculum path(s)."
                ),
            },
            {
                "step": "Pass 3: Natural Synthesis",
                "status": "Requested" if wants_synthesis else "Template",
                "details": (
                    f"{st.GEMINI_MODEL} natural wording over graph notes "
                    "(falls back to structured natural summary if offline)"
                    if wants_synthesis
                    else "Structured natural summary without generator."
                ),
            },
        ]

        # Mode A / B / C bounded subgraph and diagnostic MCQ layer
        query_mode = routing.get("query_mode") or "mode_a"
        secondary_concept = None
        if query_mode == "mode_b" and len(related_nodes) > 0:
            secondary_concept = related_nodes[0].get("id")

        from archipelago.inference.subgraph import generate_bounded_subgraph

        bounded_subgraph = generate_bounded_subgraph(
            anchor_id,
            secondary_target_id=secondary_concept,
            mode=query_mode,
        )

        diagnostic_mcqs = []
        try:
            from archipelago.inference.diagnostic_mcq import generate_diagnostic_mcqs

            prereq_ids = [p["id"] for p in prereqs if isinstance(p, dict) and p.get("id")]
            diagnostic_mcqs = generate_diagnostic_mcqs(
                anchor_id,
                prereq_ids=prereq_ids,
                num_questions=3,
            )
        except Exception as exc:
            print(f"Pre-cached MCQ generation fallback triggered: {exc}")
            diagnostic_mcqs = []

        def generate_graph():
            init_payload = {
                "anchor_concept": target_concept,
                "query_mode": query_mode,
                "subgraph": bounded_subgraph.to_dict(),
                "diagnostic_mcqs": diagnostic_mcqs,
                "prerequisites": prereqs,
                "unlocks": unlocks,
                "related_concepts": related_nodes,
                "curriculum_paths": curriculum_paths,
                "citations": citation_payloads,
                "routing": {
                    "route": routing["route"],
                    "score": routing.get("score"),
                    "reason": routing.get("reason"),
                    "query_mode": query_mode,
                },
                "citation_by_concept": {
                    concept_id: [
                        {
                            "evidence_id": evidence.get("evidence_id"),
                            "doc_id": evidence.get("doc_id"),
                            "page_number": evidence.get("page_number"),
                            "printed_page": _resolve_printed_page(evidence),
                            "section_title": evidence.get("section_title"),
                        }
                        for evidence in concept_evidence
                    ]
                    for concept_id, concept_evidence in citation_map.items()
                },
                "logs": step_logs,
            }
            sterile = bool((routing.get("slots") or {}).get("sterile"))
            yield json.dumps(init_payload) + "\n[STREAM_START]\n"
            if wants_synthesis:
                try:
                    had_tokens = False
                    accumulated = []
                    for token in stream_synthesis_with_ollama(
                        notes,
                        evidence_ids=evidence_ids,
                        user_query=query,
                        citation_payloads=citation_payloads,
                        sterile=sterile,
                        fallback_text=natural_fallback,
                        history=history,
                    ):
                        had_tokens = True
                        accumulated.append(token)
                        yield token

                    if not had_tokens:
                        fallback_prose = (
                            enforce_sterile_prose(natural_fallback) if sterile else natural_fallback
                        )
                        yield "\n[STREAM_DONE]\n" + with_holdings(query, fallback_prose, citations=citation_payloads)
                    else:
                        final = cleanse_model_citations("".join(accumulated), citation_payloads)
                        yield "\n[STREAM_DONE]\n" + with_holdings(query, final, citations=citation_payloads)
                    return
                except Exception:
                    # Keep real retrieved material usable when inference is unavailable.
                    # The fallback is deterministically grounded before it reaches the UI.
                    yield "\n[STREAM_DONE]\n" + with_holdings(query, natural_fallback, citations=citation_payloads)
                    return
            fallback_prose = (
                enforce_sterile_prose(natural_fallback) if sterile else natural_fallback
            )
            yield with_holdings(query, fallback_prose, citations=citation_payloads)

        return Response(generate_graph(), mimetype="text/plain")

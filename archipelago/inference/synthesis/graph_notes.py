"""Auto-split from synthesis.py — do not edit blocks by hand."""
from __future__ import annotations

import json
import kuzu
import torch
import google.generativeai as genai
from archipelago.inference.llm_gateway import gateway_chat, gateway_chat_stream, gateway_chat_with_tools, is_llm_available, LLM_UNAVAILABLE_MSG, configure_gateway
from archipelago.inference.graph_lock import graph_lock
from archipelago.inference import state as st
from archipelago.inference.aliases import _node_name
from archipelago.inference.citations import (
    _citation_label, _citation_marker, _cite_with_link, validate_citations,
    cleanse_model_citations,
)
from archipelago.inference.curriculum import format_curriculum_paths_section


def _summarize_evidence(evidence_list, max_chars=140):
    """Extract the most useful sentence(s) from evidence text passages.

    Returns a short string of the most relevant content from the source text,
    skipping bibliography/reference-heavy passages. This injects actual
    page-level text into graph notes so the LLM has real content to synthesize,
    not just metadata labels.
    """
    seen = set()
    snippets = []
    for ev in (evidence_list or []):
        text = (ev.get("text") or ev.get("text_passage") or "").strip()
        if not text or len(text) < 15:
            continue
        # Dedupe near-duplicate passages
        norm = " ".join(text.lower().split()[:8])
        if norm in seen:
            continue
        seen.add(norm)
        # Skip bibliography / pure reference passages
        lower = text.lower()
        if lower.count("et al") >= 3 and len(lower) < 200:
            continue
        # Take first substantial sentence, capped
        first = text.split(".")[0] if "." in text[:200] else text[:max_chars]
        snippets.append(first[:max_chars].strip())
        if len(snippets) >= 2:
            break
    return "; ".join(snippets) if snippets else ""


def build_graph_notes(user_query, target_concept, prereqs, unlocks, related, citation_map,
                      bare_markers=False):
    """Structured notes for the synthesizer (not shown raw to the user by default).

    With ``bare_markers`` the notes carry only ``[S#]`` markers (the generator
    contract for the post-hoc provenance pass); otherwise full labels.

    Injects actual text passages from source documents so the LLM has real
    content to work with — not just metadata labels. Without this hybrid
    context injection, the LLM sees only concept names + summaries and
    defensively rejects even grounded queries.
    """
    target_name = _node_name(target_concept)
    target_summary = (target_concept.get("summary") or "").strip()
    tid = target_concept.get("id", "")
    target_evidence_text = _summarize_evidence(citation_map.get(tid, []), max_chars=300)

    lines = [
        f"User question: {user_query}",
        f"Primary concept: {target_name}",
        f"Summary: {target_summary or 'No summary stored.'}",
    ]
    if target_evidence_text:
        lines.append(f"Source text on page: \"{target_evidence_text}\"")
    if bare_markers and citation_map.get(tid):
        lines[-1] += _citation_marker(citation_map[tid], bare_markers)
    if prereqs:
        lines.append("Prerequisites (from graph traversal):")
        for item in prereqs[:st.MAX_PREREQS_SHOWN]:
            name = _node_name(item)
            summ = (item.get("summary") or "")[:200]
            ev_text = _summarize_evidence(citation_map.get(item.get("id"), []))
            marker = _citation_marker(citation_map.get(item.get("id"), []), bare_markers) if bare_markers else \
                _citation_label(name, citation_map.get(item.get("id"), []))
            if ev_text:
                if bare_markers:
                    lines.append(f"  - {name}: {summ} [Source text: \"{ev_text}\"]{marker}")
                else:
                    lines.append(f"  - {name}: {summ} [Source text: \"{ev_text}\"]{marker}")
            else:
                if bare_markers:
                    lines.append(f"  - {name}: {summ}{marker}")
                else:
                    lines.append(f"  - {name}: {summ}{marker}")
    if unlocks:
        lines.append("What this unlocks / related downstream:")
        for item in unlocks[:st.MAX_UNLOCKS_SHOWN]:
            name = _node_name(item)
            summ = (item.get("summary") or "")[:160]
            ev_text = _summarize_evidence(citation_map.get(item.get("id"), []))
            marker = _citation_marker(citation_map.get(item.get("id"), []), bare_markers) if bare_markers else \
                _citation_label(name, citation_map.get(item.get("id"), []))
            if ev_text:
                if bare_markers:
                    lines.append(f"  - {name}: {summ} [Source text: \"{ev_text}\"]{marker}")
                else:
                    lines.append(f"  - {name}: {summ} [Source text: \"{ev_text}\"]{marker}")
            else:
                if bare_markers:
                    lines.append(f"  - {name}: {summ}{marker}")
                else:
                    lines.append(f"  - {name}: {summ}{marker}")
    # Related neighbors from embedder ranking (soft path)
    if related:
        lines.append("Nearest graph concepts by embedding similarity:")
        for r in related[:st.TOP_K_RELATED]:
            if r.get("id") == target_concept.get("id"):
                continue
            lines.append(
                f"  - {r.get('label')} (score={float(r.get('cos') or 0):.3f}): "
                f"{(r.get('summary') or '')[:140]}"
            )
    target_id = target_concept.get("id", "")
    if not bare_markers:
        lines.append(
            f"Target citations:{_citation_label(target_name, citation_map.get(target_id, []))}"
        )
    return "\n".join(lines)


def format_natural_fallback(user_query, target_concept, prereqs, unlocks, related, citation_map,
                            curriculum_paths=None, partial=False):
    """Human-readable answer when Ollama is unavailable — never dump raw notes.

    Session 2: multi-hop curriculum paths and in-bubble ``#page=N`` markdown links.
    When ``partial`` is True, acknowledge soft/family coverage instead of overclaiming.
    """
    target_name = _node_name(target_concept)
    target_summary = (target_concept.get("summary") or "").strip()
    cite = _cite_with_link(target_name, citation_map.get(target_concept.get("id"), []))
    parts = []
    if partial:
        parts.append(
            f"I have **partial coverage** for what you asked. The closest concept family "
            f"in this library graph is **{target_name}** — here's what we index about it "
            f"(coverage may be incomplete)."
        )
    else:
        parts.append(f"**{target_name}** is covered in this library.")
    if target_summary:
        parts.append(f"\n{target_summary}{cite}")
    # Prefer a short curriculum path over dumping every neighbor
    path_section = format_curriculum_paths_section(curriculum_paths)
    if path_section:
        parts.append(path_section)
    elif prereqs:
        parts.append("\n**Learn first:**")
        for item in prereqs[: min(2, st.MAX_PREREQS_SHOWN)]:
            name = _node_name(item)
            summ = (item.get("summary") or "").strip()
            line = f"- **{name}**"
            if summ:
                line += f" — {summ[:140]}"
            line += _cite_with_link(name, citation_map.get(item.get("id"), []))
            parts.append(line)
    peers = [
        r for r in (related or [])
        if r.get("id") != target_concept.get("id")
    ][:3]
    if peers and not path_section:
        parts.append("\n**Nearby topics:**")
        for r in peers:
            label = r.get("label") or r.get("name") or r.get("id")
            parts.append(f"- **{label}**")
    if unlocks:
        parts.append("\n**What this opens up:**")
        for item in unlocks[: min(2, st.MAX_UNLOCKS_SHOWN)]:
            name = _node_name(item)
            summ = (item.get("summary") or "").strip()
            parts.append(
                f"- **{name}**"
                + (f" — {summ[:120]}" if summ else "")
            )
    if peers or prereqs or unlocks:
        parts.append("\nAsk about a linked concept to continue the study path.")
    return "\n".join(parts)


def generate_aura_synthesis(recipe):
    if not st.aura_loaded:
        return "Error: Local generator model (aura-qwen) is not loaded."
    messages = [{"role": "user", "content": recipe}]
    try:
        prompt = st.aura_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = st.aura_tokenizer(prompt, return_tensors="pt").to(st.aura_model.device)
        with torch.no_grad():
            outputs = st.aura_model.generate(
                **inputs,
                max_new_tokens=2048,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
            )
        generated_ids = outputs[0][inputs.input_ids.shape[1]:]
        response = st.aura_tokenizer.decode(generated_ids, skip_special_tokens=True)
        return response
    except Exception as e:
        return f"Error during model synthesis: {e}"


def run_ollama_agent(messages):
    """Agent with function calling via Gemini gateway."""
    tools = [{
        'type': 'function',
        'function': {
            'name': 'query_database',
            'description': 'Execute a Cypher query on the KuzuDB graph database. Available node tables: Document (id), Chunk (id, chunk_id, page_number, section_title, text_passage), Concept (id, name, concept_type, difficulty, summary). Relationships: HAS_CHUNK (Doc->Chunk), MENTIONS (Chunk->Concept), REQUIRES (Concept->Concept), UNLOCKS (Concept->Concept), RELATED (Concept->Concept).',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'The Cypher query to execute.',
                    },
                },
                'required': ['query'],
            },
        },
    }]

    # Convert tools to Gemini function declaration format
    gemini_tools = [genai.protos.Tool(
        function_declarations=[genai.protos.FunctionDeclaration(
            name='query_database',
            description='Execute a Cypher query on the KuzuDB graph database.',
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    'query': genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description='The Cypher query to execute.',
                    )
                },
                required=['query'],
            ),
        )]
    )]

    try:
        text, tool_calls = gateway_chat_with_tools(
            messages=messages,
            tools=gemini_tools,
            purpose="agent",
        )
        tool_logs = []

        if tool_calls:
            for tc in tool_calls:
                func_name = tc.get('name')
                query = tc.get('args', {}).get('query')
                if func_name == 'query_database' and query:
                    print(f"Gemini calling query_database: {query}")
                    try:
                        with graph_lock.read_lock():
                            conn = kuzu.Connection(st.db)
                            res = conn.execute(query)
                            cols = res.get_column_names()
                            rows = []
                            while res.has_next():
                                rows.append(res.get_next())
                            tool_result = {"columns": cols, "rows": rows}
                            log_msg = f"Executed Cypher:\n{query}\n\nResult: Found {len(rows)} records."
                    except Exception as e:
                        tool_result = {"error": str(e)}
                        log_msg = f"Failed Cypher:\n{query}\n\nError: {e}"
                    tool_logs.append({"tool": "query_database", "query": query, "log": log_msg})

                    # Second call with tool result
                    messages.append({"role": "assistant", "content": f"Tool call: query_database({query})"})
                    messages.append({"role": "user", "content": f"Tool result: {json.dumps(tool_result)}"})

            final_text = gateway_chat(messages=messages, purpose="agent")
            return final_text or text, tool_logs
        else:
            return text, []
    except Exception as e:
        return f"Error connecting to Gemini API: {e}", []

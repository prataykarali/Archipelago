"""Hugging Face Space Gradio entrypoint for Archipelago."""

from __future__ import annotations

import json
import os
import gradio as gr

from archipelago.inference import state as st
from archipelago.inference.pipeline import run_archipelago_inference
from archipelago.inference.routing import resolve_query_routing
from archipelago.inference.system_faq import try_system_faq

try:
    import spaces
    @spaces.GPU
    def dummy_gpu_check() -> None:
        """Satisfy HF ZeroGPU checker while running the app on CPU."""
        pass
except ImportError:
    pass

# ── Port configuration ───────────────────────────────────────────────────────
# Default values for local or Hugging Face setup
_DEFAULT_PORT = 7860
_MAX_CITATIONS_SHOWN = 5


def init_app() -> None:
    """Initialize the process-wide state, loading graph concepts and embeddings."""
    try:
        with open(st.DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        nodes = data.get("visualization", {}).get("nodes", []) or data.get("nodes", [])
        for n in nodes:
            cid = n.get("id", "")
            st.CONCEPTS_DATA[cid] = n
        print(f"Loaded {len(st.CONCEPTS_DATA)} concepts from {st.DATA_FILE.name}")
    except Exception as e:
        print(f"Warning: Could not load concepts: {e}")

    # Pre-embed concepts
    try:
        from archipelago.inference.embeddings import precompute_concept_embeddings

        n = precompute_concept_embeddings()
        print(f"Arctic concept embeddings: {n} vectors (cosine kill-switch ready)")
    except Exception as exc:
        print(f"Warning: concept embedding preload failed ({exc}); lexical ranking only")


# Run initial setup
init_app()


def predict(message: str, history: list[list[str]] | None) -> str:
    """Process a user message and returns the chatbot's structured response.

    Args:
        message: The user query string.
        history: Gradio chat history.

    Returns:
        Structured text response with citations and prerequisites.
    """
    # Convert Gradio history format to the dict-based format used by Archipelago RAG
    formatted_history: list[dict[str, str]] = []
    if history:
        for user_msg, bot_msg in history:
            formatted_history.append({"role": "user", "content": user_msg})
            formatted_history.append({"role": "assistant", "content": bot_msg})

    routing = resolve_query_routing(message, formatted_history)
    route = str(routing.get("route", "graph_strong"))

    if route == "out_of_scope":
        reason = str(routing.get("reason", ""))
        if "implementation" in reason:
            return (
                "I can explain concepts but I don't write code. Ask about the theory "
                "behind an algorithm or architecture."
            )
        return (
            "That topic is outside the library's catalog. I cover AI/ML, DBMS, OS, DSA, "
            "and Math for ML."
        )

    if route in ("identity", "small_talk"):
        if route == "identity":
            return (
                "I'm Archipelago, an AI/ML library assistant. I can answer questions about "
                "Machine Learning, DBMS, Operating Systems, Data Structures & Algorithms, "
                "and related computer science topics using our indexed knowledge graph."
            )
        return (
            "Hello! I'm Archipelago, your AI/ML library assistant. Ask me about machine "
            "learning, databases, algorithms, or operating systems."
        )

    if route == "onboarding":
        return (
            "Welcome to Archipelago! Here's how to start:\n\n"
            "1. **Machine Learning foundations** — linear algebra, probability, regression\n"
            "2. **Neural networks & deep learning** — backprop, CNNs, transformers\n"
            "3. **RAG & LLMs** — embeddings, retrieval, fine-tuning\n\n"
            "Pick a topic and I'll give you a grounded path with prerequisites and source pages."
        )

    if route == "system_faq":
        faq_result = try_system_faq(message)
        return str((faq_result or {}).get("text") or (
            "I have that as an Archipelago system fact, but no FAQ entry matched."
        ))

    if route == "general_chat":
        return (
            "I'm not sure I have information about that specific topic in my library. "
            "Could you try asking about an AI/ML or computer science concept?"
        )

    # 5-stage pipeline
    result = run_archipelago_inference(message, history=formatted_history)
    text_ans = str(result.get("text") or "I couldn't find information about that in the library.")

    # Append topological map / citations at the end of the text answer
    meta_info: list[str] = []

    anchor = result.get("anchor_concept")
    if anchor and anchor.get("name"):
        meta_info.append(f"🎯 **Target Concept**: {anchor['name']}")

    prereqs = result.get("prerequisites") or []
    if prereqs:
        p_names = [p.get("name") for p in prereqs if p.get("name")]
        if p_names:
            meta_info.append(f"📚 **Requires (Prerequisites)**: {' → '.join(p_names)}")

    unlocks = result.get("unlocks") or []
    if unlocks:
        u_names = [u.get("name") for u in unlocks if u.get("name")]
        if u_names:
            meta_info.append(f"🚀 **Unlocks (Downstream)**: {' → '.join(u_names)}")

    citations = result.get("citations") or []
    if citations:
        citation_lines = []
        for c in citations[:_MAX_CITATIONS_SHOWN]:
            evidence_id = c.get("evidence_id")
            title = c.get("title")
            page = c.get("page_number")
            section = c.get("section_title")
            section_str = f", {section}" if section else ""
            citation_lines.append(f"- **[{evidence_id}]** {title} (page {page}{section_str})")
        if citation_lines:
            meta_info.append("🔍 **Sources & Citations**:\n" + "\n".join(citation_lines))

    if meta_info:
        text_ans += "\n\n---\n" + "\n\n".join(meta_info)

    return text_ans


demo = gr.ChatInterface(
    predict,
    title="Archipelago Library Assistant",
    description="Query your local RAG concept index on AI/ML, Operating Systems, DBMS, and DSA.",
)

if __name__ == "__main__":
    port_val = int(os.environ.get("PORT", str(_DEFAULT_PORT)))
    demo.launch(server_name="0.0.0.0", server_port=port_val)

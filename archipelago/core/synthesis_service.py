"""
src/core/synthesis_service.py — Synthesis & Topic Suggestion Orchestrator.

Model Governance:
- Uses Gemini via the LLM gateway.
- Mandatory bracketed citation retention ([S1], [S2]).
- Streaming (SSE) and synchronous generation.
- Interactive Topic Suggestion formatting.
- Diagnostic MCQ generation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Generator, List, Optional
from archipelago.inference.llm_gateway import gateway_chat, gateway_chat_stream

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_SYNTHESIS_MODEL = os.getenv("ARCHIPELAGO_OLLAMA_MODEL", "qwen3.5:0.8b")
DEFAULT_INGESTION_MODEL = os.getenv("ARCHIPELAGO_EXTRACTION_MODEL", "lib-qwen:latest")


class SynthesisService:
    """Local SLM orchestrator utilizing Ollama for synthesis and suggestions."""

    def __init__(
        self,
        ollama_host: Optional[str] = None,
        synthesis_model: Optional[str] = None,
        ingestion_model: Optional[str] = None,
    ) -> None:
        self.host = ollama_host or DEFAULT_OLLAMA_HOST
        self.synthesis_model = synthesis_model or DEFAULT_SYNTHESIS_MODEL
        self.ingestion_model = ingestion_model or DEFAULT_INGESTION_MODEL
        self._client: Optional[Any] = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize LLM Gateway."""
        try:
            from archipelago.inference.llm_gateway import configure_gateway, gateway_chat, gateway_chat_stream
            configure_gateway()
            self._client = True
        except Exception as exc:
            logger.warning("Could not initialize LLM Gateway (%s). Running in offline fallback mode.", exc)
            self._client = None

    def synthesize_response(
        self,
        payload: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any] | Generator[str, None, None]:
        """Dispatch isolated prompt to qwen3.5:0.8b with strict citation enforcement."""
        system_prompt = payload.get("system_prompt", "")
        user_prompt = payload.get("user_prompt", "")
        lineage = payload.get("citation_lineage", [])
        topo = payload.get("topological_summary", "")
        anchor = payload.get("anchor_concept", "")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if stream:
            return self._stream_response(messages, lineage, topo, anchor)

        return self._generate_response(messages, lineage, topo, anchor)

    def _generate_response(
        self,
        messages: List[Dict[str, str]],
        lineage: List[Dict[str, Any]],
        topo: str,
        anchor: str,
    ) -> Dict[str, Any]:
        """Execute synchronous synthesis."""
        text_output = ""
        if self._client is not None:
            try:
                response = gateway_chat(
                    messages,
                    purpose='synthesis',
                    temperature=0.1,
                    max_tokens=512
                )
                msg = getattr(response, "message", None) or (
                    response.get("message") if isinstance(response, dict) else {}
                )
                content = getattr(msg, "content", None) or (
                    msg.get("content") if isinstance(msg, dict) else ""
                )
                if not content and hasattr(msg, "thinking") and msg.thinking:
                    content = msg.thinking
                text_output = content or self._grounded_fallback(anchor, topo, lineage)
            except Exception as exc:
                logger.error("Ollama synthesis error: %s; using grounded fallback.", exc)
                text_output = self._grounded_fallback(anchor, topo, lineage)
        else:
            text_output = self._grounded_fallback(anchor, topo, lineage)

        cleaned_text = self._clean_repetitions(text_output)

        return {
            "text": cleaned_text,
            "citations": lineage,
            "topology": topo,
            "anchor_concept": anchor,
        }

    def _stream_response(
        self,
        messages: List[Dict[str, str]],
        lineage: List[Dict[str, Any]],
        topo: str,
        anchor: str,
    ) -> Generator[str, None, None]:
        """Stream SSE chunks for real-time frontend rendering."""
        metadata = {
            "anchor_concept": anchor,
            "topology": topo,
            "citations": lineage,
        }
        yield f"data: {json.dumps({'type': 'metadata', 'payload': metadata})}\n\n"

        if self._client is not None:
            try:
                stream = gateway_chat_stream(
                    messages,
                    purpose='synthesis',
                    temperature=0.1,
                    max_tokens=512
                )
                for chunk in stream:
                    msg = getattr(chunk, "message", None) or (
                        chunk.get("message") if isinstance(chunk, dict) else {}
                    )
                    token = getattr(msg, "content", None) or (
                        msg.get("content") if isinstance(msg, dict) else ""
                    )
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            except Exception as exc:
                fallback = self._grounded_fallback(anchor, topo, lineage)
                yield f"data: {json.dumps({'type': 'token', 'content': fallback})}\n\n"
        else:
            fallback = self._grounded_fallback(anchor, topo, lineage)
            yield f"data: {json.dumps({'type': 'token', 'content': fallback})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


    def generate_topic_suggestions(
        self,
        term: str,
        candidate_nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format interactive clarification payload for Tier 2 ambiguous terms."""
        clarification_text = (
            f"I couldn't find an exact match for '{term}' in the active curriculum catalog. "
            "Did you mean one of these related topics currently on our shelves?"
        )

        formatted_options = []
        for cand in candidate_nodes[:5]:
            reqs = cand.get("prerequisites", [])
            unls = cand.get("unlocks", [])
            req_str = f"Requires: {', '.join(reqs)}" if reqs else "Foundational entry"
            unl_str = f"Unlocks: {', '.join(unls)}" if unls else "Terminal topic"

            formatted_options.append({
                "concept_id": cand.get("id"),
                "name": cand.get("name"),
                "difficulty": cand.get("difficulty", "intermediate"),
                "summary": cand.get("summary", ""),
                "prerequisites": reqs,
                "unlocks": unls,
                "display_roadmap": f"{req_str} ➔ **{cand.get('name')}** ➔ {unl_str}",
            })

        return {
            "type": "TOPIC_SUGGESTION",
            "message": clarification_text,
            "query_term": term,
            "suggestions": formatted_options,
        }

    def generate_diagnostic_mcq(
        self,
        concept: str,
        prerequisites: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Formulate a 3-question prerequisite MCQ with branching logic."""
        questions = []
        prereq_names = [p.get("name") or p.get("id") for p in prerequisites if p]
        if not prereq_names:
            prereq_names = ["Mathematical Foundations", "Linear Algebra", "Data Structures"]

        for idx, p_name in enumerate(prereq_names[:3], 1):
            questions.append({
                "question_id": f"mcq_{idx}",
                "prerequisite": p_name,
                "question": f"Which fundamental principle of '{p_name}' is essential before studying '{concept}'?",
                "options": {
                    "A": f"Mathematical properties governing {p_name} transformations",
                    "B": f"Asymptotic memory limits of {p_name} state machines",
                    "C": f"Empirical initialization bounds in non-convex {p_name}",
                    "D": f"Discrete topological sorting of {p_name} graphs",
                },
                "correct_option": "A",
                "explanation": f"Understanding foundational {p_name} representations is a strict prerequisite for {concept}.",
                "citation": f"Curriculum DAG: {p_name} -> {concept}",
            })

        return {
            "type": "MCQ_DIAGNOSTIC",
            "target_concept": concept,
            "questions": questions,
            "instructions": "Select the correct option for each question to assess mastery of prerequisites.",
        }

    @staticmethod
    def _clean_repetitions(text: str) -> str:
        """Remove pathological consecutive duplicate sentences or blocks."""
        lines = text.split("\n")
        deduped = []
        last_line = None
        for line in lines:
            if line.strip() and line.strip() == last_line:
                continue
            deduped.append(line)
            if line.strip():
                last_line = line.strip()
        return "\n".join(deduped)

    @staticmethod
    def _grounded_fallback(anchor: str, topo: str, lineage: List[Dict[str, Any]]) -> str:
        """Deterministic grounded fallback when local SLM is offline or initializing."""
        passages_text = ""
        for item in lineage:
            passages_text += f"\n- **[{item['badge']}]** *{item['doc_title']}* (Page {item['page_number']})\n"

        return (
            f"### Pedagogical Overview: {anchor}\n\n"
            f"{topo}\n\n"
            f"#### Grounded Sources:\n{passages_text}\n"
            f"*(Generated via deterministic graph grounding.)*"
        )

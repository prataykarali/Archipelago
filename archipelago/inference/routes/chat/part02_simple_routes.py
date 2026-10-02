"""Chat route handlers: scope refusals, identity, roadmap, onboarding, small talk."""

from __future__ import annotations

import json

from flask import Response

from archipelago.inference.routes.chat.part00_shared import with_holdings
from archipelago.inference.scope_gate import (
    IMPLEMENTATION_REFUSAL_MESSAGE,
    NOT_IN_CORPUS_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
)
from archipelago.inference.synthesis import (
    general_chat_reply,
    identity_reply,
    onboarding_reply,
)


def handle_out_of_scope(query, history, routing, wants_synthesis):
    """Defusal refusals with a soft 'maybe you meant' bridge."""
    reason = routing.get("reason", "out_of_scope_topic") or ""
    rl = reason.lower()
    intent_meta = routing.get("slots") or {}
    if "implementation" in rl:
        out_msg = IMPLEMENTATION_REFUSAL_MESSAGE
        detail = (
            f"Intent gate blocked implementation "
            f"(intent={intent_meta.get('intent')}, "
            f"method={intent_meta.get('intent_method')})."
        )
    elif "not_in_corpus" in rl or "entity" in rl:
        out_msg = NOT_IN_CORPUS_MESSAGE
        detail = (
            f"Intent gate: entity/trivia not grounded in corpus "
            f"(intent={intent_meta.get('intent')})."
        )
    elif "meta" in rl:
        # Same sterile boundary as OOS — do not leak constraints
        out_msg = OUT_OF_SCOPE_MESSAGE
        detail = "Intent gate blocked meta / system-prompt extraction."
    else:
        out_msg = OUT_OF_SCOPE_MESSAGE
        detail = f"Out of AIML library scope (intent={intent_meta.get('intent')}, reason={reason})."

    closest = intent_meta.get("closest_concepts") or []
    # Soft "maybe you meant" bridge on every reject flavor that has
    # plausible graph neighbors — not just corpus misses.
    closest = [c for c in closest if c][:3]
    if closest:
        bridge = ", ".join(f"**{c}**" for c in closest)
        out_msg = (
            f"{out_msg}\n\nIf you were after something nearby, the closest "
            f"concepts on our shelves are: {bridge}."
        )

    def generate_out_of_scope():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 0.0, "reason": reason},
            "logs": [
                {
                    "step": "Pass 1: Intent Gate & Scope",
                    "status": "Out of Scope",
                    "details": detail,
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, out_msg)

    return Response(generate_out_of_scope(), mimetype="text/plain")


def handle_identity(query, history, routing, wants_synthesis):
    """Assistant identity / capabilities question."""

    def generate_identity():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "identity"},
            "logs": [
                {
                    "step": "Pass 1: Intent",
                    "status": "Identity",
                    "details": "Assistant identity / capabilities question.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, identity_reply(query, history))

    return Response(generate_identity(), mimetype="text/plain")


def handle_roadmap_quiz(query, history, routing, wants_synthesis):
    """Generate 5 diagnostic MCQs for the target concept."""

    def generate_quiz_stream():
        from archipelago.inference.curriculum import generate_diagnostic_quiz

        target_id = routing.get("slots", {}).get("target_concept") or "low_rank_adaptation"
        quiz = generate_diagnostic_quiz(target_id, num_questions=5)
        target_info = quiz.get("target_concept", {})
        target_name = target_info.get("name") or target_id
        prereq_names = [q["concept_name"] for q in quiz.get("questions", [])]

        payload = {
            "anchor_concept": target_id,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": routing.get("related", [])[:5],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "diagnostic_assessment"},
            "logs": [
                {
                    "step": "Pass 1: Intent",
                    "status": "Diagnostic Assessment",
                    "details": f"Generating 5 diagnostic MCQs for target concept: {target_name}.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"

        # If synthesis is requested, let the inference model introduce the diagnostic quiz contextually
        if wants_synthesis:
            try:
                from archipelago.inference.llm_gateway import gateway_chat_stream

                prompt = (
                    f"You are Archipelago Diagnostic Tutor. A student wants to learn '{target_name}'. "
                    f"To build a personalized 1-6 hop learning roadmap, we need to test their prior knowledge on its prerequisites: {', '.join(prereq_names[:4])}. "
                    f"Write a friendly, encouraging 2-sentence introduction explaining why assessing these foundations is critical before jumping into '{target_name}'. Do not reveal quiz answers."
                )
                for chunk in gateway_chat_stream(
                    messages=[{"role": "user", "content": prompt}],
                    purpose="synthesis",
                    temperature=0.2,
                    max_tokens=120,
                    timeout=15,
                ):
                    if chunk:
                        yield chunk
                yield "\n\n"
            except Exception:
                yield f"Welcome to the diagnostic assessment for **{target_name}**! Assessing your foundational grasp on prerequisite concepts allows Archipelago to build an optimal, personalized 1–6 hop learning roadmap.\n\n"
        else:
            yield f"Welcome to the diagnostic assessment for **{target_name}**! Assessing your foundational grasp on prerequisite concepts allows Archipelago to build an optimal, personalized 1–6 hop learning roadmap.\n\n"

        lines = [
            f"### 🎯 Knowledge Assessment: Prerequisites for {target_name}\n",
            f"Let's assess your prior knowledge to build a personalized 1–6 hop learning roadmap to **{target_name}**.",
            "Answer these 5 quick diagnostic questions (reply with e.g. *1-A, 2-B, 3-C, 4-D, 5-A* or just your answers):\n",
        ]
        for q in quiz.get("questions", []):
            lines.append(
                f"**Question {q['q_index']}: {q['concept_name']}** `[{q['difficulty'].upper()}]`"
            )
            lines.append(f"{q['question']}")
            for opt_key, opt_text in sorted(q.get("options", {}).items()):
                lines.append(f"- **({opt_key})** {opt_text}")
            lines.append("")

        lines.append("---")
        lines.append(
            f"💡 *Once you answer, Archipelago will identify your baseline concept and plot your step-by-step roadmap to {target_name}!*"
        )
        yield "\n".join(lines)

    return Response(generate_quiz_stream(), mimetype="text/plain")


def handle_roadmap_quiz_eval(query, history, routing, wants_synthesis):
    """Evaluate diagnostic quiz answers and stream the personalized roadmap."""

    def generate_quiz_eval_stream():
        from archipelago.inference.curriculum import evaluate_quiz_and_route_roadmap

        slots = routing.get("slots", {})
        target_id = slots.get("target_concept") or "low_rank_adaptation"
        student_answers = slots.get("answers") or {}

        eval_result = evaluate_quiz_and_route_roadmap(student_answers, target_id, max_hops=6)
        score_str = eval_result.get("score", "0/5")
        baseline = eval_result.get("baseline_concept", {})
        baseline_name = baseline.get("name") if isinstance(baseline, dict) else str(baseline)
        roadmap = eval_result.get("roadmap", {})
        target_name = eval_result.get("target_concept", {}).get("name") or target_id
        hops = roadmap.get("hops", 0)

        payload = {
            "anchor_concept": target_id,
            "prerequisites": roadmap.get("steps", []),
            "unlocks": [],
            "citations": [],
            "related_concepts": routing.get("related", [])[:5],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "diagnostic_evaluation"},
            "logs": [
                {
                    "step": "Pass 1: Intent",
                    "status": "Diagnostic Evaluation",
                    "details": f"Student scored {score_str}. Baseline: {baseline_name}. Roadmap: {hops} hops to {target_name}.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"

        # Run inference model to synthesize personalized pedagogical feedback
        if wants_synthesis:
            try:
                from archipelago.inference.llm_gateway import gateway_chat_stream

                prompt = (
                    f"You are Archipelago Diagnostic Tutor. A student completed a diagnostic quiz for target concept '{target_name}'.\n"
                    f"Score: {score_str}.\n"
                    f"Identified Starting Baseline: {baseline_name}.\n"
                    f"Mastered Prerequisites: {', '.join(eval_result.get('mastered_concepts', [])) or 'None'}.\n"
                    f"Prerequisites to Review: {', '.join(eval_result.get('gap_concepts', [])) or 'None'}.\n"
                    f"In 2-3 encouraging sentences, evaluate their performance, highlight what they mastered, and introduce their personalized {hops}-hop learning path."
                )
                for chunk in gateway_chat_stream(
                    messages=[{"role": "user", "content": prompt}],
                    purpose="synthesis",
                    temperature=0.2,
                    max_tokens=150,
                    timeout=15,
                ):
                    if chunk:
                        yield chunk
                yield "\n\n"
            except Exception:
                yield f"### 📊 Diagnostic Evaluation: Score {score_str}\n\nBased on your responses, your foundational baseline is **{baseline_name}**. Here is your customized learning roadmap to **{target_name}**:\n\n"
        else:
            yield f"### 📊 Diagnostic Evaluation: Score {score_str}\n\nBased on your responses, your foundational baseline is **{baseline_name}**. Here is your customized learning roadmap to **{target_name}**:\n\n"

        # Stream the computed roadmap and question breakdown
        lines = [f"### 🗺️ Personalized Roadmap: {baseline_name} → {target_name} ({hops} hops)\n"]
        lines.append(roadmap.get("markdown", ""))
        lines.append("\n#### 📝 Question Review")
        for d in eval_result.get("details", {}).get("mastered", []):
            lines.append(
                f"- ✅ **Q{d['q_index']}: {d['concept_name']}** — Correct (`{d['user_answer']}`). {d['explanation']}"
            )
        for d in eval_result.get("details", {}).get("gaps", []):
            lines.append(
                f"- ❌ **Q{d['q_index']}: {d['concept_name']}** — Selected `{d['user_answer']}` (Correct: `{d['correct_answer']}`). {d['explanation']}"
            )
        yield "\n".join(lines)

    return Response(generate_quiz_eval_stream(), mimetype="text/plain")


def handle_roadmap_between(query, history, routing, wants_synthesis):
    """Direct start-to-target personalized roadmap."""

    def generate_roadmap_stream():
        from archipelago.inference.curriculum import find_roadmap_between

        slots = routing.get("slots", {})
        start_id = slots.get("start_id", "")
        target_id = slots.get("target_id", "")
        roadmap = find_roadmap_between(start_id, target_id, max_hops=6)

        payload = {
            "anchor_concept": target_id,
            "prerequisites": roadmap.get("steps", []),
            "unlocks": [],
            "citations": [],
            "related_concepts": routing.get("related", [])[:5],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "personalized_roadmap"},
            "logs": [
                {
                    "step": "Pass 1: Intent",
                    "status": "Personalized Roadmap",
                    "details": f"Calculated {roadmap.get('hops', 0)}-hop curriculum from {roadmap.get('start_name')} to {roadmap.get('target_name')}.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield roadmap.get("markdown", "")

    return Response(generate_roadmap_stream(), mimetype="text/plain")


def handle_onboarding(query, history, routing, wants_synthesis):
    """Broad AIML syllabus / start-learning entry path."""

    def generate_onboarding():
        related = routing.get("related") or []
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": related[:5],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "onboarding_syllabus"},
            "logs": [
                {
                    "step": "Pass 1: Intent",
                    "status": "Onboarding",
                    "details": "Broad AIML syllabus / start-learning entry path.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, onboarding_reply(query, related))

    return Response(generate_onboarding(), mimetype="text/plain")


def handle_small_talk(query, history, routing, wants_synthesis):
    """Conversational pleasantry detected."""

    def generate_small_talk():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {
                "route": routing["route"],
                "score": 1.0,
                "reason": "conversational_greeting",
            },
            "logs": [
                {
                    "step": "Pass 1: Intent",
                    "status": "Small talk",
                    "details": "Conversational pleasantry detected.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, general_chat_reply(query, history))

    return Response(generate_small_talk(), mimetype="text/plain")

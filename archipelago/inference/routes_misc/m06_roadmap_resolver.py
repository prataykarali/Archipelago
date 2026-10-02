"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from pathlib import Path
from flask import jsonify, send_from_directory, request, redirect
from archipelago.inference import state as st
from .m01_cors_pdf import REMOTE_PDF_SOURCES  # noqa: F401


@st.app.route("/api/roadmap/quiz", methods=["GET", "POST"])
def api_roadmap_quiz():
    """Generate 5-6 diagnostic MCQs to test baseline knowledge for a target concept."""
    from archipelago.inference.curriculum import generate_diagnostic_quiz
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        target = data.get("target") or data.get("target_concept_id") or "low_rank_adaptation"
        num_q = int(data.get("num_questions") or 5)
    else:
        target = request.args.get("target") or request.args.get("target_concept_id") or "low_rank_adaptation"
        num_q = int(request.args.get("num_questions") or 5)

    quiz = generate_diagnostic_quiz(target, num_questions=num_q)
    return jsonify(quiz)


@st.app.route("/api/roadmap/plan", methods=["POST"])
def api_roadmap_plan():
    """Evaluate diagnostic quiz responses and compute personalized 1-6 hop roadmap."""
    from archipelago.inference.curriculum import evaluate_quiz_and_route_roadmap
    data = request.get_json(silent=True) or {}
    target = data.get("target") or data.get("target_concept_id") or "low_rank_adaptation"
    responses = data.get("responses") or data.get("answers") or {}
    quiz_data = data.get("quiz_data")
    max_hops = int(data.get("max_hops") or 6)

    result = evaluate_quiz_and_route_roadmap(
        quiz_responses=responses,
        target_concept_id=target,
        quiz_data=quiz_data,
        max_hops=max_hops,
    )
    return jsonify(result)


@st.app.route("/api/roadmap/between", methods=["GET", "POST"])
def api_roadmap_between():
    """Directly compute a 1-6 hop roadmap between start_concept_id and target_concept_id."""
    from archipelago.inference.curriculum import find_roadmap_between
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        start = data.get("start") or data.get("start_concept_id") or ""
        target = data.get("target") or data.get("target_concept_id") or ""
        max_hops = int(data.get("max_hops") or 6)
    else:
        start = request.args.get("start") or request.args.get("start_concept_id") or ""
        target = request.args.get("target") or request.args.get("target_concept_id") or ""
        max_hops = int(request.args.get("max_hops") or 6)

    roadmap = find_roadmap_between(start, target, max_hops=max_hops)
    return jsonify(roadmap)


def resolve_pdf_file(filename: str) -> Path | None:
    """Resolve a PDF filename to a local path or None."""
    p = Path(filename)
    if p.is_file():
        return p
    pdf_dir = Path(getattr(st, "PDF_DIR", "pdfs"))
    candidate = pdf_dir / filename
    if candidate.is_file():
        return candidate
    candidate = pdf_dir / "papers" / filename
    if candidate.is_file():
        return candidate
    candidate = pdf_dir / "textbooks" / filename
    if candidate.is_file():
        return candidate
    for match in pdf_dir.rglob(p.name):
        if match.is_file():
            return match
    return None


def pdf_available(doc_id: str) -> bool:
    """Return True if the PDF exists locally or has a remote fallback."""
    if not doc_id:
        return False
    if resolve_pdf_file(doc_id) is not None:
        return True
    fname = Path(doc_id).name
    return fname in REMOTE_PDF_SOURCES

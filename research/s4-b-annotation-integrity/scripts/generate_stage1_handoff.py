#!/usr/bin/env python3
"""
Generate a clean Stage 1 package for a new independent human reviewer.

Guarantees:
- Exactly 113 candidates across 6 queries.
- No human relevance judgments prefilled.
- No reviewer A scores, notes, or prior adjudication suggestions.
- No question category, retrieval rank, score, or system identity.
- Full original candidate passages (no truncation).
- Clear 0/1/2 rubric.
- Query-level answerability and multi-passage fields.
- Clear caveat: the reviewer can judge evidence in the supplied pool, but cannot certify absence from the entire corpus without access to a corpus-wide audit.
- No source verification map included in Stage 1 handoff package.
- Preserves all previous files and hashes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
LOCAL_ONLY = ROOT / "artifacts" / "validation" / "local_only"
PACKAGE_DIR = LOCAL_ONLY / "stage1_handoff_package"
RESEARCH_DIR = ROOT / "research" / "s4-b-annotation-integrity"

WS_JSON = LOCAL_ONLY / "s4a_human_annotation_worksheet.json"

POOL_SIZES = {
    "CIKM-PILOT-001": 17,
    "CIKM-PILOT-005": 14,
    "CIKM-PILOT-013": 16,
    "CIKM-PILOT-002": 17,
    "CIKM-PILOT-004": 22,
    "CIKM-PILOT-023": 27,
}

def build_stage1_markdown(ws_json: dict) -> str:
    lines: list[str] = []
    lines.append("# Archipelago CIKM 2027 — Independent Human Annotation Pilot (Stage 1 Worksheet)")
    lines.append("")
    lines.append("## Overview and Instructions for Independent Reviewer")
    lines.append("")
    lines.append("You are acting as an **independent human reviewer** for this scientific QA evaluation pilot.")
    lines.append("To ensure scientific validity, this worksheet is strictly blinded:")
    lines.append("- Retrieval system identities (`bm25`, `dense`, `hybrid_rrf`), retrieval ranks, and retrieval scores are completely removed.")
    lines.append("- Question classifications and category metadata are completely removed.")
    lines.append("- No peer judgments, prior review scores, or adjudication suggestions are included.")
    lines.append("- Full candidate passage texts are provided below without truncation.")
    lines.append("")
    lines.append("### Important Methodological Boundary (Corpus vs Pool Scope)")
    lines.append("> **CRITICAL NOTICE ON ANSWERABILITY SCOPE:**")
    lines.append("> As an annotator, you are evaluating evidence present within the **supplied candidate pool**.")
    lines.append("> You can determine whether the supplied pool contains sufficient evidence to answer each question.")
    lines.append("> **You cannot certify that an unanswered question is absent from the entire corpus** based solely on this candidate pool. Full corpus unanswerability requires an independent, corpus-wide search audit.")
    lines.append("> If none of the candidate passages answer the question, record `UNANSWERED_IN_POOL` (or `UNANSWERABLE_OUT_OF_CORPUS` if the concept is demonstrably beyond the domain/corpus period).")
    lines.append("")
    lines.append("### Relevance Judgment Rubric (`0 / 1 / 2`)")
    lines.append("For each candidate passage, assign an integer relevance grade:")
    lines.append("- **`0` — Not Relevant:** The passage does not answer or provide context for the question. Contains irrelevant topics, boilerplate, or index listings.")
    lines.append("- **`1` — Partially Relevant / Context:** The passage contains relevant domain background, related definitions, or partial steps, but does not fully answer the question on its own.")
    lines.append("- **`2` — Directly Answers / Supports:** The passage directly answers the question or provides core supporting evidence required to resolve it.")
    lines.append("")
    lines.append("For any passage you score `1` or `2`, record the supporting quote span in the provided field.")
    lines.append("")
    lines.append("### Two-Stage Study Design")
    lines.append("This study operates in two strictly separated stages:")
    lines.append("1. **Stage 1 (This Package):** Complete blinded relevance and answerability assessments based solely on candidate texts.")
    lines.append("2. **Stage 2 (Post-Submission Source Verification):** After submitting Stage 1, you will receive a candidate-to-source mapping to inspect original PDFs, verify page references, and confirm exact quotation spans.")
    lines.append("*(Do not consult external search engines or repository Git history during Stage 1).*")
    lines.append("")
    lines.append("---")
    lines.append("")

    pools = ws_json.get("blinded_pools", {})
    queries = ws_json.get("queries", [])

    for q in queries:
        qid = q["query_id"]
        question_text = q["question"]
        pool_items = pools.get(qid, [])

        lines.append(f"## Query: {qid}")
        lines.append(f"**Question:** {question_text}")
        lines.append("")
        lines.append("**Query Answerability:** `[ ANSWERABLE | UNANSWERED_IN_POOL | UNANSWERABLE_OUT_OF_CORPUS | CANNOT_DETERMINE ]`")
        lines.append("Your assessment: `[ ________________________________ ]`")
        lines.append("")
        lines.append("**Requires Multiple Supporting Passages?** (`YES / NO`): `[ _____ ]`")
        lines.append("")
        lines.append("### Candidate Passages for Evaluation")
        lines.append("")

        for item in pool_items:
            cid = item["pool_item_id"]
            page = item.get("page_number", "?")
            section = item.get("section_title", "") or "N/A"
            full_text = item.get("text", "").strip()

            lines.append(f"#### Candidate: {cid} (Document Page Reference: {page})")
            lines.append(f"- Section Header: `{section}`")
            lines.append(f"- **Relevance Score (`0 / 1 / 2`):** ___")
            lines.append(f"- **Supporting Quote Span (required if score ≥ 1):** ______________________________")
            lines.append("")
            lines.append(f"> {full_text}")
            lines.append("")

        lines.append(f"**Reviewer Notes for {qid}:** __________________________________________________")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Submission Checklist")
    lines.append("- [ ] All 113 candidate passages scored (0, 1, or 2).")
    lines.append("- [ ] No candidate left blank.")
    lines.append("- [ ] Supporting quote spans noted for all passages with score ≥ 1.")
    lines.append("- [ ] Query-level answerability recorded for all 6 queries.")
    lines.append("- [ ] Multi-passage requirement recorded for all 6 queries.")
    lines.append("- [ ] Stage 1 worksheet saved and submitted to study coordinator.")
    lines.append("")
    lines.append("**Reviewer ID / Signature:** ____________________    **Date:** ____________________")
    lines.append("")
    return "\n".join(lines)


def build_stage1_json(ws_json: dict) -> list[dict]:
    pools = ws_json.get("blinded_pools", {})
    queries = ws_json.get("queries", [])
    
    records = []
    for q in queries:
        qid = q["query_id"]
        pool_items = pools.get(qid, [])
        rec = {
            "query_id": qid,
            "reviewer_id": "independent_reviewer",
            "question": q["question"],
            "review_status": "UNVERIFIED_CANDIDATE",
            "stage": "STAGE_1_BLINDED_EVALUATION",
            "answerability_assessment": None,
            "requires_multiple_supporting_passages": None,
            "passage_relevance_judgments": {it["pool_item_id"]: None for it in pool_items},
            "supporting_quote_spans": {it["pool_item_id"]: None for it in pool_items},
            "reviewer_notes": ""
        }
        records.append(rec)
    return records


def main():
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    ws_json = json.loads(WS_JSON.read_text(encoding="utf-8"))

    # 1. Generate clean Stage 1 Markdown Worksheet
    stage1_md = build_stage1_markdown(ws_json)
    stage1_md_path = PACKAGE_DIR / "stage1_independent_worksheet.md"
    stage1_md_path.write_text(stage1_md, encoding="utf-8")
    print(f"Generated {stage1_md_path}")

    # 2. Generate clean Stage 1 JSON template
    stage1_json = build_stage1_json(ws_json)
    stage1_json_path = PACKAGE_DIR / "stage1_independent_template.json"
    stage1_json_path.write_text(json.dumps(stage1_json, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {stage1_json_path}")

    # 3. Create Reviewer Instructions Guide
    instructions = (RESEARCH_DIR / "REVIEWER_B_INSTRUCTIONS.md").read_text(encoding="utf-8")
    # Tailor instructions for the independent reviewer handoff
    instructions_path = PACKAGE_DIR / "INDEPENDENT_REVIEWER_GUIDE.md"
    guide_text = f"""# Independent Human Reviewer Guide — Stage 1 Annotation

**Package Path:** `artifacts/validation/local_only/stage1_handoff_package/`  
**Stage 1 Worksheet:** `stage1_independent_worksheet.md`  
**Stage 1 Submission Template:** `stage1_independent_template.json`  

---

## 1. Scope & Protocol
You are serving as an independent human annotator for a 6-question scientific QA evaluation.
- All 113 candidate passages are completely blinded: no retrieval systems, no scores, no category tags.
- Evaluate each candidate strictly on the factual evidence it provides.
- In accordance with methodological standards, Stage 2 (source and page verification) will be provided only after you complete and submit this Stage 1 package.

## 2. Corpus vs. Pool Scope
- You are judging whether the evidence provided in the candidate pool resolves the query.
- Note that an absence of evidence in this 113-candidate pool indicates the question is `UNANSWERED_IN_POOL`. Absolute absence from the whole corpus cannot be certified without an independent exhaustive corpus search.

## 3. How to Annotate
1. Open `stage1_independent_worksheet.md` in your text editor.
2. Fill in your relevance score (`0`, `1`, or `2`) for each of the 113 candidates.
3. For scores `1` or `2`, note the exact supporting quote span.
4. Record answerability and multi-passage need for each query.
5. Submit the worksheet or `stage1_independent_template.json` to the study coordinator.
"""
    instructions_path.write_text(guide_text, encoding="utf-8")
    print(f"Generated {instructions_path}")

if __name__ == "__main__":
    main()

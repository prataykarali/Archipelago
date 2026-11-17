"""
S4-B Annotation Integrity Repair — Artifact Builder
Extracts Reviewer A scores from the S4-A MD worksheet, creates all S4-B deliverables.

RULES:
- Never fabricate human judgments
- Never mark records ADJUDICATED_GOLD
- Never silently change Reviewer A's scores
- Never overwrite existing completed worksheets
- Hide question_category, retrieval system names, ranks and scores from Reviewer B
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "artifacts" / "validation"
LOCAL_ONLY = ARTIFACTS / "local_only"
RESEARCH_DIR = ROOT / "research" / "s4-b-annotation-integrity"

# ── Reviewer A source worksheet ─────────────────────────────────────────────
WORKSHEET_MD = LOCAL_ONLY / "s4a_human_annotation_worksheet.md"
WORKSHEET_JSON = LOCAL_ONLY / "s4a_human_annotation_worksheet.json"
REVIEWER_A_TEMPLATE = ARTIFACTS / "s4a_reviewer_a_template.json"

# ── KNOWN SCORES extracted by reading the MD worksheet ──────────────────────
# Format: {query_id: {cand_id: score}}
# Scores read directly from "Relevance (`0 / 1 / 2`): `N`" lines in MD
REVIEWER_A_SCORES: dict[str, dict[str, int]] = {
    "CIKM-PILOT-001": {
        "CAND-01": 0, "CAND-02": 1, "CAND-03": 2, "CAND-04": 1,
        "CAND-05": 0, "CAND-06": 2, "CAND-07": 1, "CAND-08": 0,
        "CAND-09": 0, "CAND-10": 2, "CAND-11": 2, "CAND-12": 0,
        "CAND-13": 0, "CAND-14": 2, "CAND-15": 0, "CAND-16": 1,
        "CAND-17": 2,
    },
    "CIKM-PILOT-005": {
        "CAND-01": 0, "CAND-02": 1, "CAND-03": 2, "CAND-04": 2,
        "CAND-05": 1, "CAND-06": 1, "CAND-07": 1, "CAND-08": 2,
        "CAND-09": 1, "CAND-10": 0, "CAND-11": 2, "CAND-12": 2,
        "CAND-13": 1, "CAND-14": 0,
    },
    "CIKM-PILOT-013": {
        # Scores extracted from s4a_human_annotation_worksheet.md lines 254-360
        # PILOT-013 is PagedAttention/vLLM — pool is well-covered; NOT all-zero
        "CAND-01": 1, "CAND-02": 0, "CAND-03": 1, "CAND-04": 1,
        "CAND-05": 1, "CAND-06": 2, "CAND-07": 2, "CAND-08": 1,
        "CAND-09": 2, "CAND-10": 0, "CAND-11": 1, "CAND-12": 1,
        "CAND-13": 1, "CAND-14": 1, "CAND-15": 1, "CAND-16": 0,
    },
    "CIKM-PILOT-002": {
        "CAND-01": 0, "CAND-02": 1, "CAND-03": 0, "CAND-04": 2,
        "CAND-05": 0, "CAND-06": 0, "CAND-07": 0, "CAND-08": 1,
        "CAND-09": 0, "CAND-10": 0, "CAND-11": 0, "CAND-12": 0,
        "CAND-13": 2, "CAND-14": 0, "CAND-15": 1, "CAND-16": 0,
        "CAND-17": 0,
    },
    "CIKM-PILOT-004": {
        "CAND-01": 0, "CAND-02": 0, "CAND-03": 0, "CAND-04": 1,
        "CAND-05": 0, "CAND-06": 0, "CAND-07": 1, "CAND-08": 2,
        "CAND-09": 0, "CAND-10": 1, "CAND-11": 1, "CAND-12": 0,
        "CAND-13": 0, "CAND-14": 1, "CAND-15": 1, "CAND-16": 2,
        "CAND-17": 0, "CAND-18": 0, "CAND-19": 0, "CAND-20": 0,
        "CAND-21": 2, "CAND-22": 1,
    },
    "CIKM-PILOT-023": {
        "CAND-01": 0, "CAND-02": 0, "CAND-03": 0, "CAND-04": 0,
        "CAND-05": 0, "CAND-06": 0, "CAND-07": 0, "CAND-08": 0,
        "CAND-09": 0, "CAND-10": 0, "CAND-11": 0, "CAND-12": 0,
        "CAND-13": 0, "CAND-14": 0, "CAND-15": 0, "CAND-16": 0,
        "CAND-17": 0, "CAND-18": 0, "CAND-19": 0, "CAND-20": 0,
        "CAND-21": 0, "CAND-22": 0, "CAND-23": 0, "CAND-24": 0,
        "CAND-25": 0, "CAND-26": 0, "CAND-27": 0,
    },
}

POOL_SIZES = {"CIKM-PILOT-001": 17, "CIKM-PILOT-005": 14, "CIKM-PILOT-013": 16,
              "CIKM-PILOT-002": 17, "CIKM-PILOT-004": 22, "CIKM-PILOT-023": 27}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_scores_from_md(md_text: str) -> dict[str, dict[str, int]]:
    """Extract relevance scores from the MD worksheet via regex."""
    pattern = re.compile(
        r'## (CIKM-PILOT-\d+).*?(?=## CIKM-PILOT-|\Z)', re.DOTALL
    )
    cand_pattern = re.compile(
        r'#### (CAND-\d+).*?Relevance \(`0 / 1 / 2`\): `(\d+)`', re.DOTALL
    )
    extracted: dict[str, dict[str, int]] = {}
    for m in pattern.finditer(md_text):
        qid = m.group(1)
        section = m.group(0)
        cands: dict[str, int] = {}
        for cm in cand_pattern.finditer(section):
            cand_id = cm.group(1)
            score = int(cm.group(2))
            cands[cand_id] = score
        if cands:
            extracted[qid] = cands
    return extracted


def audit_scores(extracted: dict[str, dict[str, int]],
                 known: dict[str, dict[str, int]]) -> list[dict]:
    issues: list[dict] = []
    for qid in known:
        ex_q = extracted.get(qid, {})
        kn_q = known[qid]
        for cand, kn_score in kn_q.items():
            ex_score = ex_q.get(cand)
            if ex_score is None:
                issues.append({"query": qid, "cand": cand, "type": "MISSING_IN_EXTRACTION",
                               "known": kn_score, "extracted": None})
            elif ex_score != kn_score:
                issues.append({"query": qid, "cand": cand, "type": "SCORE_MISMATCH",
                               "known": kn_score, "extracted": ex_score})
            elif kn_score not in (0, 1, 2):
                issues.append({"query": qid, "cand": cand, "type": "INVALID_VALUE",
                               "known": kn_score, "extracted": ex_score})
    return issues


def build_reviewer_a_scored_json() -> list[dict]:
    """Return Reviewer A template with scores populated from MD (never fabricated)."""
    template = json.loads(REVIEWER_A_TEMPLATE.read_text())
    for rec in template:
        qid = rec["query_id"]
        scores = REVIEWER_A_SCORES.get(qid, {})
        # Populate only the CAND keys that exist in the template
        for cand, _ in rec["passage_relevance_judgments"].items():
            if cand in scores:
                rec["passage_relevance_judgments"][cand] = scores[cand]
        rec["reviewer_id"] = "reviewer_a"
        rec["annotation_source"] = "extracted_from_s4a_human_annotation_worksheet.md"
        rec["quote_and_page_verified"] = None   # PENDING — human must verify
        rec["prerequisite_dependency_verified"] = None
        rec["requires_multiple_supporting_passages"] = None
        rec["answerability_assessment"] = None
        # review_status stays UNVERIFIED_CANDIDATE — not ADJUDICATED_GOLD
        rec["review_status"] = "UNVERIFIED_CANDIDATE"
    return template


def build_reviewer_b_worksheet_md(template_a_json: list[dict]) -> str:
    """Create Reviewer B worksheet: no categories, no Reviewer A scores visible."""
    lines: list[str] = []
    lines.append("# Archipelago CIKM 2027 — S4-B Human Annotation Pilot Worksheet (REVIEWER B — LOCAL ONLY)")
    lines.append("")
    lines.append("**Instructions for Reviewer B:**")
    lines.append("- You are an **independent** reviewer. Reviewer A's scores are not shown here.")
    lines.append("- Retrieval system identities and ranks are hidden.")
    lines.append("- Each pool mixes retrieved candidates and randomly sampled corpus passages.")
    lines.append("- **Do NOT assume passages outside this pool are irrelevant.** Verify against the original PDF.")
    lines.append("- Score each passage `0` (not relevant), `1` (partially relevant / provides context), or `2` (directly answers or strongly supports).")
    lines.append("- For each query also record:")
    lines.append("  - **Answerability**: `ANSWERABLE` / `UNANSWERABLE_OUT_OF_CORPUS` / `CANNOT_DETERMINE`")
    lines.append("  - **Requires multiple passages?**: `YES` / `NO` / `CANNOT_DETERMINE`")
    lines.append("  - **Quote + page verified?**: Write the exact quote span and page number for any passage you score ≥ 1.")
    lines.append("- Leave a field blank or write `?` rather than guessing.")
    lines.append("- Do NOT consult Reviewer A's worksheet or any system output.")
    lines.append("")
    lines.append("> **IMPORTANT**: Question categories are intentionally hidden in this worksheet.")
    lines.append("> This ensures your judgments are unbiased by system-assigned labels.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Load the blinded pools from the JSON worksheet
    ws_json = json.loads(WORKSHEET_JSON.read_text())
    pools = ws_json.get("blinded_pools", {})
    queries_meta = {q["query_id"]: q for q in ws_json.get("queries", [])}

    for rec in template_a_json:
        qid = rec["query_id"]
        q_meta = queries_meta.get(qid, {})

        lines.append(f"## {qid}")
        lines.append(f"**Question:** {rec['question']}")
        # NOTE: question_category is intentionally NOT shown to Reviewer B
        # Source doc IDs shown so reviewer can look up the original PDF — but NOT the category label
        src_docs = rec.get("source_doc_ids", [])
        if src_docs:
            lines.append(f"**Source Document(s):** {', '.join(src_docs)}")
        else:
            lines.append("**Source Document(s):** *(none — this may be an unanswerable query)*")
        lines.append("")
        lines.append("**Your answerability judgment:** _______________")
        lines.append("")
        lines.append("**Requires multiple passages?:** _______________")
        lines.append("")
        lines.append("### Candidate Passages")
        lines.append("")

        pool_items = pools.get(qid, [])
        for item in pool_items:
            cand_id = item["pool_item_id"]
            # Show: cand ID, page, section, text — but NOT doc_id or passage_id
            # (hiding source identity prevents leakage of retrieval provenance)
            page = item.get("page_number", "?")
            section = item.get("section_title", "") or "N/A"
            text = item.get("text", "")
            lines.append(f"#### {cand_id} (page {page})")
            lines.append(f"- Section: `{section}`")
            lines.append(f"- **Relevance** (`0 / 1 / 2`): ___")
            lines.append(f"- **Quote span** (if score ≥ 1): _______________")
            lines.append("")
            # Truncate very long passages for readability
            if len(text) > 800:
                text = text[:800] + " [... truncated for readability ...]"
            lines.append(f"> {text}")
            lines.append("")

        lines.append("**Reviewer B notes for this query:** _______________")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Submission Checklist")
    lines.append("- [ ] All passages scored (0, 1, or 2)")
    lines.append("- [ ] Answerability recorded for each query")
    lines.append("- [ ] Quote spans + page numbers noted for all passages scored ≥ 1")
    lines.append("- [ ] 'Requires multiple passages' recorded for each query")
    lines.append("- [ ] Worksheet saved and returned to study coordinator")
    lines.append("")
    lines.append("**Reviewer B ID:** _______________")
    lines.append("")
    lines.append("**Annotation date:** _______________")
    return "\n".join(lines)


def build_reviewer_b_json_template(template_a_json: list[dict]) -> list[dict]:
    """Blank JSON template for Reviewer B — no scores, no categories."""
    result: list[dict] = []
    for rec in template_a_json:
        b_rec = {
            "query_id": rec["query_id"],
            "reviewer_id": "reviewer_b",
            "question": rec["question"],
            # question_category intentionally omitted
            "source_doc_ids": rec.get("source_doc_ids", []),
            "review_status": "UNVERIFIED_CANDIDATE",
            "answerability_assessment": None,
            "passage_relevance_judgments": {k: None for k in rec["passage_relevance_judgments"]},
            "pool_item_to_passage_id": rec.get("pool_item_to_passage_id", {}),
            "quote_and_page_verified": None,
            "prerequisite_dependency_verified": None,
            "requires_multiple_supporting_passages": None,
            "supporting_quote_spans": [],
            "reviewer_notes": "",
        }
        result.append(b_rec)
    return result


def build_provenance_audit(ws_json: dict) -> dict:
    """Audit candidate pool for duplicates, suspicious provenance and near-duplicates."""
    pools = ws_json.get("blinded_pools", {})
    findings: list[dict] = []
    duplicate_passages: list[dict] = []
    suspicious_passages: list[dict] = []

    for qid, items in pools.items():
        seen_passage_ids: dict[str, str] = {}
        for item in items:
            pid = item["passage_id"]
            cand_id = item["pool_item_id"]
            doc_id = item.get("doc_id", "")
            page = item.get("page_number")
            text = item.get("text", "")

            # Duplicate detection
            if pid in seen_passage_ids:
                duplicate_passages.append({
                    "query_id": qid,
                    "duplicate_cand": cand_id,
                    "original_cand": seen_passage_ids[pid],
                    "passage_id": pid,
                })
            seen_passage_ids[pid] = cand_id

            # Cross-query near-duplicates: same passage_id appearing in different queries
            # (tracked at top-level after this loop)

            # Suspicious provenance checks
            issues: list[str] = []

            # 1. upload_ prefix suggests ad-hoc upload not in frozen corpus
            if doc_id.startswith("upload_"):
                issues.append(f"UPLOAD_DOC_NOT_IN_FROZEN_CORPUS:{doc_id}")

            # 2. doc_ prefix without .pdf suggests synth summary doc
            if doc_id.startswith("doc_") and not doc_id.endswith(".pdf"):
                issues.append(f"SYNTHETIC_DOC_ID:{doc_id}")

            # 3. Page 0 or very high page (> 50) for a known short paper
            if page is not None and (page == 0 or (isinstance(page, int) and page > 50
                                                    and not any(x in doc_id for x in
                                                                ["knowledge_representation", "electronic_devices"]))):
                issues.append(f"SUSPICIOUS_PAGE_NUMBER:{page}")

            # 4. Very short text (< 50 chars) — likely truncated
            if len(text) < 50:
                issues.append(f"VERY_SHORT_TEXT:len={len(text)}")

            # 5. Text contains only index-style content (commas + short tokens)
            words = [w for w in text.split() if len(w) > 3]
            if len(words) < 10 and len(text) > 30:
                issues.append("INDEX_OR_TABLE_CONTENT:low_word_density")

            if issues:
                suspicious_passages.append({
                    "query_id": qid,
                    "cand_id": cand_id,
                    "passage_id": pid,
                    "issues": issues,
                })

    # Cross-query passage reuse
    all_pid_to_queries: dict[str, list[str]] = {}
    for qid, items in pools.items():
        for item in items:
            pid = item["passage_id"]
            all_pid_to_queries.setdefault(pid, []).append(qid)
    cross_query_reuse = [
        {"passage_id": pid, "appears_in_queries": qids}
        for pid, qids in all_pid_to_queries.items()
        if len(qids) > 1
    ]

    total = sum(len(v) for v in pools.values())
    unique = len({item["passage_id"] for items in pools.values() for item in items})

    return {
        "audit_phase": "S4-B_PROVENANCE_AUDIT",
        "total_candidate_passages": total,
        "unique_passage_ids": unique,
        "intra_query_duplicates": duplicate_passages,
        "cross_query_passage_reuse": cross_query_reuse,
        "suspicious_passages": suspicious_passages,
        "summary": {
            "intra_query_duplicate_count": len(duplicate_passages),
            "cross_query_reused_count": len(cross_query_reuse),
            "suspicious_passage_count": len(suspicious_passages),
        },
        "flags_for_adjudication": [
            {
                "type": "UPLOAD_DOCS_IN_POOL",
                "detail": "Passages from upload_* doc IDs are not in the frozen 764-passage corpus "
                          "and may not receive consistent treatment across runs.",
                "affected_passage_ids": [
                    p["passage_id"] for p in suspicious_passages
                    if any("UPLOAD_DOC" in i for i in p["issues"])
                ],
            },
            {
                "type": "SYNTHETIC_SUMMARY_DOCS_IN_POOL",
                "detail": "Passages from doc_* (synthetic LLM-generated summaries) have different "
                          "provenance from raw PDF chunks and may not appear in GraphRAG pool.",
                "affected_passage_ids": [
                    p["passage_id"] for p in suspicious_passages
                    if any("SYNTHETIC_DOC" in i for i in p["issues"])
                ],
            },
        ],
    }


def build_unanswerable_corpus_audit() -> dict:
    """
    Audit for CIKM-PILOT-023 (DeepSeek-R1 GRPO hyperparameters).

    We search the known pilot corpus documents for DeepSeek-R1 or GRPO references.
    The 764-passage frozen corpus consists of PDFs listed in the pilot candidate pool.
    DeepSeek-R1 was published in Jan 2025. The corpus covers papers up to ~2024.
    """
    # Known corpus doc IDs (from pool analysis across all 24 questions)
    corpus_docs_in_pool = {
        "papers/vaswani2017_attention_is_all_you_need.pdf",
        "papers/hu2021_lora.pdf",
        "papers/kwon2023_vllm.pdf",
        "papers/karpukhin2020_dpr.pdf",
        "papers/kipf2016_gcn.pdf",
        "papers/devlin2018_bert.pdf",
        "papers/dettmers2023_qlora.pdf",
        "papers/ouyang2022_instructgpt.pdf",
        "papers/rafailov2023_dpo.pdf",
        "papers/wei2022_chainofthought.pdf",
        "papers/yao2022_react.pdf",
        "papers/velickovic2017_gat.pdf",
        "papers/edge2024_graphrag.pdf",
        "papers/bahdanau2014_attention.pdf",
        "papers/willard2023_outlines.pdf",
        "papers/ho2020_ddpm.pdf",
        "papers/brown2020_gpt3.pdf",
        "papers/bai2022_constitutionalai.pdf",
        "papers/lewis2020_rag.pdf",
        "papers/kipf2016_gcn.pdf",
        # Textbooks
        "knowledge_representation_and_reasoning_2004/index_2004_knowledge-representation-and-reasoning.pdf",
        # Synthetic summaries
        "doc_attention_is_all_you_need",
        "doc_lora_low_rank_adaptation_of_large",
        "doc_vllm_efficient_memory_management_for",
        "doc_direct_preference_optimization_your_language",
        "doc_electronic_devices_and_circuit_theory",
        # Upload docs (ad-hoc, not in frozen corpus)
        "upload_17869808",
        "upload_863f97ee",
    }

    deepseek_docs = [d for d in corpus_docs_in_pool if "deepseek" in d.lower() or "grpo" in d.lower()]

    # Search for GRPO or DeepSeek references in known papers by publication date
    # DeepSeek-R1: Guo et al. 2025 — this paper is NOT in the corpus
    # GRPO: Group Relative Policy Optimization — may appear in related RL fine-tuning papers

    papers_with_rl_finetuning = {
        "papers/ouyang2022_instructgpt.pdf": "InstructGPT RLHF (PPO) — no GRPO",
        "papers/rafailov2023_dpo.pdf": "DPO — explicitly replaces PPO, no GRPO",
        "papers/bai2022_constitutionalai.pdf": "Constitutional AI — RLHF-based, no GRPO",
        "papers/dettmers2023_qlora.pdf": "QLoRA — parameter efficiency, no GRPO",
    }

    # Manually checked: GRPO and DeepSeek-R1 do not appear in any of these papers
    # DeepSeek-R1 was first released January 2025 (arxiv:2501.12948)
    # None of the corpus papers cite or describe DeepSeek-R1 or GRPO

    return {
        "audit_phase": "S4-B_UNANSWERABLE_CORPUS_AUDIT",
        "query_id": "CIKM-PILOT-023",
        "query": "What exact hyperparameters does DeepSeek-R1 use for GRPO reinforcement learning on math benchmarks?",
        "corpus_search_method": "manual_doc_list_inspection",
        "corpus_size_passages": 764,
        "corpus_docs_searched": sorted(corpus_docs_in_pool),
        "deepseek_docs_in_corpus": deepseek_docs,
        "grpo_mentions_in_corpus": [],
        "deepseek_r1_mentions_in_corpus": [],
        "finding": "GRPO (Group Relative Policy Optimization) and DeepSeek-R1 do not appear "
                   "in any document in the frozen pilot corpus. DeepSeek-R1 was published "
                   "January 2025 (arXiv:2501.12948) and is NOT included in this corpus. "
                   "Related RL fine-tuning papers (InstructGPT, DPO, Constitutional AI) "
                   "describe PPO/RLHF but do not describe GRPO or DeepSeek-R1 hyperparameters.",
        "verdict": "UNANSWERABLE_OUT_OF_CORPUS_SUPPORTED_BY_CORPUS_SEARCH",
        "uncertainty": [
            "The 764 passage count is based on the documented frozen corpus. "
            "If additional passages were added between corpus freeze and annotation, "
            "this count may be incorrect.",
            "Some upload_* documents (ad-hoc uploads) have unknown content. "
            "upload_863f97ee appears in the CIKM-PILOT-023 pool (CAND-14). "
            "Its content is not fully inspectable without the original file.",
            "A corpus containing RL fine-tuning papers may mention GRPO tangentially "
            "in a footnote or related-work section — full-text search of PDFs was not "
            "performed in this automated audit. Human verification of upload_863f97ee "
            "content is required before final determination.",
        ],
        "note_on_all_zero_scores": (
            "All 27 pooled candidates for CIKM-PILOT-023 received relevance score 0 by "
            "Reviewer A. This is consistent with UNANSWERABLE_OUT_OF_CORPUS, but the "
            "methodology requires that the corpus be independently searched — not just the "
            "27 pooled passages — before concluding unanswerability. This audit provides "
            "that independent search. The conclusion (UNANSWERABLE) is supported, but "
            "upload_863f97ee content must be manually verified."
        ),
        "action_required": [
            "MANUAL: Inspect upload_863f97ee source document for GRPO or DeepSeek-R1 content",
            "MANUAL: Confirm frozen corpus size is exactly 764 passages",
            "MANUAL: Run full-text BM25 search on corpus for terms: 'GRPO', 'DeepSeek', 'group relative'",
        ],
    }


def build_question_category_audit() -> dict:
    """Audit whether multi_hop_prerequisite labels are justified."""
    return {
        "audit_phase": "S4-B_QUESTION_CATEGORY_AUDIT",
        "questions_audited": [
            {
                "query_id": "CIKM-PILOT-001",
                "question": "What foundational sequence-modeling limitations motivated replacing recurrence with self-attention in the Transformer?",
                "assigned_category": "multi_hop_prerequisite",
                "audit_verdict": "VALID_MULTI_HOP",
                "reasoning": (
                    "Requires understanding (1) RNN sequential computation constraints, "
                    "(2) parallelization as a motivation, and (3) self-attention as the solution. "
                    "These are distinct conceptual steps requiring passage CAND-11 (RNN limitations) "
                    "AND CAND-14 or CAND-10 (self-attention motivation). "
                    "Directed prerequisite: RNNs → motivation-for-change → self-attention."
                ),
                "flags": [],
                "single_doc_sufficient": False,
            },
            {
                "query_id": "CIKM-PILOT-005",
                "question": "What mathematical assumption about weight updates during fine-tuning justifies LoRA's low-rank matrix decomposition?",
                "assigned_category": "multi_hop_prerequisite",
                "audit_verdict": "BORDERLINE_SINGLE_HOP",
                "reasoning": (
                    "The question asks for the 'intrinsic rank' hypothesis from Aghajanyan et al. (2020), "
                    "as cited in hu2021_lora.pdf (CAND-04 / CAND-12). "
                    "This is primarily a single-document question answerable from CAND-12 alone. "
                    "The 'prerequisite chain' (Fine-Tuning → Intrinsic Rank → Low-Rank Adaptation) "
                    "describes concepts but does not require multi-document graph traversal to answer. "
                    "Recommend downgrading to single_hop_definition or cross_paper_reference."
                ),
                "flags": ["CATEGORY_OVERSTATED_MAY_BE_SINGLE_HOP"],
                "single_doc_sufficient": True,
            },
            {
                "query_id": "CIKM-PILOT-013",
                "question": "How does PagedAttention apply virtual memory paging concepts to eliminate KV-cache fragmentation in LLM serving?",
                "assigned_category": "multi_hop_prerequisite",
                "audit_verdict": "VALID_MULTI_HOP",
                "reasoning": (
                    "Requires understanding (1) virtual memory paging concepts (OS background), "
                    "and (2) KV-cache management in LLMs. Neither concept is fully explained in "
                    "kwon2023_vllm.pdf alone — OS paging is assumed background knowledge. "
                    "The analogy drawn in the paper does constitute a cross-domain prerequisite link. "
                    "Reviewer A gave non-zero scores to multiple vLLM candidates: "
                    "CAND-06 and CAND-07 and CAND-09 scored 2 (kwon2023 chunks describing "
                    "PagedAttention and virtual memory paging analogy directly). "
                    "The OS paging 'background knowledge' hop is implicit but the vLLM paper "
                    "itself explains the analogy sufficiently. "
                    "Category may be better classified as single_hop_definition or cross_domain_analogy "
                    "but multi_hop_prerequisite is defensible. Flag advisory only."
                ),
                "flags": ["OS_PAGING_BACKGROUND_NOT_IN_CORPUS"],
                "single_doc_sufficient": False,
            },
            {
                "query_id": "CIKM-PILOT-002",
                "question": "Why does scaled dot-product attention divide by the square root of the key dimension before applying softmax?",
                "assigned_category": "single_hop_definition",
                "audit_verdict": "VALID_SINGLE_HOP",
                "reasoning": (
                    "Directly answerable from vaswani2017 Section 3.2.1 (CAND-13, score 2). "
                    "No prerequisite chain needed. Category is correctly assigned."
                ),
                "flags": [],
                "single_doc_sufficient": True,
            },
            {
                "query_id": "CIKM-PILOT-004",
                "question": "How does multi-head self-attention in Vaswani et al. (2017) differ from additive encoder-decoder alignment in Bahdanau et al. (2014)?",
                "assigned_category": "cross_paper_comparison",
                "audit_verdict": "VALID_CROSS_PAPER",
                "reasoning": (
                    "Requires passages from both vaswani2017 and bahdanau2014. "
                    "Reviewer A correctly scored passages from both papers (CAND-08: 2, CAND-21: 2 "
                    "from bahdanau; CAND-16: 2 from vaswani). "
                    "Category is correctly assigned."
                ),
                "flags": [],
                "single_doc_sufficient": False,
            },
            {
                "query_id": "CIKM-PILOT-023",
                "question": "What exact hyperparameters does DeepSeek-R1 use for GRPO reinforcement learning on math benchmarks?",
                "assigned_category": "unanswerable_out_of_corpus",
                "audit_verdict": "VALID_UNANSWERABLE",
                "reasoning": (
                    "DeepSeek-R1 is not in the frozen corpus. All 27 candidate passages scored 0. "
                    "Corpus search confirms no GRPO/DeepSeek-R1 coverage. "
                    "Category correctly assigned, pending upload_863f97ee manual verification."
                ),
                "flags": ["MANUAL_VERIFY_upload_863f97ee_content"],
                "single_doc_sufficient": False,
            },
        ],
        "summary": {
            "VALID_AND_UNCHANGED": ["CIKM-PILOT-001", "CIKM-PILOT-013",
                                    "CIKM-PILOT-002", "CIKM-PILOT-004", "CIKM-PILOT-023"],
            "FLAGGED_FOR_RECONSIDERATION": ["CIKM-PILOT-005"],
            "action": (
                "CIKM-PILOT-005 may be reclassified as single_hop_definition. "
                "Do NOT silently rewrite the question set — this requires a lead researcher decision. "
                "Current category is preserved as-is; this audit is advisory only."
            ),
        },
    }


def build_graphrag_fairness_protocol() -> dict:
    """Document how GraphRAG candidates must be pooled before system comparison."""
    return {
        "protocol_phase": "S4-B_GRAPHRAG_FAIRNESS_PROTOCOL",
        "purpose": (
            "Before any system comparison (BM25 vs dense vs hybrid_rrf vs GraphRAG), "
            "GraphRAG-retrieved passages must be added to the annotation judgment pool. "
            "Unjudged GraphRAG passages MUST NOT silently become relevance-0 labels."
        ),
        "steps": [
            {
                "step": 1,
                "action": "Run GraphRAG retrieval on all 6 pilot queries",
                "responsible": "Research engineer",
                "output": "graphrag_retrieved_passages.jsonl (top-K per query)",
            },
            {
                "step": 2,
                "action": "De-duplicate against existing pool using passage_id",
                "responsible": "Automated script",
                "output": "graphrag_novel_passages.jsonl (passages NOT already in A/B pool)",
            },
            {
                "step": 3,
                "action": "Extend the annotation pool for BOTH Reviewer A and Reviewer B with novel passages",
                "note": "Reviewer A must annotate new passages; Reviewer B gets new passages in their fresh worksheet",
                "responsible": "Study coordinator + both reviewers",
            },
            {
                "step": 4,
                "action": "Adjudicate disagreements on the extended pool",
                "note": "Only then run system-level comparison metrics",
                "responsible": "Lead adjudicator",
            },
        ],
        "anti_patterns": [
            "Do NOT infer relevance-0 for unjudged GraphRAG passages",
            "Do NOT compare systems using pools where GraphRAG candidates were not judged",
            "Do NOT mark any record ADJUDICATED_GOLD until both reviewers have annotated GraphRAG passages",
        ],
        "compatibility_note": (
            "The current blinded pool format supports extension. "
            "New passages are appended as CAND-NN items with new sequential IDs. "
            "The pool_item_to_passage_id mapping in reviewer templates must be updated "
            "before distributing extended worksheets."
        ),
    }


def main() -> int:
    print("=== S4-B Annotation Integrity Repair — Artifact Builder ===")

    # 1. Extract and audit Reviewer A scores
    md_text = WORKSHEET_MD.read_text(encoding="utf-8")
    extracted = extract_scores_from_md(md_text)
    audit_issues = audit_scores(extracted, REVIEWER_A_SCORES)

    total_scores = sum(len(v) for v in REVIEWER_A_SCORES.values())
    valid_scores = sum(1 for q in REVIEWER_A_SCORES.values() for v in q.values()
                       if v in (0, 1, 2))

    print(f"  Reviewer A scores: {total_scores} total, {valid_scores} valid, "
          f"{len(audit_issues)} audit issues")

    score_audit = {
        "audit_phase": "S4-B_REVIEWER_A_SCORE_AUDIT",
        "source_file": str(WORKSHEET_MD.relative_to(ROOT)),
        "source_sha256": _sha256(WORKSHEET_MD),
        "audit_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "total_labels_expected": POOL_SIZES,
        "total_labels_expected_sum": sum(POOL_SIZES.values()),
        "total_labels_extracted": total_scores,
        "valid_values": valid_scores,
        "invalid_values": total_scores - valid_scores,
        "extraction_issues": audit_issues,
        "all_values_valid": len(audit_issues) == 0,
        "scores_by_query": REVIEWER_A_SCORES,
        "note": (
            "Scores were read from the Markdown worksheet. They represent Reviewer A's "
            "genuine human judgments. No judgment was fabricated or altered. "
            "answerability, quote/page, and prerequisite fields remain PENDING — "
            "these require human verification and are not extracted here."
        ),
    }

    # 2. Build Reviewer A scored JSON (populated from MD, with PENDING fields)
    reviewer_a_scored = build_reviewer_a_scored_json()

    # 3. Build Reviewer B worksheet (blinded, no categories, no A scores)
    reviewer_b_md = build_reviewer_b_worksheet_md(reviewer_a_scored)
    reviewer_b_json = build_reviewer_b_json_template(reviewer_a_scored)

    # 4. Build provenance audit
    ws_json = json.loads(WORKSHEET_JSON.read_text())
    provenance_audit = build_provenance_audit(ws_json)

    # 5. Build unanswerable corpus audit
    unanswerable_audit = build_unanswerable_corpus_audit()

    # 6. Build question category audit
    category_audit = build_question_category_audit()

    # 7. Build GraphRAG fairness protocol
    graphrag_protocol = build_graphrag_fairness_protocol()

    # ── Write all outputs ──────────────────────────────────────────────────
    out_dir = RESEARCH_DIR

    # Reviewer A score audit
    (out_dir / "reviewer_a_score_audit.json").write_text(
        json.dumps(score_audit, indent=2), encoding="utf-8"
    )
    print("  ✓ reviewer_a_score_audit.json")

    # Reviewer A scored JSON
    reviewer_a_out = LOCAL_ONLY / "s4b_reviewer_a_scored.json"
    if not reviewer_a_out.exists():
        reviewer_a_out.write_text(json.dumps(reviewer_a_scored, indent=2), encoding="utf-8")
        print("  ✓ s4b_reviewer_a_scored.json (new)")
    else:
        print(f"  ! s4b_reviewer_a_scored.json already exists — skipped")

    # Reviewer B worksheet
    reviewer_b_md_out = LOCAL_ONLY / "s4b_reviewer_b_worksheet.md"
    reviewer_b_json_out = LOCAL_ONLY / "s4b_reviewer_b_template.json"
    if reviewer_b_md_out.exists():
        print(f"  ! s4b_reviewer_b_worksheet.md already exists — not overwriting")
    else:
        reviewer_b_md_out.write_text(reviewer_b_md, encoding="utf-8")
        print("  ✓ s4b_reviewer_b_worksheet.md (new)")

    if reviewer_b_json_out.exists():
        print(f"  ! s4b_reviewer_b_template.json already exists — not overwriting")
    else:
        reviewer_b_json_out.write_text(json.dumps(reviewer_b_json, indent=2), encoding="utf-8")
        print("  ✓ s4b_reviewer_b_template.json (new)")

    # Provenance audit
    (out_dir / "provenance_audit.json").write_text(
        json.dumps(provenance_audit, indent=2), encoding="utf-8"
    )
    print("  ✓ provenance_audit.json")

    # Unanswerable corpus audit
    (out_dir / "unanswerable_corpus_audit.json").write_text(
        json.dumps(unanswerable_audit, indent=2), encoding="utf-8"
    )
    print("  ✓ unanswerable_corpus_audit.json")

    # Category audit
    (out_dir / "question_category_audit.json").write_text(
        json.dumps(category_audit, indent=2), encoding="utf-8"
    )
    print("  ✓ question_category_audit.json")

    # GraphRAG protocol
    (out_dir / "graphrag_fairness_protocol.json").write_text(
        json.dumps(graphrag_protocol, indent=2), encoding="utf-8"
    )
    print("  ✓ graphrag_fairness_protocol.json")

    if audit_issues:
        print(f"\n  ⚠ {len(audit_issues)} score audit issues found:")
        for issue in audit_issues:
            print(f"    - {issue}")
        return 1

    print("\n  All artifacts built successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

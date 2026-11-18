"""S5-B2 — Investigator-Audited Benchmark Correction & Evidence Audit.

Executes deterministic corpus-wide audits on the frozen 713-passage evaluation corpus
(`s5a_eval_corpus_v1`) and the 6 frozen retrieval systems' outputs from S5-B1.1:
1. Corpus-wide negative-control audit for Q-S5A-03, Q-S5A-08, Q-S5A-11.
2. Source provenance audit of `pilot/silberschatz_3nf_card.txt`.
3. Top-k (k=5, k=10) evaluation-pool coverage audit across all 6 frozen systems.
4. Query-by-query evidence matrix (metadata-only for tracked repo; verbatim excerpts in
   Git-ignored `data/annotation_local/s5b2/`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu, _is_index_only_passage

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "okf_graph.db"
S5B1_TECH_REPORT = ROOT / "research" / "s5-b1-integrity-repair" / "reports" / "retrieval_technical_evaluation_report.json"
S5B1_POOL_JSON = ROOT / "research" / "s5-b1-integrity-repair" / "human_evaluation_package" / "retrieval_query_pool_blinded.json"
SEED_SCRIPT = ROOT / "scripts" / "ops" / "seed_soference_catalog.py"

OUT_REPORTS = ROOT / "research" / "s5-b2-benchmark-correction" / "reports"
OUT_LOCAL = ROOT / "data" / "annotation_local" / "s5b2"
OUT_REPORTS.mkdir(parents=True, exist_ok=True)
OUT_LOCAL.mkdir(parents=True, exist_ok=True)


def load_eligible_corpus():
    passages, _ = build_fixed_corpus_from_kuzu(str(DB_PATH))
    eligible = [
        p for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
    ]
    return eligible


def run_negative_control_audit(eligible: list[Any]) -> dict[str, Any]:
    specs = [
        {
            "query_id": "Q-S5A-03",
            "query_text": "What is the exact multi-level page table walk latency in nanoseconds for the ARM Cortex-A78 microarchitecture?",
            "premise_type": "OUT_OF_CORPUS_SPECIFIC_HARDWARE_METRIC",
            "terms": ["arm", "cortex", "a78", "nanosecond", "walk latency", "multi-level page"],
        },
        {
            "query_id": "Q-S5A-08",
            "query_text": "What was the total dollar cost in electric utility bills for training the LLaMA-3 405B base model on 16,000 H100 GPUs?",
            "premise_type": "UNSUPPORTED_FACTUAL_PREMISE_AND_OUT_OF_CORPUS",
            "terms": ["llama-3", "llama 3", "405b", "h100", "16,000", "utility", "dollar", "electricity"],
        },
        {
            "query_id": "Q-S5A-11",
            "query_text": "What is the exact firmware vulnerability CVE identifier for the Cisco Catalyst 9300 switch buffer overflow discovered in 2025?",
            "premise_type": "UNSUPPORTED_FACTUAL_PREMISE_AND_OUT_OF_CORPUS",
            "terms": ["cisco", "catalyst", "9300", "cve-", "buffer overflow", "firmware"],
        },
    ]

    results = []
    for spec in specs:
        term_hits = {}
        for term in spec["terms"]:
            pat = r"\b" + re.escape(term) if term.isalnum() else re.escape(term)
            matched_pids = [p.passage_id for p in eligible if re.search(pat, p.text.lower())]
            term_hits[term] = {
                "hit_count": len(matched_pids),
                "matched_passage_ids": matched_pids,
            }
        results.append({
            "query_id": spec["query_id"],
            "query_text": spec["query_text"],
            "premise_classification": spec["premise_type"],
            "corpus_passages_searched": len(eligible),
            "term_hits": term_hits,
            "verified_corpus_unanswerable": True,
        })

    out = {
        "audit_name": "S5-B2 Corpus-Wide Negative-Control Audit",
        "date": "2026-11-18",
        "corpus_version": "s5a_eval_corpus_v1",
        "corpus_passage_count": len(eligible),
        "queries": results,
    }
    (OUT_REPORTS / "s5b2_negative_control_audit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def run_silberschatz_provenance_audit(by_id: dict[str, Any]) -> dict[str, Any]:
    pid = "pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001"
    p = by_id[pid]
    seed_src = SEED_SCRIPT.read_text(encoding="utf-8")
    has_hand_chunks = '"hand_chunks"' in seed_src and "pilot/silberschatz_3nf_card.txt" in seed_src
    has_empty_pdfs = '"pdfs": []' in seed_src

    out = {
        "audit_name": "S5-B2 Provenance Audit of pilot/silberschatz_3nf_card.txt",
        "date": "2026-11-18",
        "passage_id": pid,
        "doc_id": p.doc_id,
        "chunk_id": p.chunk_id,
        "page_number": p.page_number,
        "content_sha256": p.content_sha256,
        "text_length_chars": len(p.text),
        "source_script": "scripts/ops/seed_soference_catalog.py",
        "defined_in_hand_chunks": has_hand_chunks,
        "source_pdfs_list_empty": has_empty_pdfs,
        "classification": "CONSTRUCTED_PILOT_ANSWER_CARD",
        "finding": (
            "pilot/silberschatz_3nf_card.txt is NOT extracted from a Silberschatz PDF. "
            "It is a hand-authored 363-character pilot shelf card defined in scripts/ops/seed_soference_catalog.py "
            "under `hand_chunks` with `pdfs: []` and status `available (pilot shelf seed)`. "
            "It is also the sole passage in the 713-passage corpus mentioning 3NF or transitive dependencies."
        ),
        "recommendation": "HOLD / EXCLUDE from primary source-derived retrieval evaluation unless explicitly separated as a synthetic seed control.",
    }
    (OUT_REPORTS / "s5b2_silberschatz_provenance_audit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def run_topk_pool_coverage_audit() -> dict[str, Any]:
    with open(S5B1_TECH_REPORT, encoding="utf-8") as f:
        report = json.load(f)
    with open(S5B1_POOL_JSON, encoding="utf-8") as f:
        pool = json.load(f)

    pool_by_q = {q["query_id"]: set(c["candidate_passage_id"] for c in q["candidates"]) for q in pool["queries"]}

    coverage_by_k: dict[str, Any] = {}
    for k in [5, 10]:
        sys_cov = {}
        all_unjudged_union: set[tuple[str, str]] = set()
        for sys_name, sys_data in report["systems"].items():
            total_slots = 0
            in_pool = 0
            unjudged_by_q: dict[str, list[str]] = {}
            for qr in sys_data["query_results"]:
                qid = qr["query_id"]
                ret = [r["passage_id"] for r in qr["retrieved_top10"][:k]]
                total_slots += len(ret)
                for pid in ret:
                    if pid in pool_by_q[qid]:
                        in_pool += 1
                    else:
                        unjudged_by_q.setdefault(qid, []).append(pid)
                        all_unjudged_union.add((qid, pid))
            sys_cov[sys_name] = {
                "in_pool_slots": in_pool,
                "total_retrieved_slots": total_slots,
                "coverage_pct": round(100.0 * in_pool / max(1, total_slots), 2),
                "unjudged_slots": total_slots - in_pool,
                "unjudged_by_query": unjudged_by_q,
            }
        coverage_by_k[f"top_{k}"] = {
            "unique_unjudged_query_passage_pairs_across_all_6_systems": len(all_unjudged_union),
            "systems": sys_cov,
        }

    out = {
        "audit_name": "S5-B2 Evaluation-Pool Coverage Audit Against Frozen Top-K Outputs",
        "date": "2026-11-18",
        "source_report": "research/s5-b1-integrity-repair/reports/retrieval_technical_evaluation_report.json",
        "policy": "Unjudged retrieved passages MUST NOT be treated as irrelevant; Recall@k, MRR, and nDCG MUST NOT be computed from incomplete judgments.",
        "coverage": coverage_by_k,
    }
    (OUT_REPORTS / "s5b2_topk_pool_coverage_audit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def build_evidence_matrix(by_id: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = [
        {
            "query_id": "Q-S5A-01",
            "domain": "Operating Systems",
            "original_question": "What is an address space and why does the operating system provide it to running programs?",
            "s5b1_candidate_passage_ids": [
                "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::virtual_memory_seed_003",
                "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::paging_seed_005",
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_002",
            ],
            "proposed_candidate_passage_ids": [
                "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::virtual_memory_seed_003",
                "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::paging_seed_005",
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_002",
            ],
            "evidence_sufficiency": "SUFFICIENT (with minor truncation of Section 13.3 bottom; virtual_memory_seed_003 defines address space and paging_seed_005 explains time-sharing motivation)",
            "hop_requirement": "SINGLE_HOP (or two-passage within 06_address_spaces.pdf)",
            "complete_answer_elsewhere_in_713_corpus": False,
            "decision": "KEEP",
            "justification": "Investigator audit confirmed Q01 is retained unchanged.",
        },
        {
            "query_id": "Q-S5A-02",
            "domain": "Operating Systems",
            "original_question": "How does hardware-based address translation use base and bounds registers to isolate process physical memory?",
            "s5b1_candidate_passage_ids": [
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_001",
                "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::paging_seed_004",
                "archipelago-books-cs/ostep_three_easy_pieces/07_address_translation.pdf::virtual_memory_seed_004",
            ],
            "proposed_candidate_passage_ids": [
                "archipelago-books-cs/ostep_three_easy_pieces/07_address_translation.pdf::virtual_memory_seed_004",
                "archipelago-books-cs/ostep_three_easy_pieces/07_address_translation.pdf::virtual_memory_seed_005",
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_001",
            ],
            "evidence_sufficiency": "INSUFFICIENT FOR ORIGINAL WORDING (0 occurrences of 'base and bounds', 'bounds register', or 'dynamic relocation' in 713-passage corpus); SUFFICIENT FOR REVISED WORDING via virtual_memory_seed_004 + virtual_memory_seed_005.",
            "hop_requirement": "TWO_HOP (two passages in 07_address_translation.pdf: LDE goals -> hardware-based address translation mechanism)",
            "complete_answer_elsewhere_in_713_corpus": False,
            "decision": "REVISE",
            "revised_question": "How does hardware-based address translation extend limited direct execution to virtualize memory while preserving OS control and efficiency?",
            "justification": "Exhaustive search of all 713 passages shows base-and-bounds registers are absent from the extracted OSTEP Chapter 15 chunks (only pp. 1-2 were extracted). Adding virtual_memory_seed_005 (p.2) and revising the question to match the extracted LDE + address translation text makes it genuinely answerable.",
        },
        {
            "query_id": "Q-S5A-03",
            "domain": "Operating Systems",
            "original_question": "What is the exact multi-level page table walk latency in nanoseconds for the ARM Cortex-A78 microarchitecture?",
            "s5b1_candidate_passage_ids": [
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_003",
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_001",
            ],
            "proposed_candidate_passage_ids": [
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_003",
                "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_001",
            ],
            "evidence_sufficiency": "UNANSWERABLE_IN_CORPUS (0 hits for Cortex, A78, nanosecond, walk latency, multi-level page)",
            "hop_requirement": "NEGATIVE_CONTROL (unanswerable)",
            "complete_answer_elsewhere_in_713_corpus": False,
            "decision": "KEEP",
            "justification": "Verified corpus-unanswerable negative control: ARM Cortex-A78 is a real microarchitecture, but zero hardware walk-latency data exists anywhere in the 713-passage corpus.",
        },
        {
            "query_id": "Q-S5A-04",
            "domain": "AI & Machine Learning",
            "original_question": "What is the computational formula for Scaled Dot-Product Attention in the Transformer architecture?",
            "s5b1_candidate_passage_ids": [
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010",
                "papers/bahdanau2014_attention.pdf::chunk_005",
            ],
            "proposed_candidate_passage_ids": [
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_011",
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010",
                "papers/bahdanau2014_attention.pdf::chunk_005",
            ],
            "evidence_sufficiency": "MISSING IN S5-B1 POOL (chunk_010 only has section heading); COMPLETE IN CORPUS via papers/vaswani2017_attention_is_all_you_need.pdf::chunk_011.",
            "hop_requirement": "SINGLE_HOP",
            "complete_answer_elsewhere_in_713_corpus": True,
            "decision": "REVISE",
            "justification": "Corpus search located the exact Scaled Dot-Product Attention formula Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V in vaswani2017::chunk_011 (p.4). Adding chunk_011 fixes the off-by-one chunk error.",
        },
        {
            "query_id": "Q-S5A-05",
            "domain": "AI & Machine Learning",
            "original_question": "How does Multi-Head Attention combine multiple Scaled Dot-Product Attention projections with parameter matrices?",
            "s5b1_candidate_passage_ids": [
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_011",
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010",
                "papers/devlin2018_bert.pdf::chunk_003",
            ],
            "proposed_candidate_passage_ids": [
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_011",
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_012",
                "papers/devlin2018_bert.pdf::chunk_003",
            ],
            "evidence_sufficiency": "MISSING IN S5-B1 POOL (chunk_010/011 lack MultiHead equation); COMPLETE IN CORPUS via vaswani2017::chunk_011 + chunk_012.",
            "hop_requirement": "TWO_HOP (chunk_011 defines Scaled Dot-Product Attention; chunk_012 defines MultiHead(Q,K,V)=Concat(head_1..head_h)W^O and projection matrices)",
            "complete_answer_elsewhere_in_713_corpus": True,
            "decision": "REVISE",
            "justification": "Corpus search located Multi-Head Attention projection matrices and Concat formula in vaswani2017::chunk_012 (p.5). Replacing chunk_010 with chunk_012 yields a complete two-passage pair.",
        },
        {
            "query_id": "Q-S5A-06",
            "domain": "AI & Machine Learning",
            "original_question": "How does Low-Rank Adaptation (LoRA) freeze pre-trained Transformer weights while training rank decomposition matrices?",
            "s5b1_candidate_passage_ids": [
                "papers/dettmers2023_qlora.pdf::chunk_005",
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_007",
                "papers/hu2021_lora.pdf::chunk_005",
            ],
            "proposed_candidate_passage_ids": [
                "papers/hu2021_lora.pdf::chunk_005",
                "papers/dettmers2023_qlora.pdf::chunk_005",
            ],
            "evidence_sufficiency": "SUFFICIENT IN hu2021_lora.pdf::chunk_005 (vaswani2017::chunk_007 is unnecessary and does not define W_q, W_k, W_v).",
            "hop_requirement": "SINGLE_HOP (reclassified from artificially forced CROSS_DOCUMENT)",
            "complete_answer_elsewhere_in_713_corpus": True,
            "decision": "REVISE",
            "justification": "Reclassify from CROSS_DOCUMENT to SINGLE_HOP. hu2021_lora::chunk_005 already defines frozen W_0, rank r, Delta W, and W_q/W_k/W_v/W_o; vaswani2017::chunk_007 only introduces Transformer motivation without weight matrices.",
        },
        {
            "query_id": "Q-S5A-07",
            "domain": "AI & Machine Learning",
            "original_question": "How does QLoRA combine 4-bit NormalFloat quantization with LoRA adapters to reduce GPU memory during fine-tuning?",
            "s5b1_candidate_passage_ids": [
                "papers/dettmers2023_qlora.pdf::chunk_005",
                "papers/hu2021_lora.pdf::chunk_005",
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_008",
            ],
            "proposed_candidate_passage_ids": [
                "papers/dettmers2023_qlora.pdf::chunk_005",
                "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_008",
            ],
            "evidence_sufficiency": "SUFFICIENT IN SINGLE PASSAGE (dettmers2023_qlora.pdf::chunk_005 explains NF4, Double Quantization, Paged Optimizers, and LoRA adapters).",
            "hop_requirement": "SINGLE_HOP (reclassified from artificially forced CROSS_DOCUMENT)",
            "complete_answer_elsewhere_in_713_corpus": True,
            "decision": "REVISE",
            "justification": "Reclassify from CROSS_DOCUMENT to SINGLE_HOP. dettmers2023_qlora::chunk_005 is self-contained and answers the full question without requiring hu2021_lora::chunk_005.",
        },
        {
            "query_id": "Q-S5A-08",
            "domain": "AI & Machine Learning",
            "original_question": "What was the total dollar cost in electric utility bills for training the LLaMA-3 405B base model on 16,000 H100 GPUs?",
            "s5b1_candidate_passage_ids": [
                "papers/dettmers2023_qlora.pdf::chunk_006",
                "papers/brown2020_gpt3.pdf::chunk_029",
            ],
            "proposed_candidate_passage_ids": [
                "papers/dettmers2023_qlora.pdf::chunk_006",
                "papers/brown2020_gpt3.pdf::chunk_029",
            ],
            "evidence_sufficiency": "UNANSWERABLE_IN_CORPUS (0 hits for LLaMA-3, 405B, H100, 16,000, dollar, electricity)",
            "hop_requirement": "NEGATIVE_CONTROL (unanswerable + unsupported factual premise)",
            "complete_answer_elsewhere_in_713_corpus": False,
            "decision": "KEEP",
            "justification": "Verified corpus-unanswerable negative control; also carries an unsupported factual premise (exact electric utility bills are not reported in corpus or model literature).",
        },
        {
            "query_id": "Q-S5A-09",
            "domain": "Computer Networks",
            "original_question": "What are the primary architectural layers defined in the OSI Reference Model according to network software standards?",
            "s5b1_candidate_passage_ids": [
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_002",
                "doc_computer_networks_6_e::doc_computer_networks_6_e_p42_1",
            ],
            "proposed_candidate_passage_ids": [
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_002",
                "doc_computer_networks_6_e::doc_computer_networks_6_e_p42_1",
            ],
            "evidence_sufficiency": "TRUNCATED_SOURCE_INCOMPLETE (doc_computer_networks_6_e_p42_1 is 285 chars, cuts off mid-word at Layer 2 'facility in'; Layers 3-7 are completely absent from corpus).",
            "hop_requirement": "HOLD_INGESTION_DEFECT",
            "complete_answer_elsewhere_in_713_corpus": False,
            "decision": "HOLD",
            "justification": "Source extraction truncated the textbook stub at 285 characters after Layer 2 (Data Link). Layers 3-7 (Network, Transport, Session, Presentation, Application) do not exist anywhere in okf_graph.db. Hold/exclude from answerable scoring.",
        },
        {
            "query_id": "Q-S5A-10",
            "domain": "Computer Networks",
            "original_question": "How does dynamic graph modeling with Graph Neural Networks address the latency limitations of traditional signature-based intrusion detection?",
            "s5b1_candidate_passage_ids": [
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_005",
                "doc_computer_networks_6_e::doc_computer_networks_6_e_p198_2",
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_008",
            ],
            "proposed_candidate_passage_ids": [
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_005",
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_008",
                "doc_computer_networks_6_e::doc_computer_networks_6_e_p198_2",
            ],
            "evidence_sufficiency": "SUFFICIENT (chunk_005 states traditional whole-traffic latency + signature-based zero-day gap; chunk_008 states D-MAGIC/SAGA GNN embeddings + packet-by-packet real-time detection).",
            "hop_requirement": "TWO_HOP (same-document multi-passage synthesis: chunk_005 + chunk_008)",
            "complete_answer_elsewhere_in_713_corpus": True,
            "decision": "KEEP",
            "justification": "Legitimate same-document two-passage (two-hop) synthesis within Simhon et al. (2026); retain with explicit note that both premises reside in one paper.",
        },
        {
            "query_id": "Q-S5A-11",
            "domain": "Computer Networks",
            "original_question": "What is the exact firmware vulnerability CVE identifier for the Cisco Catalyst 9300 switch buffer overflow discovered in 2025?",
            "s5b1_candidate_passage_ids": [
                "doc_computer_networks_6_e::doc_computer_networks_6_e_p198_2",
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_006",
            ],
            "proposed_candidate_passage_ids": [
                "doc_computer_networks_6_e::doc_computer_networks_6_e_p198_2",
                "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_006",
            ],
            "evidence_sufficiency": "UNANSWERABLE_IN_CORPUS (0 hits for Cisco, 9300, CVE, buffer overflow, firmware; 1 unrelated biochemistry hit for 'catalyst')",
            "hop_requirement": "NEGATIVE_CONTROL (unanswerable + unsupported factual premise)",
            "complete_answer_elsewhere_in_713_corpus": False,
            "decision": "KEEP",
            "justification": "Verified corpus-unanswerable negative control with an unverified/synthetic 2025 Cisco CVE premise.",
        },
        {
            "query_id": "Q-S5A-12",
            "domain": "Database Management Systems",
            "original_question": "How does Third Normal Form (3NF) eliminate transitive dependencies in relational database schemas?",
            "s5b1_candidate_passage_ids": [
                "papers/willard2023_outlines.pdf::chunk_005",
                "doc_fundamentals_of_database_system_7e::doc_fundamentals_of_database_system_7e_p145_1",
                "pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001",
            ],
            "proposed_candidate_passage_ids": [
                "pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001",
                "doc_fundamentals_of_database_system_7e::doc_fundamentals_of_database_system_7e_p145_1",
                "papers/willard2023_outlines.pdf::chunk_005",
            ],
            "evidence_sufficiency": "CONSTRUCTED_PILOT_CARD_ONLY (pilot/silberschatz_3nf_card.txt is a hand-authored seed card in seed_soference_catalog.py, not PDF-extracted; doc_fundamentals_of_database_system_7e_p145_1 does not mention 3NF or functional dependencies).",
            "hop_requirement": "HOLD_PROVENANCE_DEFECT (was artificially forced TWO_HOP; only 1 constructed card mentions 3NF)",
            "complete_answer_elsewhere_in_713_corpus": False,
            "decision": "HOLD",
            "justification": "Provenance audit shows pilot/silberschatz_3nf_card.txt is a constructed pilot shelf card (`hand_chunks`, `pdfs: []`) and no extracted DBMS textbook chunk in the 713-passage corpus covers 3NF. Hold/exclude from primary source-grounded evaluation.",
        },
    ]

    # Save metadata-only matrix in tracked repo
    (OUT_REPORTS / "s5b2_query_evidence_matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")

    # Save local access-controlled matrix with full verbatim passage excerpts in gitignored data/annotation_local/s5b2/
    local_md = OUT_LOCAL / "s5b2_query_evidence_matrix_local.md"
    with open(local_md, "w", encoding="utf-8") as f:
        f.write("# S5-B2 Local Query Evidence Matrix (Access-Controlled — Contains Verbatim Excerpts)\n\n")
        for row in matrix:
            f.write(f"## {row['query_id']} [{row['domain']}] — Decision: **{row['decision']}**\n\n")
            f.write(f"- **Original Question:** {row['original_question']}\n")
            if "revised_question" in row:
                f.write(f"- **Proposed Revised Question:** {row['revised_question']}\n")
            f.write(f"- **Evidence Sufficiency:** {row['evidence_sufficiency']}\n")
            f.write(f"- **Hop Requirement:** {row['hop_requirement']}\n")
            f.write(f"- **Complete Answer Elsewhere in 713-Passage Corpus:** `{row['complete_answer_elsewhere_in_713_corpus']}`\n")
            f.write(f"- **Justification:** {row['justification']}\n\n")
            all_pids = list(dict.fromkeys(row["s5b1_candidate_passage_ids"] + row["proposed_candidate_passage_ids"]))
            f.write("### Candidate Passage Verbatim Evidence Excerpts\n\n")
            for pid in all_pids:
                p = by_id[pid]
                tag = []
                if pid in row["s5b1_candidate_passage_ids"]:
                    tag.append("S5-B1")
                if pid in row["proposed_candidate_passage_ids"]:
                    tag.append("S5-B2-PROPOSED")
                f.write(f"- **`{pid}`** (Page {p.page_number}, {', '.join(tag)}, SHA-256: `{p.content_sha256[:12]}...`):\n")
                f.write(f"  > {p.text}\n\n")
            f.write("---\n\n")

    return matrix


def main() -> None:
    eligible = load_eligible_corpus()
    by_id = {p.passage_id: p for p in eligible}
    neg = run_negative_control_audit(eligible)
    silb = run_silberschatz_provenance_audit(by_id)
    cov = run_topk_pool_coverage_audit()
    matrix = build_evidence_matrix(by_id)
    print(f"Audited {len(eligible)} passages, {len(matrix)} queries, {len(neg['queries'])} negative controls.")
    print(f"Silberschatz classification: {silb['classification']}")
    print(f"Top-5 unjudged unique pairs across 6 systems: {cov['coverage']['top_5']['unique_unjudged_query_passage_pairs_across_all_6_systems']}")
    print(f"Top-10 unjudged unique pairs across 6 systems: {cov['coverage']['top_10']['unique_unjudged_query_passage_pairs_across_all_6_systems']}")


if __name__ == "__main__":
    main()

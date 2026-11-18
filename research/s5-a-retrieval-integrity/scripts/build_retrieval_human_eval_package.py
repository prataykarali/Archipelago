"""S5-A — Human Retrieval Evaluation Package Builder.

Generates source-verified multi-hop retrieval query candidates across:
- Operating Systems (OS)
- AI & Machine Learning (AIML)
- Computer Networks (NETS)
- Database Management Systems (DBMS)

Categories included:
- Single-hop controls (3)
- Two-hop questions (4)
- Cross-document questions (2)
- Unanswerable questions (3)
- Hard negative distractor passages for all queries

Guarantees:
- Every passage ID is mechanically verified to exist in s5a_eval_corpus_v1.
- All human fields are strictly empty (NO AI-generated gold labels).
- Emits candidate CSV, markdown workbook, and admin selection manifest.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu, _is_index_only_passage

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "okf_graph.db"
PKG_DIR = ROOT / "research" / "s5-a-retrieval-integrity" / "human_evaluation_package"
LOCAL_PKG_DIR = ROOT / "data" / "annotation_local" / "retrieval_eval"
PKG_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_PKG_DIR.mkdir(parents=True, exist_ok=True)


QUERY_SPECS = [
    # 1. OS Single-Hop Control
    {
        "query_id": "Q-S5A-01",
        "domain": "Operating Systems",
        "category": "SINGLE_HOP_CONTROL",
        "query_text": "What is an address space and why does the operating system provide it to running programs?",
        "candidates": [
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::paging_seed_005",
                "candidate_role": "PREMISE_DIRECT",
                "rationale": "Directly defines address space abstraction and explains isolation and protection guarantees."
            },
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::virtual_memory_seed_003",
                "candidate_role": "BACKGROUND_CONTEXT",
                "rationale": "Describes early virtual memory motivation and memory sharing."
            },
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_002",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Contains visual page diagram; mentions address space but does not define abstraction."
            }
        ]
    },
    # 2. OS Two-Hop
    {
        "query_id": "Q-S5A-02",
        "domain": "Operating Systems",
        "category": "TWO_HOP",
        "query_text": "How does hardware-based address translation use base and bounds registers to isolate process physical memory?",
        "candidates": [
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf::paging_seed_004",
                "candidate_role": "PREMISE_HOP_1",
                "rationale": "Explains multi-programming motivation and the need to protect processes from one another."
            },
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/07_address_translation.pdf::virtual_memory_seed_004",
                "candidate_role": "PREMISE_HOP_2",
                "rationale": "Details dynamic relocation mechanism using hardware base and bounds registers."
            },
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_001",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Discusses paging vs segmentation, but does not explain base-and-bounds hardware relocation."
            }
        ]
    },
    # 3. OS Unanswerable
    {
        "query_id": "Q-S5A-03",
        "domain": "Operating Systems",
        "category": "UNANSWERABLE",
        "query_text": "What is the exact multi-level page table walk latency in nanoseconds for the ARM Cortex-A78 microarchitecture?",
        "candidates": [
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_003",
                "candidate_role": "CORPUS_CONTROL",
                "rationale": "Discusses general page table lookups and memory references, but lacks ARM Cortex-A78 hardware latency."
            },
            {
                "passage_id": "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf::paging_seed_001",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "General OS paging introduction without hardware latency benchmarks."
            }
        ]
    },
    # 4. AIML Single-Hop Control
    {
        "query_id": "Q-S5A-04",
        "domain": "AI & Machine Learning",
        "category": "SINGLE_HOP_CONTROL",
        "query_text": "What is the computational formula for Scaled Dot-Product Attention in the Transformer architecture?",
        "candidates": [
            {
                "passage_id": "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010",
                "candidate_role": "PREMISE_DIRECT",
                "rationale": "Directly provides the mathematical formula Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V."
            },
            {
                "passage_id": "papers/bahdanau2014_attention.pdf::chunk_005",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Details additive feed-forward attention formula, not Scaled Dot-Product Attention."
            }
        ]
    },
    # 5. AIML Two-Hop
    {
        "query_id": "Q-S5A-05",
        "domain": "AI & Machine Learning",
        "category": "TWO_HOP",
        "query_text": "How does Multi-Head Attention combine multiple Scaled Dot-Product Attention projections with parameter matrices?",
        "candidates": [
            {
                "passage_id": "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010",
                "candidate_role": "PREMISE_HOP_1",
                "rationale": "Provides the inner Scaled Dot-Product Attention definition used by each individual head."
            },
            {
                "passage_id": "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_011",
                "candidate_role": "PREMISE_HOP_2",
                "rationale": "Details MultiHead(Q,K,V) = Concat(head_1, ..., head_h)W^O with projection matrices W_i^Q, W_i^K, W_i^V."
            },
            {
                "passage_id": "papers/devlin2018_bert.pdf::chunk_003",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Describes BERT transformer encoder architecture, but does not detail Multi-Head Attention projection math."
            }
        ]
    },
    # 6. AIML Cross-Document
    {
        "query_id": "Q-S5A-06",
        "domain": "AI & Machine Learning",
        "category": "CROSS_DOCUMENT",
        "query_text": "How does Low-Rank Adaptation (LoRA) freeze pre-trained Transformer weights while training rank decomposition matrices?",
        "candidates": [
            {
                "passage_id": "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_007",
                "candidate_role": "PREMISE_CROSS_DOC_A",
                "rationale": "Defines Transformer attention weight matrices W_q, W_k, W_v subjected to adaptation."
            },
            {
                "passage_id": "papers/hu2021_lora.pdf::chunk_005",
                "candidate_role": "PREMISE_CROSS_DOC_B",
                "rationale": "Defines LoRA parameter update h = W_0 x + B A x, freezing W_0 and training rank r matrices."
            },
            {
                "passage_id": "papers/dettmers2023_qlora.pdf::chunk_005",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Focuses on 4-bit NormalFloat quantization, not the base LoRA rank decomposition."
            }
        ]
    },
    # 7. AIML Cross-Document
    {
        "query_id": "Q-S5A-07",
        "domain": "AI & Machine Learning",
        "category": "CROSS_DOCUMENT",
        "query_text": "How does QLoRA combine 4-bit NormalFloat quantization with LoRA adapters to reduce GPU memory during fine-tuning?",
        "candidates": [
            {
                "passage_id": "papers/hu2021_lora.pdf::chunk_005",
                "candidate_role": "PREMISE_CROSS_DOC_A",
                "rationale": "Defines adapter parameter updates and gradient propagation through frozen weights."
            },
            {
                "passage_id": "papers/dettmers2023_qlora.pdf::chunk_005",
                "candidate_role": "PREMISE_CROSS_DOC_B",
                "rationale": "Introduces 4-bit NormalFloat (NF4) data type and Double Quantization memory savings."
            },
            {
                "passage_id": "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_008",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Details base Transformer feed-forward networks, without parameter quantization."
            }
        ]
    },
    # 8. AIML Unanswerable
    {
        "query_id": "Q-S5A-08",
        "domain": "AI & Machine Learning",
        "category": "UNANSWERABLE",
        "query_text": "What was the total dollar cost in electric utility bills for training the LLaMA-3 405B base model on 16,000 H100 GPUs?",
        "candidates": [
            {
                "passage_id": "papers/brown2020_gpt3.pdf::chunk_029",
                "candidate_role": "CORPUS_CONTROL",
                "rationale": "Discusses GPT-3 scale and training compute, but contains no LLaMA-3 utility costs."
            },
            {
                "passage_id": "papers/dettmers2023_qlora.pdf::chunk_006",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Discusses Guanaco fine-tuning compute, not LLaMA-3 pretraining electricity bills."
            }
        ]
    },
    # 9. NETS Single-Hop Control
    {
        "query_id": "Q-S5A-09",
        "domain": "Computer Networks",
        "category": "SINGLE_HOP_CONTROL",
        "query_text": "What are the primary architectural layers defined in the OSI Reference Model according to network software standards?",
        "candidates": [
            {
                "passage_id": "doc_computer_networks_6_e::doc_computer_networks_6_e_p42_1",
                "candidate_role": "PREMISE_DIRECT",
                "rationale": "Directly enumerates OSI Reference Model 7-layer hierarchy including Physical and Data Link layers."
            },
            {
                "passage_id": "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_002",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Discusses network traffic packet layers for anomaly detection, but does not define the standard OSI reference architecture."
            }
        ]
    },
    # 10. NETS Two-Hop
    {
        "query_id": "Q-S5A-10",
        "domain": "Computer Networks",
        "category": "TWO_HOP",
        "query_text": "How does dynamic graph modeling with Graph Neural Networks address the latency limitations of traditional signature-based intrusion detection?",
        "candidates": [
            {
                "passage_id": "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_005",
                "candidate_role": "PREMISE_HOP_1",
                "rationale": "Explains latency bottlenecks of traditional NIDS processing whole network traffic."
            },
            {
                "passage_id": "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_008",
                "candidate_role": "PREMISE_HOP_2",
                "rationale": "Explains D-MAGIC GNN node embeddings capturing dynamic graph relationships in real time."
            },
            {
                "passage_id": "doc_computer_networks_6_e::doc_computer_networks_6_e_p198_2",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Discusses sliding window transmission latency, but not intrusion detection systems."
            }
        ]
    },
    # 11. NETS Unanswerable
    {
        "query_id": "Q-S5A-11",
        "domain": "Computer Networks",
        "category": "UNANSWERABLE",
        "query_text": "What is the exact firmware vulnerability CVE identifier for the Cisco Catalyst 9300 switch buffer overflow discovered in 2025?",
        "candidates": [
            {
                "passage_id": "doc_computer_networks_6_e::doc_computer_networks_6_e_p198_2",
                "candidate_role": "CORPUS_CONTROL",
                "rationale": "Discusses sliding window buffer management, but contains zero Cisco 2025 CVE vulnerability data."
            },
            {
                "passage_id": "papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_006",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Discusses zero-shot anomaly detection, not commercial switch firmware CVEs."
            }
        ]
    },
    # 12. DBMS Two-Hop
    {
        "query_id": "Q-S5A-12",
        "domain": "Database Management Systems",
        "category": "TWO_HOP",
        "query_text": "How does Third Normal Form (3NF) eliminate transitive dependencies in relational database schemas?",
        "candidates": [
            {
                "passage_id": "pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001",
                "candidate_role": "PREMISE_HOP_1",
                "rationale": "Provides formal definition of 3NF: for every X -> A, either X is a superkey or A is prime attribute."
            },
            {
                "passage_id": "doc_fundamentals_of_database_system_7e::doc_fundamentals_of_database_system_7e_p145_1",
                "candidate_role": "PREMISE_HOP_2",
                "rationale": "Defines relational data model tuples, attributes, and relational database constraints."
            },
            {
                "passage_id": "papers/willard2023_outlines.pdf::chunk_005",
                "candidate_role": "HARD_NEGATIVE",
                "rationale": "Discusses finite automata and context-free grammars, unrelated to relational normalization."
            }
        ]
    }
]


def run():
    print("Loading s5a_eval_corpus_v1 from okf_graph.db...")
    passages, _ = build_fixed_corpus_from_kuzu(str(DB_PATH))
    eligible_passages = [
        p for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
    ]
    passage_by_id = {p.passage_id: p for p in eligible_passages}
    print(f"Eligible corpus: {len(passage_by_id)} passages.")

    candidate_rows = []
    manifest_queries = []
    total_candidates = 0

    for q in QUERY_SPECS:
        qid = q["query_id"]
        domain = q["domain"]
        cat = q["category"]
        qtext = q["query_text"]

        q_manifest_candidates = []

        for c in q["candidates"]:
            pid = c["passage_id"]
            if pid not in passage_by_id:
                raise ValueError(f"Mechanical verification failed: passage {pid} not found in s5a_eval_corpus_v1!")

            p = passage_by_id[pid]
            role = c["candidate_role"]
            rationale = c["rationale"]
            p_sha = p.content_sha256
            total_candidates += 1

            candidate_rows.append({
                "query_id": qid,
                "domain": domain,
                "category": cat,
                "query_text": qtext,
                "candidate_passage_id": pid,
                "candidate_doc_id": p.doc_id,
                "candidate_chunk_id": p.chunk_id,
                "candidate_page_number": p.page_number,
                "candidate_role": role,
                "passage_sha256": p_sha,
                # Human fields strictly empty
                "human_relevance_grade": "",
                "human_evidence_quote": "",
                "human_confidence": "",
                "human_notes": "",
            })

            q_manifest_candidates.append({
                "passage_id": pid,
                "doc_id": p.doc_id,
                "chunk_id": p.chunk_id,
                "page_number": p.page_number,
                "candidate_role": role,
                "passage_sha256": p_sha,
                "admin_rationale": rationale,
            })

        manifest_queries.append({
            "query_id": qid,
            "domain": domain,
            "category": cat,
            "query_text": qtext,
            "candidate_count": len(q["candidates"]),
            "candidates": q_manifest_candidates,
        })

    # Save Candidate Pool CSV
    csv_path = PKG_DIR / "retrieval_query_candidate_pool.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "query_id", "domain", "category", "query_text",
            "candidate_passage_id", "candidate_doc_id", "candidate_chunk_id",
            "candidate_page_number", "candidate_role", "passage_sha256",
            "human_relevance_grade", "human_evidence_quote", "human_confidence", "human_notes"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidate_rows)

    # Save Admin Manifest JSON
    manifest_path = PKG_DIR / "retrieval_query_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "s5a_retrieval_query_suite_v1.0",
            "queries_count": len(manifest_queries),
            "total_candidate_pairs": total_candidates,
            "domains": sorted(list(set(q["domain"] for q in manifest_queries))),
            "category_distribution": {
                cat: sum(1 for q in manifest_queries if q["category"] == cat)
                for cat in ["SINGLE_HOP_CONTROL", "TWO_HOP", "CROSS_DOCUMENT", "UNANSWERABLE"]
            },
            "queries": manifest_queries,
        }, f, indent=2)

    # Save Local Reviewer Markdown Workbook
    wb_path = LOCAL_PKG_DIR / "retrieval_relevance_reviewer_workbook.md"
    with open(wb_path, "w", encoding="utf-8") as f:
        f.write("# Archipelago S5-A Human Retrieval Relevance Reviewer Workbook\n\n")
        f.write("> **INSTRUCTIONS FOR INDEPENDENT ANNOTATORS**\n")
        f.write("> Assign a discrete integer grade for each passage:\n")
        f.write("> - `0` = Irrelevant / Distractor\n")
        f.write("> - `1` = Topic-Relevant / Partial Background\n")
        f.write("> - `2` = Highly Relevant / Key Grounding Premise\n\n---\n\n")

        for q in manifest_queries:
            f.write(f"## Query {q['query_id']} [{q['domain']}] ({q['category']})\n\n")
            f.write(f"**Query:** *\"{q['query_text']}\"*\n\n")
            for c in q["candidates"]:
                pid = c["passage_id"]
                p = passage_by_id[pid]
                f.write(f"### Candidate Passage `{pid}` (Page {p.page_number})\n\n")
                f.write(f"> {p.text}\n\n")
                f.write("**Reviewer Evaluation:**\n")
                f.write("- **Relevance Grade:** `[ ] 0   [ ] 1   [ ] 2`\n")
                f.write("- **Supporting Quote:** \n")
                f.write("- **Confidence:** `HIGH | MEDIUM | LOW`\n")
                f.write("- **Notes:** \n\n")
            f.write("---\n\n")

    print(f"Generated {len(manifest_queries)} queries with {total_candidates} candidate passages.")
    print(f"CSV saved to: {csv_path}")
    print(f"Manifest saved to: {manifest_path}")
    print(f"Workbook saved to: {wb_path}")


if __name__ == "__main__":
    run()

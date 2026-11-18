"""S5-B2 — Proposed Corrected Blinded Annotation Package Builder.

Generates the separately versioned `s5b2_proposed_v2.0_pending_approval` reviewer package:
- Preserves the frozen S5-B1.1 pilot (`research/s5-b1-integrity-repair/`) untouched.
- Uses deterministic PRNG shuffling (seed = 20261119) from lexicographically sorted passage IDs.
- Excludes held queries (Q-S5A-09, Q-S5A-12) pending investigator decision.
- Strips ALL category, answerability, role, and rationale metadata from reviewer-facing outputs.
- Emits separate Reviewer A and Reviewer B workbooks in Git-ignored `data/annotation_local/s5b2/`
  containing verified passage text from `okf_graph.db`, neutral pair IDs, and empty judgment fields.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu, _is_index_only_passage

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "okf_graph.db"
BASE_DIR = ROOT / "research" / "s5-b2-benchmark-correction"
SPECS_PATH = BASE_DIR / "corpus" / "s5b2_proposed_blinded_query_specs.json"
PKG_DIR = BASE_DIR / "proposed_package"
LOCAL_DIR = ROOT / "data" / "annotation_local" / "s5b2"

RANDOM_SEED = 20261119


def _write_workbook(
    path: Path,
    reviewer_id: str,
    reviewer_label: str,
    queries: list[dict[str, Any]],
    passage_by_id: dict[str, Any],
) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Archipelago S5-B2 Proposed Human Retrieval Relevance Workbook — {reviewer_label}\n\n")
        f.write(f"- **Package Version:** `s5b2_proposed_v2.0_pending_approval`\n")
        f.write(f"- **Reviewer ID:** `{reviewer_id}`\n")
        f.write(f"- **Candidate Ordering Seed:** `{RANDOM_SEED}` (Deterministic PRNG shuffle)\n")
        f.write("- **Blinding Status:** Strictly blinded (zero categories, roles, or system predictions)\n\n")
        f.write("> **INSTRUCTIONS FOR INDEPENDENT ANNOTATOR**\n")
        f.write("> Evaluate each candidate passage independently against the query text using the 3-point scale:\n")
        f.write("> - `0` = Irrelevant / Distractor\n")
        f.write("> - `1` = Partially Relevant / Background Context\n")
        f.write("> - `2` = Highly Relevant / Grounding Premise\n")
        f.write("> \n")
        f.write("> Copy a verbatim supporting quote from the passage for grade `1` or `2` (leave blank for `0`).\n\n---\n\n")

        for q in queries:
            f.write(f"## Query {q['query_id']} [{q['domain']}]\n\n")
            f.write(f"**Query:** *\"{q['query_text']}\"*\n\n")
            for c in q["candidates"]:
                p = passage_by_id[c["candidate_passage_id"]]
                f.write(f"### Candidate Pair `{c['pair_id']}`\n\n")
                f.write(f"- **Candidate Passage ID:** `{p.passage_id}`\n")
                f.write(f"- **Document ID:** `{p.doc_id}`\n")
                f.write(f"- **Chunk ID:** `{p.chunk_id}`\n")
                f.write(f"- **Page Number:** `{p.page_number}`\n")
                f.write(f"- **Passage SHA-256:** `{p.content_sha256}`\n\n")
                f.write("**Verified Source Passage Text:**\n\n")
                f.write(f"> {p.text}\n\n")
                f.write(f"**{reviewer_label} Judgment Fields:**\n")
                f.write(f"- **reviewer_id:** `{reviewer_id}`\n")
                f.write("- **human_relevance_grade (0 | 1 | 2):** \n")
                f.write("- **human_evidence_quote:** \n")
                f.write("- **human_confidence (HIGH | MEDIUM | LOW):** \n")
                f.write("- **human_notes:** \n\n")
            f.write("---\n\n")


def run() -> None:
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    passages, _ = build_fixed_corpus_from_kuzu(str(DB_PATH))
    eligible = [
        p for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
    ]
    passage_by_id = {p.passage_id: p for p in eligible}

    with open(SPECS_PATH, encoding="utf-8") as f:
        specs = json.load(f)

    rng = random.Random(RANDOM_SEED)
    csv_rows: list[dict[str, Any]] = []
    json_queries: list[dict[str, Any]] = []
    pair_counter = 0

    for q in specs["queries"]:
        qid = q["query_id"]
        domain = q["domain"]
        qtext = q["query_text"]

        sorted_pids = sorted(q["candidate_passage_ids"])
        shuffled_pids = list(sorted_pids)
        rng.shuffle(shuffled_pids)

        q_cands = []
        for rank_idx, pid in enumerate(shuffled_pids, start=1):
            pair_counter += 1
            pair_id = f"S5B2-PAIR-{pair_counter:03d}"
            if pid not in passage_by_id:
                raise ValueError(f"Passage {pid} not found in frozen 713-passage corpus")
            p = passage_by_id[pid]

            csv_rows.append({
                "pair_id": pair_id,
                "query_id": qid,
                "domain": domain,
                "query_text": qtext,
                "candidate_passage_id": pid,
                "candidate_doc_id": p.doc_id,
                "candidate_chunk_id": p.chunk_id,
                "candidate_page_number": p.page_number,
                "passage_sha256": p.content_sha256,
                "human_relevance_grade": "",
                "human_evidence_quote": "",
                "human_confidence": "",
                "human_notes": "",
            })

            q_cands.append({
                "pair_id": pair_id,
                "presentation_order": rank_idx,
                "candidate_passage_id": pid,
                "candidate_doc_id": p.doc_id,
                "candidate_chunk_id": p.chunk_id,
                "candidate_page_number": p.page_number,
                "passage_sha256": p.content_sha256,
            })

        json_queries.append({
            "query_id": qid,
            "domain": domain,
            "query_text": qtext,
            "candidate_count": len(q_cands),
            "candidates": q_cands,
        })

    csv_path = PKG_DIR / "retrieval_query_candidate_pool_blinded.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "pair_id", "query_id", "domain", "query_text",
            "candidate_passage_id", "candidate_doc_id", "candidate_chunk_id",
            "candidate_page_number", "passage_sha256",
            "human_relevance_grade", "human_evidence_quote", "human_confidence", "human_notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    json_path = PKG_DIR / "retrieval_query_pool_blinded.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "s5b2_proposed_v2.0_pending_approval",
            "status": "PROPOSED_PENDING_INVESTIGATOR_APPROVAL",
            "randomization_seed": RANDOM_SEED,
            "candidate_ordering_policy": "deterministic_prng_shuffle_from_lexicographical",
            "queries_count": len(json_queries),
            "total_candidate_pairs": pair_counter,
            "domains": sorted(list(set(q["domain"] for q in json_queries))),
            "queries": json_queries,
        }, f, indent=2)

    protocol_path = PKG_DIR / "RETRIEVAL_ANNOTATION_PROTOCOL.md"
    with open(protocol_path, "w", encoding="utf-8") as f:
        f.write("# Archipelago S5-B2 Proposed Human Retrieval Relevance Annotation Protocol\n\n")
        f.write("**Status:** `PROPOSED_PENDING_INVESTIGATOR_APPROVAL` (Do not distribute until approved)\n\n")
        f.write("## 1. Objective\n\n")
        f.write("Independently evaluate candidate passage relevance for 10 active academic queries across computer science domains.\n")
        f.write("Reviewers receive only query text, domain labels, neutral pair identifiers (`S5B2-PAIR-001`..`S5B2-PAIR-025`),\n")
        f.write("and source-verified passages.\n\n")
        f.write("## 2. Discrete Grading Scale (0, 1, 2)\n\n")
        f.write("| Grade | Label | Operational Definition |\n")
        f.write("|---|---|---|\n")
        f.write("| **0** | Irrelevant / Distractor | The passage does not provide evidence answering the query, or addresses an unrelated topic. |\n")
        f.write("| **1** | Partially Relevant / Context | The passage discusses related terminology or background context, but is insufficient on its own to ground the answer. |\n")
        f.write("| **2** | Highly Relevant / Grounding Evidence | The passage directly answers the query or supplies an essential factual premise required to answer the query. |\n\n")
        f.write("## 3. Independent Dual-Reviewer Procedure\n\n")
        f.write("- **Reviewer A** (`reviewer_a_s5b2_workbook.md`) and **Reviewer B** (`reviewer_b_s5b2_workbook.md`) grade independently.\n")
        f.write(f"- Candidate ordering within each query is randomized using deterministic seed `{RANDOM_SEED}`.\n")
        f.write("- Unjudged passages from system top-k outputs are NOT assumed irrelevant.\n")

    wb_a = LOCAL_DIR / "reviewer_a_s5b2_workbook.md"
    wb_b = LOCAL_DIR / "reviewer_b_s5b2_workbook.md"
    _write_workbook(wb_a, "REV_A", "Reviewer A", json_queries, passage_by_id)
    _write_workbook(wb_b, "REV_B", "Reviewer B", json_queries, passage_by_id)

    print(f"Generated proposed S5-B2 package: {len(json_queries)} queries, {pair_counter} pairs (seed={RANDOM_SEED}).")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    print(f"Workbooks: {wb_a} & {wb_b}")


if __name__ == "__main__":
    run()

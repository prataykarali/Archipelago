"""S5-B1.1 — Final Blinded Human Retrieval Evaluation Package Builder.

Guarantees:
1. Zero category or answerability hints in reviewer-facing CSV, JSON, protocol, or workbooks.
2. Deterministic PRNG randomization (seed = 20261118) of candidate ordering within each query
   from a neutral lexicographically sorted passage list.
3. Strict separation of administrator-only manifest into Git-ignored local storage
   (`annotation_local/admin_retrieval_manifest.json` and `data/annotation_local/s5b1_admin/`).
   Zero role or rationale strings in any Git-tracked script or artifact.
4. Separate Reviewer A and Reviewer B local workbooks containing actual verified passage text
   from `okf_graph.db`, neutral pair IDs (`PAIR-001`..`PAIR-031`), and empty judgment fields.
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
BASE_DIR = ROOT / "research" / "s5-b1-integrity-repair"
BLINDED_SPECS_PATH = BASE_DIR / "corpus" / "s5b1_blinded_query_specs.json"
PKG_DIR = BASE_DIR / "human_evaluation_package"
LOCAL_DIR = BASE_DIR / "annotation_local"
DATA_ADMIN_DIR = ROOT / "data" / "annotation_local" / "s5b1_admin"

RANDOM_SEED = 20261118


def _write_reviewer_workbook(
    path: Path,
    reviewer_id: str,
    reviewer_label: str,
    blinded_queries: list[dict[str, Any]],
    passage_by_id: dict[str, Any],
) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Archipelago S5-B1.1 Human Retrieval Relevance Workbook — {reviewer_label}\n\n")
        f.write(f"- **Reviewer ID:** `{reviewer_id}`\n")
        f.write(f"- **Candidate Ordering Seed:** `{RANDOM_SEED}` (Deterministic PRNG shuffle)\n")
        f.write("- **Blinding Status:** Strictly blinded (no system predictions, roles, or query categories)\n\n")
        f.write("> **INSTRUCTIONS FOR INDEPENDENT ANNOTATOR**\n")
        f.write("> Evaluate each candidate passage independently against the query text using the 3-point scale:\n")
        f.write("> - `0` = Irrelevant / Distractor (does not support answering the query)\n")
        f.write("> - `1` = Partially Relevant / Background Context (topically related but insufficient premise)\n")
        f.write("> - `2` = Highly Relevant / Grounding Premise (directly answers or provides an essential premise)\n")
        f.write("> \n")
        f.write("> If you assign grade `1` or `2`, copy a verbatim supporting quote from the passage.\n")
        f.write("> Leave the quote blank if you assign grade `0`.\n\n---\n\n")

        for q in blinded_queries:
            f.write(f"## Query {q['query_id']} [{q['domain']}]\n\n")
            f.write(f"**Query:** *\"{q['query_text']}\"*\n\n")
            for c in q["candidates"]:
                pair_id = c["pair_id"]
                pid = c["candidate_passage_id"]
                p = passage_by_id[pid]
                f.write(f"### Candidate Pair `{pair_id}`\n\n")
                f.write(f"- **Candidate Passage ID:** `{pid}`\n")
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
    print("=" * 75)
    print("S5-B1.1 — Final Blinded Human Retrieval Evaluation Package Builder")
    print("=" * 75)

    PKG_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    DATA_ADMIN_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load frozen eligible corpus
    passages, _ = build_fixed_corpus_from_kuzu(str(DB_PATH))
    eligible_passages = [
        p for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
    ]
    passage_by_id = {p.passage_id: p for p in eligible_passages}
    print(f"Loaded {len(eligible_passages)} eligible passages from okf_graph.db")

    # 2. Load blinded query specs
    with open(BLINDED_SPECS_PATH, encoding="utf-8") as f:
        blinded_specs_doc = json.load(f)
    blinded_specs = blinded_specs_doc["queries"]

    # Optional: load local gitignored admin specs if available on this machine
    local_admin_specs_path = LOCAL_DIR / "admin_query_specs_local.json"
    if not local_admin_specs_path.exists():
        local_admin_specs_path = DATA_ADMIN_DIR / "admin_query_specs_local.json"

    admin_lookup: dict[tuple[str, str], dict[str, str]] = {}
    admin_query_meta: dict[str, dict[str, str]] = {}
    if local_admin_specs_path.exists():
        with open(local_admin_specs_path, encoding="utf-8") as f:
            raw_admin = json.load(f)
        for aq in raw_admin["queries"]:
            qid = aq["query_id"]
            admin_query_meta[qid] = {k: v for k, v in aq.items() if k != "candidates"}
            for ac in aq["candidates"]:
                admin_lookup[(qid, ac["passage_id"])] = ac

    # 3. Deterministic PRNG shuffle of candidates within each query
    rng = random.Random(RANDOM_SEED)

    blinded_csv_rows: list[dict[str, Any]] = []
    blinded_json_queries: list[dict[str, Any]] = []
    admin_manifest_pairs: list[dict[str, Any]] = []
    pair_counter = 0

    for q in blinded_specs:
        qid = q["query_id"]
        domain = q["domain"]
        qtext = q["query_text"]

        # Sort lexicographically first to guarantee canonical starting order, then shuffle deterministically
        sorted_pids = sorted(q["candidate_passage_ids"])
        shuffled_pids = list(sorted_pids)
        rng.shuffle(shuffled_pids)

        q_blinded_candidates = []

        for rank_idx, pid in enumerate(shuffled_pids, start=1):
            pair_counter += 1
            pair_id = f"PAIR-{pair_counter:03d}"

            if pid not in passage_by_id:
                raise ValueError(f"Mechanical verification failed: passage {pid} not found in s5a_eval_corpus_v1!")

            p = passage_by_id[pid]
            p_sha = p.content_sha256

            # 1. Blinded CSV Row (ZERO category, role, or rationale columns)
            blinded_csv_rows.append({
                "pair_id": pair_id,
                "query_id": qid,
                "domain": domain,
                "query_text": qtext,
                "candidate_passage_id": pid,
                "candidate_doc_id": p.doc_id,
                "candidate_chunk_id": p.chunk_id,
                "candidate_page_number": p.page_number,
                "passage_sha256": p_sha,
                "human_relevance_grade": "",
                "human_evidence_quote": "",
                "human_confidence": "",
                "human_notes": "",
            })

            # 2. Blinded JSON Entry (ZERO category, role, or rationale fields)
            q_blinded_candidates.append({
                "pair_id": pair_id,
                "presentation_order": rank_idx,
                "candidate_passage_id": pid,
                "candidate_doc_id": p.doc_id,
                "candidate_chunk_id": p.chunk_id,
                "candidate_page_number": p.page_number,
                "passage_sha256": p_sha,
            })

            # 3. Local-only Admin Manifest Entry (if local admin specs present)
            if (qid, pid) in admin_lookup:
                ac = admin_lookup[(qid, pid)]
                q_meta = admin_query_meta.get(qid, {})
                admin_Entry = {
                    "pair_id": pair_id,
                    "presentation_order": rank_idx,
                    "query_id": qid,
                    "domain": domain,
                    "query_text": qtext,
                    "candidate_passage_id": pid,
                    "candidate_doc_id": p.doc_id,
                    "candidate_chunk_id": p.chunk_id,
                    "candidate_page_number": p.page_number,
                    "passage_sha256": p_sha,
                }
                for k, v in q_meta.items():
                    if k not in admin_Entry:
                        admin_Entry[k] = v
                for k, v in ac.items():
                    if k != "passage_id":
                        admin_Entry[k] = v
                admin_manifest_pairs.append(admin_Entry)

        blinded_json_queries.append({
            "query_id": qid,
            "domain": domain,
            "query_text": qtext,
            "candidate_count": len(q_blinded_candidates),
            "candidates": q_blinded_candidates,
        })

    # Save 1: Blinded Candidate Pool CSV
    blinded_csv_path = PKG_DIR / "retrieval_query_candidate_pool_blinded.csv"
    with open(blinded_csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "pair_id", "query_id", "domain", "query_text",
            "candidate_passage_id", "candidate_doc_id", "candidate_chunk_id",
            "candidate_page_number", "passage_sha256",
            "human_relevance_grade", "human_evidence_quote", "human_confidence", "human_notes"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(blinded_csv_rows)

    # Save 2: Blinded JSON Query Pool (NO category or category_distribution)
    blinded_json_path = PKG_DIR / "retrieval_query_pool_blinded.json"
    with open(blinded_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "s5b1_1_blinded_query_pool_v1.0",
            "randomization_seed": RANDOM_SEED,
            "candidate_ordering_policy": "deterministic_prng_shuffle_from_lexicographical",
            "queries_count": len(blinded_json_queries),
            "total_candidate_pairs": pair_counter,
            "domains": sorted(list(set(q["domain"] for q in blinded_json_queries))),
            "queries": blinded_json_queries,
        }, f, indent=2)

    # Save 3: Blinded Annotation Protocol (NO category labels or internal role terms)
    protocol_path = PKG_DIR / "RETRIEVAL_ANNOTATION_PROTOCOL.md"
    with open(protocol_path, "w", encoding="utf-8") as f:
        f.write("# Archipelago S5-B1.1 Human Retrieval Relevance Annotation Protocol\n\n")
        f.write("## 1. Objective\n\n")
        f.write("Independently evaluate candidate passage relevance for 12 academic queries across computer science domains.\n")
        f.write("This protocol enforces strict double-blind evaluation: reviewers receive only query text, domain labels,\n")
        f.write("neutral candidate pair identifiers (`PAIR-001` through `PAIR-031`), and source-verified passages.\n\n")
        f.write("## 2. Discrete Grading Scale (0, 1, 2)\n\n")
        f.write("| Grade | Label | Operational Definition |\n")
        f.write("|---|---|---|\n")
        f.write("| **0** | Irrelevant / Distractor | The passage does not provide evidence answering the query, or addresses an unrelated topic. |\n")
        f.write("| **1** | Partially Relevant / Context | The passage discusses related terminology or background context, but is insufficient on its own to ground the answer. |\n")
        f.write("| **2** | Highly Relevant / Grounding Evidence | The passage directly answers the query or supplies an essential factual premise required to answer the query. |\n\n")
        f.write("## 3. Required Reviewer Judgment Fields\n\n")
        f.write("- `human_relevance_grade`: Discrete integer (`0`, `1`, or `2`).\n")
        f.write("- `human_evidence_quote`: Verbatim substring from the passage supporting grade `1` or `2` (leave blank for grade `0`).\n")
        f.write("- `human_confidence`: `HIGH`, `MEDIUM`, or `LOW`.\n")
        f.write("- `human_notes`: Optional free-text observation.\n\n")
        f.write("## 4. Independent Dual-Reviewer Procedure\n\n")
        f.write("- **Reviewer A** (`reviewer_a_retrieval_workbook.md`) and **Reviewer B** (`reviewer_b_retrieval_workbook.md`) complete judgments independently.\n")
        f.write("- Candidate ordering within each query has been randomized using deterministic seed `20261118`.\n")
        f.write("- Inter-annotator agreement is measured after both workbooks are locked using Cohen's Weighted Kappa.\n")

    # Save 4: Separate Reviewer A and Reviewer B Local Workbooks (Git-ignored)
    wb_a_path = LOCAL_DIR / "reviewer_a_retrieval_workbook.md"
    wb_b_path = LOCAL_DIR / "reviewer_b_retrieval_workbook.md"
    _write_reviewer_workbook(wb_a_path, "REV_A", "Reviewer A", blinded_json_queries, passage_by_id)
    _write_reviewer_workbook(wb_b_path, "REV_B", "Reviewer B", blinded_json_queries, passage_by_id)

    # Save 5: Local Git-ignored Admin Manifest (only when local admin specs exist)
    if admin_manifest_pairs:
        admin_doc = {
            "version": "s5b1_1_admin_manifest_v1.0",
            "date": "2026-11-18",
            "storage_policy": "LOCAL_GITIGNORED_ONLY",
            "randomization_seed": RANDOM_SEED,
            "queries_count": len(blinded_specs),
            "total_candidate_pairs": pair_counter,
            "candidate_pairs": admin_manifest_pairs,
        }
        for admin_path in [
            LOCAL_DIR / "admin_retrieval_manifest.json",
            DATA_ADMIN_DIR / "admin_retrieval_manifest.json",
        ]:
            with open(admin_path, "w", encoding="utf-8") as f:
                json.dump(admin_doc, f, indent=2)
        print(f"Local admin manifest saved to gitignored: {LOCAL_DIR / 'admin_retrieval_manifest.json'}")

    print(f"Generated {len(blinded_specs)} queries with {pair_counter} randomized candidate pairs (seed={RANDOM_SEED}).")
    print(f"Blinded CSV saved to: {blinded_csv_path}")
    print(f"Blinded JSON saved to: {blinded_json_path}")
    print(f"Protocol saved to: {protocol_path}")
    print(f"Reviewer A Workbook saved to: {wb_a_path}")
    print(f"Reviewer B Workbook saved to: {wb_b_path}")


if __name__ == "__main__":
    run()

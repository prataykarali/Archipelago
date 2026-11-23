"""Build system-blinded pooled top-k human relevance worksheets for Archipelago D5.

Pools the top-K candidates from all four frozen TREC run files in
`research/d5_sigir_evaluation/ranked_runs/`:
  - bm25.run
  - snowflake_arctic_neural.run
  - feature_hashed_vector.run
  - archipelago_graph_assisted.run

Outputs:
  1. `research/d5_sigir_evaluation/human_annotation_worksheet.json`
     Full blinded pool with passage text and strictly null reviewer fields.
  2. `research/d5_sigir_evaluation/worksheets/reviewer_A_worksheet.csv`
  3. `research/d5_sigir_evaluation/worksheets/reviewer_B_worksheet.csv`
     Ready-to-use spreadsheets for two independent human annotators (100% overlap
     or configurable subset), with all human grade columns blank.
  4. `research/d5_sigir_evaluation/worksheets/adjudication_worksheet.csv`
     Blank adjudication sheet for resolving disagreements between Reviewer A & B.
  5. `research/d5_sigir_evaluation/worksheets/pool_key_SEALED.json`
     Sealed mapping from blinded_candidate_id to contributing systems and ranks.
     MUST NOT be shared with human annotators during judging.

ACM SIGIR Demonstrations Track — Scientific Evaluation Integrity
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
D5_DIR = REPO_ROOT / "research" / "d5_sigir_evaluation"
HOST_GRAPH_PATH = REPO_ROOT / "host_inference" / "fixtures" / "okf_graph.json"
RUNS_DIR = D5_DIR / "ranked_runs"
WORKSHEETS_DIR = D5_DIR / "worksheets"

POOL_DEPTH_K = 5
MIN_PASSAGE_CHARS = 40
BLIND_ID_HEX_LEN = 12
BLIND_SALT = "archipelago-sigir2027-d5-system-blinded-pool-v1"

POOLED_SYSTEMS: tuple[str, ...] = (
    "bm25",
    "snowflake_arctic_neural",
    "feature_hashed_vector",
    "archipelago_graph_assisted",
)

REVIEWER_CSV_FIELDS: tuple[str, ...] = (
    "item_id",
    "query_id",
    "query_text",
    "blinded_candidate_id",
    "canonical_source_doc",
    "canonical_page_number",
    "section_title",
    "passage_text",
    "relevance_grade",
    "claim_supported",
    "reviewer_id",
    "review_date",
    "confidence",
    "notes",
)

ADJUDICATION_CSV_FIELDS: tuple[str, ...] = (
    "item_id",
    "query_id",
    "query_text",
    "blinded_candidate_id",
    "reviewer_A_grade",
    "reviewer_B_grade",
    "adjudicated_relevance_grade",
    "adjudicated_claim_supported",
    "adjudicator_id",
    "adjudication_date",
    "adjudication_rationale",
)


def load_corpus_index(graph_path: Path = HOST_GRAPH_PATH) -> dict[str, dict[str, Any]]:
    """Load the 775 deduplicated corpus passages indexed by canonical passage_id."""
    raw = json.loads(graph_path.read_bytes())
    index: dict[str, dict[str, Any]] = {}
    for _cid, node in raw.get("concepts", {}).items():
        for src in node.get("sources", []):
            text = (src.get("text_passage") or "").strip()
            doc_id = src.get("doc_id") or ""
            page = int(src.get("page_number") or 0)
            chunk_id = src.get("chunk_id") or f"{doc_id}_p{page}"
            if len(text) >= MIN_PASSAGE_CHARS:
                pid = f"{doc_id}::{chunk_id}"
                if pid not in index:
                    index[pid] = {
                        "passage_id": pid,
                        "doc_id": doc_id,
                        "page_number": page,
                        "chunk_id": chunk_id,
                        "section_title": (src.get("section_title") or "").strip(),
                        "text": text,
                    }
    return index


def parse_trec_run(
    run_path: Path, depth: int = POOL_DEPTH_K
) -> dict[str, list[tuple[str, int, float]]]:
    """Parse a TREC run file, preserving passage_ids that contain internal spaces."""
    per_query: dict[str, list[tuple[str, int, float]]] = {}
    for line in run_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        qid = parts[0]
        rank = int(parts[-3])
        score = float(parts[-2])
        pid = " ".join(parts[2:-3])
        entries = per_query.setdefault(qid, [])
        if len(entries) < depth:
            entries.append((pid, rank, score))
    return per_query


def make_blinded_id(query_id: str, passage_id: str) -> str:
    """Create a deterministic, system-agnostic candidate identifier."""
    digest = hashlib.sha256(f"{BLIND_SALT}::{query_id}::{passage_id}".encode()).hexdigest()
    return f"CAND-{digest[:BLIND_ID_HEX_LEN]}"


def build_pool(
    d5_dir: Path = D5_DIR,
    graph_path: Path = HOST_GRAPH_PATH,
    depth: int = POOL_DEPTH_K,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Construct the blinded pooled worksheet dict and the sealed system key dict."""
    corpus = load_corpus_index(graph_path)
    queries: list[dict[str, Any]] = json.loads((d5_dir / "queries_heldout_50.json").read_bytes())

    runs_by_system: dict[str, dict[str, list[tuple[str, int, float]]]] = {}
    for sys_name in POOLED_SYSTEMS:
        run_path = d5_dir / "ranked_runs" / f"{sys_name}.run"
        runs_by_system[sys_name] = parse_trec_run(run_path, depth=depth)

    items: list[dict[str, Any]] = []
    sealed_entries: dict[str, dict[str, Any]] = {}
    item_counter = 0

    for q in queries:
        qid = q["query_id"]
        qtext = q["query"]

        pooled_for_query: dict[str, dict[str, dict[str, Any]]] = {}
        for sys_name in POOLED_SYSTEMS:
            for pid, rank, score in runs_by_system[sys_name].get(qid, []):
                pooled_for_query.setdefault(pid, {})[sys_name] = {
                    "rank": rank,
                    "score": score,
                }

        # Deterministic, system-agnostic ordering by blinded_candidate_id
        ordered_candidates = sorted(
            (
                (make_blinded_id(qid, pid), pid, contribs)
                for pid, contribs in pooled_for_query.items()
            ),
            key=lambda row: row[0],
        )

        for blind_id, pid, contribs in ordered_candidates:
            item_counter += 1
            item_id = f"ANN-{item_counter:04d}"
            pmeta = corpus.get(pid)
            if pmeta is None:
                msg = f"Pooled passage_id not found in corpus: {pid}"
                raise ValueError(msg)

            items.append(
                {
                    "item_id": item_id,
                    "query_id": qid,
                    "query_text": qtext,
                    "passage_id": pid,
                    "blinded_candidate_id": blind_id,
                    "canonical_source_doc": pmeta["doc_id"],
                    "canonical_page_number": pmeta["page_number"],
                    "canonical_chunk_id": pmeta["chunk_id"],
                    "section_title": pmeta["section_title"],
                    "passage_text": pmeta["text"],
                    "passage_char_count": len(pmeta["text"]),
                    "reviewer_assessment": {
                        "relevance_grade": None,
                        "claim_supported": None,
                        "reviewer_id": None,
                        "review_date": None,
                        "confidence": None,
                        "notes": None,
                    },
                }
            )
            sealed_entries[item_id] = {
                "query_id": qid,
                "passage_id": pid,
                "blinded_candidate_id": blind_id,
                "contributing_systems": contribs,
            }

    worksheet: dict[str, Any] = {
        "worksheet_metadata": {
            "title": "Archipelago SIGIR 2027 Pooled Top-5 Human Relevance Worksheet",
            "standard": (
                "TREC-Style System-Blinded Pooled Top-5 Relevance Protocol "
                "(Single-Blinded to Source System & Rank; Independent Dual-Annotator Overlap)"
            ),
            "blinding_definition": (
                "Annotators are blinded to which retrieval system(s) retrieved each candidate "
                "and to retrieval rank/score. Candidates are ordered deterministically by hashed "
                "blinded_candidate_id. Annotators judge independently without seeing each other's "
                "labels. This is system-blinded (single-blinded) IR relevance judging, NOT a "
                "clinical double-blind study."
            ),
            "instructions": (
                "Reviewers must independently assess each (query, passage) pair. Assign "
                "relevance_grade: 0 (not relevant), 1 (marginally relevant / topical), "
                "2 (highly relevant / directly answers or defines query). Assign claim_supported: "
                "FULLY_SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, or IRRELEVANT. Do NOT fill "
                "assessments algorithmically or by LLM/coding agents. All reviewer_assessment "
                "fields must remain null until completed by named human judges."
            ),
            "grading_rubric": {
                "0": "Irrelevant: does not answer or address the query topic.",
                "1": "Topical: related to query domain or mentions key concepts, but incomplete.",
                "2": "Directly Relevant: clear answer, definition, mechanism, or proof for query.",
            },
            "pool_depth_k": depth,
            "total_queries_represented": len({i["query_id"] for i in items}),
            "total_annotation_items": len(items),
            "systems_pooled": list(POOLED_SYSTEMS),
            "status": "PENDING_HUMAN_ANNOTATION",
            "human_judgments_completed": 0,
        },
        "items": items,
    }

    sealed_key: dict[str, Any] = {
        "warning": "SEALED POOL KEY — DO NOT SHARE WITH HUMAN ANNOTATORS DURING JUDGING.",
        "pool_depth_k": depth,
        "systems_pooled": list(POOLED_SYSTEMS),
        "total_items": len(items),
        "entries": sealed_entries,
    }
    return worksheet, sealed_key


def write_outputs(
    worksheet: dict[str, Any], sealed_key: dict[str, Any], d5_dir: Path = D5_DIR
) -> None:
    """Persist JSON worksheet, reviewer CSVs, adjudication template, and sealed key."""
    ws_path = d5_dir / "human_annotation_worksheet.json"
    ws_path.write_text(json.dumps(worksheet, indent=2) + "\n", encoding="utf-8")

    out_dir = d5_dir / "worksheets"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "pool_key_SEALED.json").write_text(
        json.dumps(sealed_key, indent=2) + "\n", encoding="utf-8"
    )

    items: list[dict[str, Any]] = worksheet["items"]
    for reviewer_label in ("reviewer_A_worksheet.csv", "reviewer_B_worksheet.csv"):
        csv_path = out_dir / reviewer_label
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=REVIEWER_CSV_FIELDS)
            writer.writeheader()
            for item in items:
                writer.writerow(
                    {
                        "item_id": item["item_id"],
                        "query_id": item["query_id"],
                        "query_text": item["query_text"],
                        "blinded_candidate_id": item["blinded_candidate_id"],
                        "canonical_source_doc": item["canonical_source_doc"],
                        "canonical_page_number": item["canonical_page_number"],
                        "section_title": item["section_title"],
                        "passage_text": item["passage_text"],
                        "relevance_grade": "",
                        "claim_supported": "",
                        "reviewer_id": "",
                        "review_date": "",
                        "confidence": "",
                        "notes": "",
                    }
                )

    adj_path = out_dir / "adjudication_worksheet.csv"
    with adj_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ADJUDICATION_CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "item_id": item["item_id"],
                    "query_id": item["query_id"],
                    "query_text": item["query_text"],
                    "blinded_candidate_id": item["blinded_candidate_id"],
                    "reviewer_A_grade": "",
                    "reviewer_B_grade": "",
                    "adjudicated_relevance_grade": "",
                    "adjudicated_claim_supported": "",
                    "adjudicator_id": "",
                    "adjudication_date": "",
                    "adjudication_rationale": "",
                }
            )


def main() -> None:
    """Build and write the system-blinded pooled top-5 worksheets."""
    worksheet, sealed_key = build_pool()
    write_outputs(worksheet, sealed_key)
    meta = worksheet["worksheet_metadata"]
    print(
        f"Built system-blinded top-{meta['pool_depth_k']} pool: "
        f"{meta['total_annotation_items']} items across {meta['total_queries_represented']} queries "
        f"from {len(meta['systems_pooled'])} systems."
    )


if __name__ == "__main__":
    main()

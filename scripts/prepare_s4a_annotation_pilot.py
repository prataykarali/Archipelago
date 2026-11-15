#!/usr/bin/env python3
"""Prepare the S4-A Human-Gold Annotation Pilot (6 queries).

Generates:
- Shareable metadata-only source verification report & dual-reviewer blank templates
- Local-only (gitignored) human-reviewable annotation worksheet containing blinded
  candidate passages from BM25, Dense, Hybrid RRF, and randomly sampled controls.

Never auto-fills human annotations or marks candidates as ADJUDICATED_GOLD.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archipelago.eval.annotation_pilot import (
    PILOT_SELECTED_QUERY_IDS,
    build_blinded_annotation_pool,
    create_reviewer_records,
    verify_sources_and_quotes,
)
from archipelago.eval.dataset_integrity import normalize_doc_id
from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu


def _load_kuzu_doc_provenance(db_path: Path) -> dict[str, dict[str, Any]]:
    import kuzu

    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    res = conn.execute("MATCH (d:Document) RETURN d.id, d.doc_hash, d.pdf_url, d.page_count")
    prov: dict[str, dict[str, Any]] = {}
    while res.has_next():
        doc_id_raw, doc_hash, pdf_url, page_count = res.get_next()
        canon = normalize_doc_id(str(doc_id_raw or ""))
        if canon:
            prov[canon] = {
                "doc_hash": doc_hash,
                "pdf_url": pdf_url,
                "page_count": page_count,
            }
    return prov


def _load_selected_queries(jsonl_path: Path) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["query_id"] in PILOT_SELECTED_QUERY_IDS:
                by_id[row["query_id"]] = row
    return [by_id[qid] for qid in PILOT_SELECTED_QUERY_IDS if qid in by_id]


def _load_s3_candidates(export_json_path: Path) -> dict[str, list[str]]:
    data = json.loads(export_json_path.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for q_entry in data.get("candidates", []):
        qid = q_entry["query_id"]
        if qid not in PILOT_SELECTED_QUERY_IDS:
            continue
        pids: list[str] = []
        rankings = q_entry.get("rankings", {})
        for sys_name in ("bm25", "dense", "hybrid_rrf"):
            for hit in rankings.get(sys_name, []):
                pids.append(hit["passage_id"])
        out[qid] = pids
    return out


def _render_markdown_worksheet(
    queries: list[dict[str, Any]],
    blinded_pools: dict[str, list[dict[str, Any]]],
    verification_by_qid: dict[str, dict[str, Any]],
) -> str:
    lines: list[str] = [
        "# Archipelago CIKM 2027 — S4-A Human Annotation Pilot Worksheet (LOCAL ONLY)",
        "",
        "**Instructions for Independent Reviewers (Reviewer A & Reviewer B):**",
        "- Retrieval system identities (`bm25`, `dense`, `hybrid_rrf`) and ranks are hidden.",
        "- Each pool mixes retrieved candidates and randomly sampled corpus passages.",
        "- **Do NOT assume passages outside this pool are irrelevant.** Verify against the original PDF.",
        "- Score each passage `0` (not relevant), `1` (partially relevant / context), or `2` (directly answers / supports).",
        "- For each query, record answerability, quote/page accuracy, prerequisite dependency validity, and multi-passage requirement.",
        "",
    ]
    for q in queries:
        qid = q["query_id"]
        v = verification_by_qid[qid]
        lines.extend(
            [
                f"---",
                f"## {qid} (`{q['question_category']}`)",
                f"**Question:** {q['question']}",
                f"**Source Doc IDs:** {', '.join(q.get('source_doc_ids') or ['(none — out of corpus)'])}",
                f"**Requires Manual Verification:** `{v['requires_manual_verification']}` ({', '.join(v['discrepancies']) or 'none'})",
                "",
                "### Blinded Candidate Passages",
                "",
            ]
        )
        for item in blinded_pools[qid]:
            lines.extend(
                [
                    f"#### {item['pool_item_id']} — `{item['doc_id']}` (chunk `{item['chunk_id']}`, page `{item['page_number']}`)",
                    f"- Passage ID: `{item['passage_id']}`",
                    f"- Section: `{item['section_title'] or 'N/A'}`",
                    f"- Relevance (`0 / 1 / 2`): `___`",
                    "",
                    f"> {item['text']}",
                    "",
                ]
            )
    return "\n".join(lines)


def main() -> int:
    db_path = ROOT / "okf_graph.db"
    queries_path = ROOT / "artifacts" / "validation" / "cikm_qa_pilot_candidates.jsonl"
    s3_export_path = ROOT / "artifacts" / "validation" / "s3_retrieval_candidates_export.json"

    passages, _manifest = build_fixed_corpus_from_kuzu(db_path)
    passage_by_id = {p.passage_id: p for p in passages}
    doc_prov = _load_kuzu_doc_provenance(db_path)
    queries = _load_selected_queries(queries_path)
    cand_pids_by_q = _load_s3_candidates(s3_export_path)

    verification_reports = verify_sources_and_quotes(
        queries,
        passage_by_id,
        pdf_root=ROOT / "pdfs",
        doc_provenance_by_canonical=doc_prov,
    )
    verification_by_qid = {r["query_id"]: r for r in verification_reports}

    blinded_pools = build_blinded_annotation_pool(
        passages,
        queries,
        cand_pids_by_q,
        random_sample_per_query=3,
        seed=42,
    )

    rev_a = create_reviewer_records(queries, blinded_pools, reviewer_id="reviewer_a")
    rev_b = create_reviewer_records(queries, blinded_pools, reviewer_id="reviewer_b")

    # Shareable metadata-only artifacts (safe for Git)
    ver_out = ROOT / "artifacts" / "validation" / "s4a_source_verification_report.json"
    ver_out.write_text(
        json.dumps(
            {
                "pilot_phase": "S4-A_HUMAN_GOLD_PILOT",
                "selected_queries": len(queries),
                "human_annotations_filled": 0,
                "adjudicated_gold_count": 0,
                "pool_summary": {
                    qid: len(items) for qid, items in blinded_pools.items()
                },
                "verification_reports": verification_reports,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for fname, recs in (
        ("s4a_reviewer_a_template.json", rev_a),
        ("s4a_reviewer_b_template.json", rev_b),
    ):
        (ROOT / "artifacts" / "validation" / fname).write_text(
            json.dumps(recs, indent=2) + "\n", encoding="utf-8"
        )

    # Local-only worksheet with full passage text (gitignored)
    local_dir = ROOT / "artifacts" / "validation" / "local_only"
    local_dir.mkdir(parents=True, exist_ok=True)
    md_out = local_dir / "s4a_human_annotation_worksheet.md"
    json_out = local_dir / "s4a_human_annotation_worksheet.json"

    md_out.write_text(
        _render_markdown_worksheet(queries, blinded_pools, verification_by_qid),
        encoding="utf-8",
    )
    json_out.write_text(
        json.dumps(
            {
                "pilot_phase": "S4-A_HUMAN_GOLD_PILOT_LOCAL_WORKSHEET",
                "queries": queries,
                "blinded_pools": blinded_pools,
                "verification_reports": verification_reports,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "selected_queries": [q["query_id"] for q in queries],
                "pool_sizes": {qid: len(items) for qid, items in blinded_pools.items()},
                "verification_report": str(ver_out.relative_to(ROOT)),
                "local_worksheet_md": str(md_out.relative_to(ROOT)),
                "local_worksheet_json": str(json_out.relative_to(ROOT)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""S5-C3-P0 — Private Human Review, Adjudication & Negative-Control Package Builder.

Strictly read-only with respect to all frozen datasets, corpora, rankings,
original reviewer workbooks, and S5-C2/S5-D0/S5-E0 artifacts.

Writes private hydrated workbooks containing verbatim source passages ONLY into
Git-ignored `data/annotation_local/s5c3/`. Writes a metadata-only verification
summary (zero source passages) to
`research/s5-c3-human-adjudication-prep/reports/s5c3_prep_verification_summary.json`.

Does NOT generate human relevance judgments, resolve disagreements, compute
relevance effectiveness metrics, or unlock S5-D1.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archipelago.eval.retrieval_baselines import (
    _is_index_only_passage,
    build_fixed_corpus_from_kuzu,
)

DB_PATH = ROOT / "okf_graph.db"
POOL_JSON = (
    ROOT
    / "research"
    / "s5-b2-benchmark-correction"
    / "proposed_package_v2_1"
    / "retrieval_query_pool_blinded.json"
)
NEG_AUDIT_JSON = (
    ROOT
    / "research"
    / "s5-b2-benchmark-correction"
    / "reports"
    / "s5b2_negative_control_audit.json"
)
CORPUS_MANIFEST_JSON = (
    ROOT
    / "research"
    / "s5-b1-integrity-repair"
    / "corpus"
    / "s5b1_corpus_manifest.json"
)
REV_A_ORIG = ROOT / "data" / "annotation_local" / "s5c2" / "originals" / "reviewer_a_s5b2_1_workbook.md"
REV_B_ORIG = ROOT / "data" / "annotation_local" / "s5c2" / "originals" / "reviewer_b_s5b2_1_workbook.md"

PRIVATE_OUT = ROOT / "data" / "annotation_local" / "s5c3"
PUBLIC_REPORT = (
    ROOT
    / "research"
    / "s5-c3-human-adjudication-prep"
    / "reports"
    / "s5c3_prep_verification_summary.json"
)

EXPECTED_POOL_SHA256 = "2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037"
EXPECTED_CORPUS_SHA256 = "6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7"
EXPECTED_REV_A_SHA256 = "70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c"
EXPECTED_REV_B_SHA256 = "ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4"

FORBIDDEN_BLINDING_TOKENS = [
    "bm25",
    "dense_snowflake_arctic",
    "hybrid_rrf",
    "baseline_graph",
    "repaired_graph",
    "REV_A",
    "REV_B",
    "AI-assisted",
    "disagreement",
    "UNANSWERABLE",
    "NEGATIVE_CONTROL",
    "SINGLE_HOP",
    "TWO_HOP",
    "CROSS_DOCUMENT",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified_corpus() -> dict[str, Any]:
    passages, _ = build_fixed_corpus_from_kuzu(str(DB_PATH))
    eligible = [
        p
        for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id
        != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
    ]
    corpus_sha = hashlib.sha256(
        json.dumps([p.to_dict() for p in eligible], sort_keys=True).encode("utf-8")
    ).hexdigest()
    if len(eligible) != 713 or corpus_sha != EXPECTED_CORPUS_SHA256:
        raise RuntimeError(
            f"Frozen corpus verification failed: count={len(eligible)}, sha={corpus_sha}"
        )
    return {p.passage_id: p for p in eligible}


def parse_original_workbook(path: Path) -> dict[str, dict[str, Any]]:
    """Read-only parser for preserved S5-B2.1 reviewer workbooks (Markdown or plain-text stripped)."""
    raw = path.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
    blocks = re.split(r"(?m)^(?:###\s+)?Candidate Pair `?(S5B21-PAIR-\d{3})`?\s*$", raw)
    records: dict[str, dict[str, Any]] = {}
    for i in range(1, len(blocks), 2):
        pair_id = blocks[i].strip()
        body = blocks[i + 1]

        def _extract(field_regex: str) -> str:
            m = re.search(field_regex, body, re.MULTILINE)
            if not m:
                return ""
            return m.group(1).strip().strip("`")

        passage_id = _extract(r"^- (?:\*\*)?Candidate Passage ID:(?:\*\*)?[ \t]*(.+)$")
        passage_sha = _extract(r"^- (?:\*\*)?Passage SHA-256:(?:\*\*)?[ \t]*(.+)$")
        reviewer_id = _extract(r"^- (?:\*\*)?reviewer_id:(?:\*\*)?[ \t]*(.+)$")
        grade_str = _extract(r"^- (?:\*\*)?human_relevance_grade \(0 \| 1 \| 2\):(?:\*\*)?[ \t]*(.*)$")
        quote = _extract(r"^- (?:\*\*)?human_evidence_quote:(?:\*\*)?[ \t]*(.*)$")
        confidence = _extract(r"^- (?:\*\*)?human_confidence \(HIGH \| MEDIUM \| LOW\):(?:\*\*)?[ \t]*(.*)$")
        notes = _extract(r"^- (?:\*\*)?human_notes:(?:\*\*)?[ \t]*(.*)$")

        m_text = re.search(
            r"(?:\*\*)?Verified Source Passage Text:(?:\*\*)?\s*\n+(.*?)\n+(?:\*\*)?Reviewer [AB] Judgment Fields:(?:\*\*)?",
            body,
            re.DOTALL,
        )
        wb_text = ""
        if m_text:
            lines = [re.sub(r"^> ?", "", ln) for ln in m_text.group(1).splitlines()]
            wb_text = "\n".join(lines).strip()

        records[pair_id] = {
            "pair_id": pair_id,
            "passage_id": passage_id,
            "passage_sha256": passage_sha,
            "reviewer_id": reviewer_id,
            "grade": int(grade_str),
            "quote": quote,
            "confidence": confidence,
            "notes": notes,
            "workbook_passage_text": wb_text,
        }
    return records


def build_independent_reviewer_package(
    pool: dict[str, Any], corpus_by_pid: dict[str, Any]
) -> tuple[Path, Path]:
    """Task 2: Build private blinded 254-pair workbook + blank CSV response sheet."""
    wb_path = PRIVATE_OUT / "independent_reviewer_c_s5c3_workbook.md"
    csv_path = PRIVATE_OUT / "independent_reviewer_c_s5c3_sheet.csv"

    md_lines: list[str] = [
        "# Archipelago S5-C3 — Independent Human Relevance Review Workbook (Blinded)",
        "",
        "- **Package Version:** `s5c3_p0_independent_blinded_v1`",
        "- **Source Pool Version:** `s5b2_1_proposed_pooled_v2.1_pending_approval` (254 pairs across 10 queries)",
        "- **Candidate Ordering Seed:** `20261119` (frozen deterministic PRNG shuffle)",
        "- **Blinding Guarantee:** Strictly blinded candidate review sheet; contains no prior grades, model suggestions, system identifiers, or category labels.",
        "",
        "## Reviewer Provenance & Independence Declaration (COMPLETE BEFORE GRADING)",
        "",
        "- **reviewer_identity_or_pseudonym:** ",
        "- **provenance_class:** `[ INDEPENDENT_HUMAN | HUMAN_POST_AI_EXPOSURE | AI_ASSISTED_OR_GENERATED ]`",
        "- **assistance_declaration:** `[ NONE_INDEPENDENT_HUMAN | EXPOSED_TO_AI_SUGGESTIONS | AI_ASSISTED ]`",
        "- **review_start_date_utc:** ",
        "- **review_completion_date_utc:** ",
        "- **evidence_source_used:** `okf_graph.db (s5a_eval_corpus_v1, 713 passages)`",
        "- **review_completion_status:** `[ NOT_STARTED | IN_PROGRESS | COMPLETED_254_OF_254 ]`",
        "",
        "> **GRADING INSTRUCTIONS**",
        "> Evaluate each candidate passage solely against the query text using the 3-level scale:",
        "> - `0` = Irrelevant / Distractor (does not provide evidence answering the query)",
        "> - `1` = Partially Relevant / Background Context (related terminology/background, insufficient alone)",
        "> - `2` = Highly Relevant / Grounding Evidence (directly answers or supplies an essential factual premise)",
        "> ",
        "> Provide an exact verbatim supporting quote from the passage for grades `1` and `2` (leave blank for `0`).",
        "> Do NOT use LLMs or external AI assistants to generate or draft grades if submitting under `INDEPENDENT_HUMAN`.",
        "",
        "---",
        "",
    ]

    csv_rows: list[dict[str, str]] = []

    for q in pool["queries"]:
        qid = q["query_id"]
        domain = q["domain"]
        qtext = q["query_text"]
        md_lines.extend(
            [
                f"## Query {qid} [{domain}]",
                "",
                f'**Query:** *"{qtext}"*',
                "",
            ]
        )
        for cand in q["candidates"]:
            pair_id = cand["pair_id"]
            pid = cand["candidate_passage_id"]
            doc_id = cand["candidate_doc_id"]
            chunk_id = cand["candidate_chunk_id"]
            page_num = cand["candidate_page_number"]
            psha = cand["passage_sha256"]

            passage = corpus_by_pid[pid]
            if passage.content_sha256 != psha:
                raise RuntimeError(
                    f"Passage SHA-256 mismatch for {pair_id} ({pid}): {passage.content_sha256} != {psha}"
                )

            md_lines.extend(
                [
                    f"### Candidate Pair `{pair_id}`",
                    "",
                    f"- **Query ID:** `{qid}`",
                    f"- **Canonical Document Reference:** `{doc_id}` (Chunk: `{chunk_id}`, Page: `{page_num}`)",
                    f"- **Canonical Passage SHA-256:** `{psha}`",
                    "",
                    "**Candidate Passage Text:**",
                    "",
                    f"> {passage.text}",
                    "",
                    "**Human Judgment Fields (LEAVE NO FIELD UNFILLED UPON COMPLETION):**",
                    "- **relevance_grade (0 | 1 | 2):** ",
                    "- **supporting_quotation (verbatim for 1/2; blank for 0):** ",
                    "- **confidence (HIGH | MEDIUM | LOW):** ",
                    "- **reviewer_notes:** ",
                    "",
                ]
            )

            csv_rows.append(
                {
                    "pair_id": pair_id,
                    "query_id": qid,
                    "domain": domain,
                    "query_text": qtext,
                    "candidate_doc_id": doc_id,
                    "candidate_chunk_id": chunk_id,
                    "candidate_page_number": str(page_num),
                    "passage_sha256": psha,
                    "relevance_grade": "",
                    "supporting_quotation": "",
                    "confidence": "",
                    "reviewer_notes": "",
                    "reviewer_id": "",
                    "provenance_class": "",
                    "review_date_utc": "",
                }
            )

    wb_text = "\n".join(md_lines) + "\n"
    # Verify zero blinding leaks in all non-passage metadata/header/instruction lines
    non_passage_text = "\n".join(ln for ln in md_lines if not ln.startswith("> ")).lower()
    for token in FORBIDDEN_BLINDING_TOKENS:
        if token.lower() in non_passage_text:
            raise RuntimeError(f"Blinding check failed: found forbidden token {token!r} in reviewer workbook metadata")

    wb_path.write_text(wb_text, encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    return wb_path, csv_path


def build_disagreement_and_discrepancy_packets(
    pool: dict[str, Any],
    corpus_by_pid: dict[str, Any],
    rev_a: dict[str, dict[str, Any]],
    rev_b: dict[str, dict[str, Any]],
) -> tuple[Path, Path, Path, dict[str, Any]]:
    """Task 4: Build private 51-item disagreement packet + 5-item text discrepancy reconciliation."""
    packet_md = PRIVATE_OUT / "s5c3_disagreement_adjudication_packet_51.md"
    packet_json = PRIVATE_OUT / "s5c3_disagreement_adjudication_packet_51.json"
    recon_md = PRIVATE_OUT / "s5c3_text_discrepancy_reconciliation_5.md"

    pair_lookup: dict[str, dict[str, Any]] = {}
    for q in pool["queries"]:
        for cand in q["candidates"]:
            pair_lookup[cand["pair_id"]] = {
                "query_id": q["query_id"],
                "domain": q["domain"],
                "query_text": q["query_text"],
                **cand,
            }

    disagreement_items: list[dict[str, Any]] = []
    discrepancy_records: list[dict[str, Any]] = []

    for pair_id in sorted(pair_lookup.keys()):
        meta = pair_lookup[pair_id]
        pid = meta["candidate_passage_id"]
        canonical_text = corpus_by_pid[pid].text
        a = rev_a[pair_id]
        b = rev_b[pair_id]

        # Check text discrepancies against canonical frozen source
        for rev_label, rec in [("REV_A", a), ("REV_B", b)]:
            wb_txt = rec["workbook_passage_text"]
            if wb_txt != canonical_text:
                ws_equal = " ".join(wb_txt.split()) == " ".join(canonical_text.split())
                wb_sha = hashlib.sha256(wb_txt.encode("utf-8")).hexdigest()
                canon_sha = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
                quote_in_canon = (rec["quote"] in canonical_text) if rec["quote"] else True
                diff_lines = list(
                    difflib.unified_diff(
                        canonical_text.splitlines(),
                        wb_txt.splitlines(),
                        fromfile="canonical_okf_graph_db",
                        tofile=f"{rev_label}_original_workbook",
                        lineterm="",
                    )
                )
                discrepancy_records.append(
                    {
                        "pair_id": pair_id,
                        "query_id": meta["query_id"],
                        "reviewer": rev_label,
                        "passage_id": pid,
                        "canonical_len": len(canonical_text),
                        "workbook_len": len(wb_txt),
                        "delta_chars": len(wb_txt) - len(canonical_text),
                        "whitespace_only_diff": ws_equal,
                        "canonical_sha256": canon_sha,
                        "workbook_text_sha256": wb_sha,
                        "reviewer_grade": rec["grade"],
                        "quote_matches_canonical_exact": quote_in_canon,
                        "is_also_grade_disagreement": a["grade"] != b["grade"],
                        "unified_diff": diff_lines,
                        "canonical_text": canonical_text,
                        "workbook_text": wb_txt,
                    }
                )

        if a["grade"] != b["grade"]:
            disagreement_items.append(
                {
                    "pair_id": pair_id,
                    "query_id": meta["query_id"],
                    "domain": meta["domain"],
                    "query_text": meta["query_text"],
                    "candidate_passage_id": pid,
                    "candidate_doc_id": meta["candidate_doc_id"],
                    "candidate_chunk_id": meta["candidate_chunk_id"],
                    "candidate_page_number": meta["candidate_page_number"],
                    "passage_sha256": meta["passage_sha256"],
                    "canonical_passage_text": canonical_text,
                    "reviewer_a_original": {
                        "reviewer_id": a["reviewer_id"],
                        "provenance_note": "No AI-assistance disclosure in notes",
                        "grade": a["grade"],
                        "quote": a["quote"],
                        "confidence": a["confidence"],
                        "notes": a["notes"],
                    },
                    "reviewer_b_original": {
                        "reviewer_id": b["reviewer_id"],
                        "provenance_note": "AI_ASSISTED_OR_GENERATED (disclosed on 254/254 pairs; requires independent human confirmation)",
                        "grade": b["grade"],
                        "quote": b["quote"],
                        "confidence": b["confidence"],
                        "notes": b["notes"],
                    },
                    "adjudication": {
                        "adjudicated_grade": None,
                        "adjudication_rationale": "",
                        "adjudication_evidence_quote": "",
                        "adjudicator_id": "",
                        "decision_date_utc": "",
                        "provenance_class": "",
                    },
                }
            )

    if len(disagreement_items) != 51:
        raise RuntimeError(f"Expected 51 disagreements, found {len(disagreement_items)}")
    if len(discrepancy_records) != 5:
        raise RuntimeError(f"Expected 5 text discrepancies, found {len(discrepancy_records)}")

    # Write 51-item markdown packet
    md_lines = [
        "# Archipelago S5-C3 — Private 51-Item Disagreement Adjudication Packet",
        "",
        "- **Status:** `AWAITING_HUMAN_ADJUDICATION` (All adjudicated fields intentionally blank)",
        "- **Source Pool:** `s5b2_1_proposed_pooled_v2.1_pending_approval` (51 disagreements out of 254 pairs)",
        "- **Preservation Notice:** Original Reviewer A (`70049fa8...`) and Reviewer B (`ca3e6af8...`) grades, quotes, confidence, and notes are reproduced unchanged. Reviewer B's submission is explicitly tagged as `AI_ASSISTED_OR_GENERATED` (disclosed on 254/254 items).",
        "- **Canonical Evidence Notice:** Passage text below is hydrated directly from frozen `okf_graph.db` (`s5a_eval_corpus_v1`) and SHA-256 verified.",
        "",
        "## Adjudicator Header (COMPLETE BEFORE ADJUDICATING)",
        "",
        "- **adjudicator_identity_or_pseudonym:** ",
        "- **adjudicator_role:** `[ THIRD_PARTY_HUMAN_ADJUDICATOR | PRINCIPAL_INVESTIGATOR ]`",
        "- **provenance_class:** `ADJUDICATED_HUMAN`",
        "- **assistance_declaration:** `[ NONE_INDEPENDENT_HUMAN | HUMAN_POST_AI_EXPOSURE ]`",
        "- **adjudication_date_utc:** ",
        "- **completion_status:** `[ NOT_STARTED | IN_PROGRESS | COMPLETED_51_OF_51 ]`",
        "",
        "---",
        "",
    ]

    for idx, item in enumerate(disagreement_items, start=1):
        ra = item["reviewer_a_original"]
        rb = item["reviewer_b_original"]
        md_lines.extend(
            [
                f"## Disagreement {idx:02d}/51 — `{item['pair_id']}` (`{item['query_id']}` | {item['domain']})",
                "",
                f"**Query:** *\"{item['query_text']}\"*",
                f"- **Canonical Document Reference:** `{item['candidate_doc_id']}` (Chunk: `{item['candidate_chunk_id']}`, Page: `{item['candidate_page_number']}`)",
                f"- **Canonical Passage SHA-256:** `{item['passage_sha256']}`",
                "",
                "**Canonical Frozen Passage Text (`okf_graph.db`):**",
                "",
                f"> {item['canonical_passage_text']}",
                "",
                "**Preserved Original Submissions (UNCHANGED):**",
                f"- **Reviewer A (`{ra['reviewer_id']}` | {ra['provenance_note']}):** Grade = `{ra['grade']}` | Confidence = `{ra['confidence']}`",
                f"  - Quote: `{ra['quote']}`",
                f"  - Notes: {ra['notes']}",
                f"- **Reviewer B (`{rb['reviewer_id']}` | {rb['provenance_note']}):** Grade = `{rb['grade']}` | Confidence = `{rb['confidence']}`",
                f"  - Quote: `{rb['quote']}`",
                f"  - Notes: {rb['notes']}",
                "",
                "**Human Adjudication Decision (BLANK — TO BE COMPLETED BY HUMAN ADJUDICATOR):**",
                "- **adjudicated_grade (0 | 1 | 2):** ",
                "- **adjudication_evidence_quote (verbatim for 1/2; blank for 0):** ",
                "- **adjudication_rationale:** ",
                "- **adjudicator_id:** ",
                "- **decision_date_utc:** ",
                "",
                "---",
                "",
            ]
        )

    packet_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    packet_json.write_text(
        json.dumps(
            {
                "packet_name": "S5-C3 Private 51-Item Disagreement Adjudication Packet",
                "status": "AWAITING_HUMAN_ADJUDICATION",
                "disagreement_count": len(disagreement_items),
                "items": disagreement_items,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Write 5-item text discrepancy reconciliation (private, verbatim diffs)
    recon_lines = [
        "# Archipelago S5-C3 — Passage-Text Discrepancy Reconciliation (5 Items)",
        "",
        "- **Status:** Reconciled against canonical frozen `okf_graph.db` (`s5a_eval_corpus_v1`) WITHOUT modifying original Reviewer A or Reviewer B workbooks.",
        f"- **Total Discrepancies Found:** {len(discrepancy_records)} (`REV_A`: 2, `REV_B`: 3)",
        "",
    ]
    for rec in discrepancy_records:
        recon_lines.extend(
            [
                f"## `{rec['pair_id']}` (`{rec['query_id']}`) — `{rec['reviewer']}`",
                "",
                f"- **Passage ID:** `{rec['passage_id']}`",
                f"- **Canonical Length vs. Workbook Length:** `{rec['canonical_len']}` vs. `{rec['workbook_len']}` chars (delta: `{rec['delta_chars']:+d}`)",
                f"- **Whitespace-Only Diff:** `{rec['whitespace_only_diff']}`",
                f"- **Canonical SHA-256:** `{rec['canonical_sha256']}`",
                f"- **Workbook Text SHA-256:** `{rec['workbook_text_sha256']}`",
                f"- **Reviewer Grade:** `{rec['reviewer_grade']}` | **Also a Grade Disagreement:** `{rec['is_also_grade_disagreement']}`",
                f"- **Reviewer Quote Matches Canonical Text Exactly:** `{rec['quote_matches_canonical_exact']}`",
                "",
                "### Unified Diff (`canonical_okf_graph_db` vs. `original_workbook`)",
                "```diff",
                *rec["unified_diff"],
                "```",
                "",
            ]
        )
    recon_md.write_text("\n".join(recon_lines) + "\n", encoding="utf-8")

    # Metadata-only (zero copyrighted text) summary for public report
    discrepancy_meta = [
        {
            k: v
            for k, v in rec.items()
            if k not in {"unified_diff", "canonical_text", "workbook_text"}
        }
        for rec in discrepancy_records
    ]

    return packet_md, packet_json, recon_md, {
        "disagreement_count": len(disagreement_items),
        "disagreement_pair_ids": [x["pair_id"] for x in disagreement_items],
        "discrepancy_count": len(discrepancy_meta),
        "discrepancy_metadata": discrepancy_meta,
    }


def build_negative_control_worksheets(
    neg_audit: dict[str, Any],
    corpus_by_pid: dict[str, Any],
    corpus_manifest: dict[str, Any],
) -> Path:
    """Task 5: Build private human negative-control verification worksheets against frozen 713-passage corpus."""
    ws_path = PRIVATE_OUT / "s5c3_negative_control_verification_worksheets.md"

    doc_list = sorted(corpus_manifest["documents"].items())
    lines = [
        "# Archipelago S5-C3 — Private Negative-Control Human Verification Worksheets",
        "",
        "- **Status:** `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_HUMAN_VERIFICATION`",
        "- **Scope:** Verification MUST be performed against the **frozen 713-passage corpus (`s5a_eval_corpus_v1`, 53 documents)** — NOT merely the Top-10 pooled retrieval results.",
        "- **Supported Human Classifications (Select Exactly One per Query):**",
        "  1. `NO_ANSWER_IN_FROZEN_CORPUS` — Verified corpus-wide unanswerable (no passage in the 713-passage corpus answers the query).",
        "  2. `NO_ANSWER_IN_SELECTED_PASSAGES` — Inspected search-selected candidates contain no answer, but full corpus-wide exclusion is not established.",
        "  3. `AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION` — Question premise is ambiguous, unverified, or factually unsupported/synthetic.",
        "  4. `QUESTION_REQUIRING_REVISION` — Question is answerable in corpus or malformed and requires revision before use as a negative control.",
        "",
        "## Frozen Corpus Scope Reference (`s5a_eval_corpus_v1`: 53 Documents, 713 Passages)",
        "",
        "| Document ID | Passage Count |",
        "|---|---:|",
    ]
    for doc_id, cnt in doc_list:
        lines.append(f"| `{doc_id}` | {cnt} |")
    lines.extend(["", "---", ""])

    for q in neg_audit["queries"]:
        qid = q["query_id"]
        legacy = q["legacy_query_id"]
        qtext = q["query_text"]

        # Gather ALL unique passages surfaced by exact keyword hits, alternate term hits, and dense semantic top-5
        inspected_pids: list[str] = []
        seen: set[str] = set()

        def _add_pid(pid: str) -> None:
            if pid not in seen and pid in corpus_by_pid:
                seen.add(pid)
                inspected_pids.append(pid)

        for pid in q.get("search_selected_candidate_passage_ids", []):
            _add_pid(pid)
        for info in q.get("exact_keyword_hits", {}).values():
            for pid in info.get("passage_ids", []):
                _add_pid(pid)
        for info in q.get("alternate_terminology_hits", {}).values():
            for pid in info.get("passage_ids", []):
                _add_pid(pid)

        lines.extend(
            [
                f"## Worksheet: `{qid}` (Legacy `{legacy}`)",
                "",
                f'**Query:** *"{qtext}"*',
                f"- **Current Automated Status:** `{q['adjudication_status']}`",
                f"- **External Factual Premise Status:** `{q['factual_premise_status']}`",
                f"- **Exact Keyword Hit Counts (713-Passage Corpus):** "
                + ", ".join(
                    f"`{k}`: {v['hit_count']}" for k, v in q["exact_keyword_hits"].items()
                ),
                f"- **Alternate Terminology Hit Counts (>0):** "
                + ", ".join(
                    f"`{k}`: {v['hit_count']}"
                    for k, v in q["alternate_terminology_hits"].items()
                    if v["hit_count"] > 0
                ),
                f"- **Total Unique Corpus-Wide Candidate Passages Hydrated Below for Human Inspection:** `{len(inspected_pids)}` (union of top-5 dense semantic neighbors + all exact & alternate-terminology hits)",
                "",
                "### Corpus-Wide Candidate Passages for Human Inspection",
                "",
            ]
        )

        for idx, pid in enumerate(inspected_pids, start=1):
            p = corpus_by_pid[pid]
            lines.extend(
                [
                    f"#### Candidate {idx:02d}/{len(inspected_pids)}: `{pid}` (Page {p.page_number})",
                    f"> {p.text}",
                    "",
                    "- **contains_answer (YES | NO | PARTIAL_OR_AMBIGUOUS):** ",
                    "- **inspection_note:** ",
                    "",
                ]
            )

        lines.extend(
            [
                f"### Final Human Verification Decision for `{qid}` (BLANK — HUMAN COMPLETION REQUIRED)",
                "",
                "- **human_answerability_classification:** `[ NO_ANSWER_IN_FROZEN_CORPUS | NO_ANSWER_IN_SELECTED_PASSAGES | AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION | QUESTION_REQUIRING_REVISION ]`",
                "- **external_factual_premise_assessment:** `[ VERIFIED_REAL_FACT | UNVERIFIED_OR_UNREPORTED | SYNTHETIC_OR_FALSE_PREMISE ]`",
                "- **corpus_scope_checked:** `[ INSPECTED_HYDRATED_CANDIDATES_AND_53_DOC_INVENTORY | FULL_CORPUS_SEARCH_PERFORMED ]`",
                "- **additional_corpus_queries_run_by_verifier:** ",
                "- **checked_passage_ids:** ",
                "- **verifier_id:** ",
                "- **provenance_class:** `[ INDEPENDENT_HUMAN | HUMAN_POST_AI_EXPOSURE ]`",
                "- **verification_date_utc:** ",
                "- **verification_rationale:** ",
                "",
                "---",
                "",
            ]
        )

    ws_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ws_path


def main() -> None:
    # 1. Verify frozen inputs have not drifted
    pool_sha = sha256_file(POOL_JSON)
    if pool_sha != EXPECTED_POOL_SHA256:
        raise RuntimeError(f"Pool JSON SHA-256 mismatch: {pool_sha} != {EXPECTED_POOL_SHA256}")
    rev_a_sha = sha256_file(REV_A_ORIG)
    if rev_a_sha != EXPECTED_REV_A_SHA256:
        raise RuntimeError(f"Reviewer A original SHA-256 mismatch: {rev_a_sha}")
    rev_b_sha = sha256_file(REV_B_ORIG)
    if rev_b_sha != EXPECTED_REV_B_SHA256:
        raise RuntimeError(f"Reviewer B original SHA-256 mismatch: {rev_b_sha}")

    corpus_by_pid = load_verified_corpus()
    pool = json.loads(POOL_JSON.read_text(encoding="utf-8"))
    neg_audit = json.loads(NEG_AUDIT_JSON.read_text(encoding="utf-8"))
    corpus_manifest = json.loads(CORPUS_MANIFEST_JSON.read_text(encoding="utf-8"))

    rev_a = parse_original_workbook(REV_A_ORIG)
    rev_b = parse_original_workbook(REV_B_ORIG)
    if len(rev_a) != 254 or len(rev_b) != 254:
        raise RuntimeError(f"Expected 254 parsed pairs each, got REV_A={len(rev_a)}, REV_B={len(rev_b)}")

    PRIVATE_OUT.mkdir(parents=True, exist_ok=True)
    PUBLIC_REPORT.parent.mkdir(parents=True, exist_ok=True)

    wb_path, csv_path = build_independent_reviewer_package(pool, corpus_by_pid)
    packet_md, packet_json, recon_md, dis_summary = build_disagreement_and_discrepancy_packets(
        pool, corpus_by_pid, rev_a, rev_b
    )
    neg_ws_path = build_negative_control_worksheets(neg_audit, corpus_by_pid, corpus_manifest)

    # Re-verify originals untouched
    assert sha256_file(REV_A_ORIG) == EXPECTED_REV_A_SHA256
    assert sha256_file(REV_B_ORIG) == EXPECTED_REV_B_SHA256

    summary = {
        "report_name": "S5-C3-P0 Private Human Adjudication Package Verification Summary",
        "status": "HUMAN_REVIEW_REQUIRED",
        "contains_copyrighted_passage_text": False,
        "frozen_inputs_verified": {
            "corpus_sha256": EXPECTED_CORPUS_SHA256,
            "pool_sha256": EXPECTED_POOL_SHA256,
            "reviewer_a_original_sha256": EXPECTED_REV_A_SHA256,
            "reviewer_b_original_sha256": EXPECTED_REV_B_SHA256,
        },
        "counts": {
            "pairs_awaiting_independent_review": 254,
            "disagreements_awaiting_human_adjudication": dis_summary["disagreement_count"],
            "text_discrepancies_reconciled": dis_summary["discrepancy_count"],
            "negative_controls_awaiting_verification": len(neg_audit["queries"]),
        },
        "private_gitignored_artifacts": {
            str(p.relative_to(ROOT)): {
                "byte_size": p.stat().st_size,
                "sha256": sha256_file(p),
            }
            for p in [wb_path, csv_path, packet_md, packet_json, recon_md, neg_ws_path]
        },
        "discrepancy_metadata": dis_summary["discrepancy_metadata"],
        "disagreement_pair_ids": dis_summary["disagreement_pair_ids"],
    }

    PUBLIC_REPORT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Built 6 private Git-ignored artifacts in {PRIVATE_OUT.relative_to(ROOT)}")
    print(f"Wrote metadata-only summary to {PUBLIC_REPORT.relative_to(ROOT)}")
    print(
        f"Counts: 254 review pairs | {dis_summary['disagreement_count']} disagreements | "
        f"{dis_summary['discrepancy_count']} text discrepancies | {len(neg_audit['queries'])} negative controls"
    )


if __name__ == "__main__":
    main()

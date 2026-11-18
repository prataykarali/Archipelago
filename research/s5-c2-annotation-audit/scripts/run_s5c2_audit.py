"""S5-C2 — Human Annotation Validation, Descriptive Agreement Audit & Disagreement Docket.

Validates the completed Reviewer A and Reviewer B workbooks against the frozen
254-pair S5-B2.1 pool (`s5b2_1_proposed_pooled_v2.1_pending_approval`), computes
descriptive agreement metrics (without claiming validated inter-human reliability
when AI-assistance independence is unverified), and generates:
- `research/s5-c2-annotation-audit/reports/S5C2_ANNOTATION_VALIDATION_REPORT.md`
- `research/s5-c2-annotation-audit/reports/S5C2_INTER_ANNOTATOR_AGREEMENT.md`
- `research/s5-c2-annotation-audit/reports/S5C2_NEGATIVE_CONTROL_VERIFICATION.md`
- `research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json` (metadata-only)
- `data/annotation_local/s5c2/S5C2_DISAGREEMENT_ADJUDICATION.md` (private, gitignored)
- `data/annotation_local/s5c2/S5C2_NEGATIVE_CONTROL_VERIFICATION_LOCAL.md` (private, gitignored)
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu, _is_index_only_passage

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "okf_graph.db"
POOL_JSON = ROOT / "research" / "s5-b2-benchmark-correction" / "proposed_package_v2_1" / "retrieval_query_pool_blinded.json"
NEG_AUDIT_JSON = ROOT / "research" / "s5-b2-benchmark-correction" / "reports" / "s5b2_negative_control_audit.json"

ORIG_DIR = ROOT / "data" / "annotation_local" / "s5c2" / "originals"
LOCAL_OUT = ROOT / "data" / "annotation_local" / "s5c2"
REPORTS_DIR = ROOT / "research" / "s5-c2-annotation-audit" / "reports"

REV_A_PATH = ORIG_DIR / "reviewer_a_s5b2_1_workbook.md"
REV_B_PATH = ORIG_DIR / "reviewer_b_s5b2_1_workbook.md"


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_md_quotes_and_ticks(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val.startswith("`") and val.endswith("`"):
        val = val[1:-1].strip()
    return val


def parse_workbook(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Parse either markdown-formatted or plain-text-converted reviewer workbook."""
    text = path.read_text(encoding="utf-8")
    # Split on Candidate Pair headers: either `### Candidate Pair `S5B21-PAIR-001`` or `Candidate Pair S5B21-PAIR-001`
    header_pat = re.compile(
        r"^(?:#{1,6}\s*)?Candidate Pair\s+`?(S5B21-PAIR-\d+)`?\s*$",
        re.MULTILINE,
    )
    matches = list(header_pat.finditer(text))
    entries: list[dict[str, Any]] = []
    pair_id_counts: collections.Counter[str] = collections.Counter()

    for idx, m in enumerate(matches):
        pair_id = m.group(1)
        pair_id_counts[pair_id] += 1
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]

        def _extract_field(pattern: str) -> str:
            fm = re.search(pattern, block, re.MULTILINE)
            return _strip_md_quotes_and_ticks(fm.group(1)) if fm else ""

        passage_id = _extract_field(r"^-[ \t]*\*{0,2}Candidate Passage ID:\*{0,2}[ \t]*(.+)$")
        doc_id = _extract_field(r"^-[ \t]*\*{0,2}Document ID:\*{0,2}[ \t]*(.+)$")
        chunk_id = _extract_field(r"^-[ \t]*\*{0,2}Chunk ID:\*{0,2}[ \t]*(.+)$")
        page_num = _extract_field(r"^-[ \t]*\*{0,2}Page Number:\*{0,2}[ \t]*(.+)$")
        passage_sha = _extract_field(r"^-[ \t]*\*{0,2}Passage SHA-256:\*{0,2}[ \t]*(.+)$")

        # Extract Verified Source Passage Text block (between "Verified Source Passage Text:" and "Reviewer X Judgment Fields:")
        src_m = re.search(
            r"Verified Source Passage Text:\*{0,2}\s*\n+(.*?)\n+\*{0,2}Reviewer [AB] Judgment Fields:",
            block,
            re.DOTALL,
        )
        src_text = ""
        if src_m:
            raw_src = src_m.group(1).strip()
            # Strip leading '> ' from markdown blockquotes
            src_lines = [re.sub(r"^>\s?", "", ln) for ln in raw_src.splitlines()]
            src_text = "\n".join(src_lines).strip()

        reviewer_id = _extract_field(r"^-[ \t]*\*{0,2}reviewer_id:\*{0,2}[ \t]*(.*)$")
        grade_str = _extract_field(r"^-[ \t]*\*{0,2}human_relevance_grade[ \t]*\([^)]*\):\*{0,2}[ \t]*(.*)$")
        quote = _extract_field(r"^-[ \t]*\*{0,2}human_evidence_quote:\*{0,2}[ \t]*(.*)$")
        confidence = _extract_field(r"^-[ \t]*\*{0,2}human_confidence[ \t]*\([^)]*\):\*{0,2}[ \t]*(.*)$")
        notes = _extract_field(r"^-[ \t]*\*{0,2}human_notes:\*{0,2}[ \t]*(.*)$")

        entries.append({
            "pair_id": pair_id,
            "passage_id": passage_id,
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "page_number": page_num,
            "passage_sha256": passage_sha,
            "source_text_in_workbook": src_text,
            "reviewer_id": reviewer_id,
            "grade_raw": grade_str,
            "grade": int(grade_str) if grade_str in {"0", "1", "2"} else None,
            "quote": quote,
            "confidence": confidence,
            "notes": notes,
        })

    return entries, dict(pair_id_counts)


def compute_cohens_kappa(y1: list[int], y2: list[int], quadratic: bool = True) -> float:
    n = len(y1)
    assert n == len(y2) and n > 0
    labels = [0, 1, 2]
    k = len(labels)
    O = [[0] * k for _ in range(k)]
    for a, b in zip(y1, y2):
        O[a][b] += 1
    row_sums = [sum(O[i]) for i in range(k)]
    col_sums = [sum(O[i][j] for i in range(k)) for j in range(k)]

    num = 0.0
    den = 0.0
    for i in range(k):
        for j in range(k):
            if quadratic:
                w = ((i - j) ** 2) / ((k - 1) ** 2)
            else:
                w = 0.0 if i == j else 1.0
            e_ij = (row_sums[i] * col_sums[j]) / n
            num += w * O[i][j]
            den += w * e_ij
    return 1.0 - (num / den) if den > 0 else 1.0


def validate_reviewer_entries(
    entries: list[dict[str, Any]],
    pair_counts: dict[str, int],
    expected_by_pair: dict[str, dict[str, Any]],
    corpus_by_id: dict[str, Any],
    expected_reviewer_id: str,
) -> dict[str, Any]:
    by_pair = {e["pair_id"]: e for e in entries}
    expected_ids = set(expected_by_pair.keys())
    found_ids = set(by_pair.keys())

    missing_pairs = sorted(expected_ids - found_ids)
    extra_pairs = sorted(found_ids - expected_ids)
    duplicate_pairs = sorted([pid for pid, cnt in pair_counts.items() if cnt > 1])

    invalid_grades = []
    invalid_confidences = []
    wrong_reviewer_ids = []
    missing_quotes_for_pos = []
    nonempty_quotes_for_zero = []
    passage_id_mismatches = []
    sha_mismatches = []
    source_text_discrepancies = []

    quote_exact_matches = 0
    quote_ws_normalized_matches = 0
    quote_mismatches = []
    ai_assisted_notes_count = 0

    for pid in sorted(expected_ids):
        exp = expected_by_pair[pid]
        e = by_pair.get(pid)
        if not e:
            continue

        if e["reviewer_id"] != expected_reviewer_id:
            wrong_reviewer_ids.append((pid, e["reviewer_id"]))
        if e["grade"] is None:
            invalid_grades.append((pid, e["grade_raw"]))
        if e["confidence"] not in {"HIGH", "MEDIUM", "LOW"}:
            invalid_confidences.append((pid, e["confidence"]))
        if e["passage_id"] != exp["candidate_passage_id"]:
            passage_id_mismatches.append((pid, e["passage_id"], exp["candidate_passage_id"]))
        if e["passage_sha256"] != exp["passage_sha256"]:
            sha_mismatches.append((pid, e["passage_sha256"], exp["passage_sha256"]))

        corpus_p = corpus_by_id[exp["candidate_passage_id"]]
        if e["source_text_in_workbook"] != corpus_p.text:
            if _norm_ws(e["source_text_in_workbook"]) == _norm_ws(corpus_p.text):
                source_text_discrepancies.append((pid, "WHITESPACE_ONLY"))
            else:
                source_text_discrepancies.append((pid, "CONTENT_DIFF"))

        if "ai-assisted" in e["notes"].lower():
            ai_assisted_notes_count += 1

        g = e["grade"]
        q = e["quote"]
        if g in {1, 2}:
            if not q:
                missing_quotes_for_pos.append(pid)
            else:
                if q in corpus_p.text:
                    quote_exact_matches += 1
                elif _norm_ws(q) in _norm_ws(corpus_p.text):
                    quote_ws_normalized_matches += 1
                else:
                    quote_mismatches.append({"pair_id": pid, "passage_id": exp["candidate_passage_id"], "quote": q[:120]})
        elif g == 0 and q:
            nonempty_quotes_for_zero.append(pid)

    return {
        "expected_pair_count": len(expected_ids),
        "parsed_pair_count": len(entries),
        "missing_pairs": missing_pairs,
        "extra_pairs": extra_pairs,
        "duplicate_pairs": duplicate_pairs,
        "wrong_reviewer_ids": wrong_reviewer_ids,
        "invalid_grades": invalid_grades,
        "invalid_confidences": invalid_confidences,
        "passage_id_mismatches": passage_id_mismatches,
        "sha_mismatches": sha_mismatches,
        "source_text_discrepancies_count": len(source_text_discrepancies),
        "source_text_discrepancies_sample": source_text_discrepancies[:10],
        "missing_quotes_for_grades_1_2": missing_quotes_for_pos,
        "nonempty_quotes_for_grade_0": nonempty_quotes_for_zero,
        "quote_exact_matches": quote_exact_matches,
        "quote_ws_normalized_matches": quote_ws_normalized_matches,
        "quote_mismatches": quote_mismatches,
        "ai_assisted_notes_count": ai_assisted_notes_count,
        "grade_distribution": dict(sorted(collections.Counter(e["grade"] for e in entries).items())),
        "confidence_distribution": dict(sorted(collections.Counter(e["confidence"] for e in entries).items())),
    }


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_OUT.mkdir(parents=True, exist_ok=True)

    # Load frozen corpus & approved 254-pair pool
    passages, _ = build_fixed_corpus_from_kuzu(str(DB_PATH))
    eligible = [
        p for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
    ]
    corpus_by_id = {p.passage_id: p for p in eligible}

    with open(POOL_JSON, encoding="utf-8") as f:
        pool = json.load(f)

    expected_by_pair: dict[str, dict[str, Any]] = {}
    for q in pool["queries"]:
        for c in q["candidates"]:
            expected_by_pair[c["pair_id"]] = {
                "pair_id": c["pair_id"],
                "query_id": q["query_id"],
                "domain": q["domain"],
                "query_text": q["query_text"],
                **c,
            }

    rev_a_sha = hashlib.sha256(REV_A_PATH.read_bytes()).hexdigest()
    rev_b_sha = hashlib.sha256(REV_B_PATH.read_bytes()).hexdigest()

    entries_a, counts_a = parse_workbook(REV_A_PATH)
    entries_b, counts_b = parse_workbook(REV_B_PATH)

    val_a = validate_reviewer_entries(entries_a, counts_a, expected_by_pair, corpus_by_id, "REV_A")
    val_b = validate_reviewer_entries(entries_b, counts_b, expected_by_pair, corpus_by_id, "REV_B")

    by_pair_a = {e["pair_id"]: e for e in entries_a}
    by_pair_b = {e["pair_id"]: e for e in entries_b}

    # Agreement calculations (pre-adjudication)
    y_a, y_b = [], []
    conf_mat = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    per_query_stats: dict[str, dict[str, int]] = {}
    disagreements: list[dict[str, Any]] = []

    for pid in sorted(expected_by_pair.keys()):
        exp = expected_by_pair[pid]
        qid = exp["query_id"]
        ea, eb = by_pair_a[pid], by_pair_b[pid]
        ga, gb = ea["grade"], eb["grade"]
        assert ga in {0, 1, 2} and gb in {0, 1, 2}
        y_a.append(ga)
        y_b.append(gb)
        conf_mat[ga][gb] += 1

        qst = per_query_stats.setdefault(qid, {"total": 0, "agree": 0, "disagree": 0})
        qst["total"] += 1
        if ga == gb:
            qst["agree"] += 1
        else:
            qst["disagree"] += 1
            disagreements.append({
                "pair_id": pid,
                "query_id": qid,
                "domain": exp["domain"],
                "query_text": exp["query_text"],
                "passage_id": exp["candidate_passage_id"],
                "source_text": corpus_by_id[exp["candidate_passage_id"]].text,
                "rev_a": ea,
                "rev_b": eb,
            })

    raw_agree_count = sum(1 for a, b in zip(y_a, y_b) if a == b)
    raw_agree_pct = round(100.0 * raw_agree_count / len(y_a), 2)
    kappa_quad = round(compute_cohens_kappa(y_a, y_b, quadratic=True), 4)
    kappa_unweighted = round(compute_cohens_kappa(y_a, y_b, quadratic=False), 4)

    summary = {
        "audit_name": "S5-C2 Human Annotation Validation & Descriptive Agreement Audit",
        "date": "2026-11-19",
        "pool_version": pool["version"],
        "total_pairs": len(expected_by_pair),
        "preserved_originals": {
            "reviewer_a": {"path": "data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md", "sha256": rev_a_sha, "reviewer_id": "REV_A", "ai_assisted_notes_count": val_a["ai_assisted_notes_count"]},
            "reviewer_b": {"path": "data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md", "sha256": rev_b_sha, "reviewer_id": "REV_B", "ai_assisted_notes_count": val_b["ai_assisted_notes_count"]},
        },
        "validation": {"REV_A": val_a, "REV_B": val_b},
        "descriptive_agreement_pre_adjudication": {
            "independence_status": "UNVERIFIED_AI_ASSISTED_SUBMISSION_IN_REV_B",
            "agreement_count": raw_agree_count,
            "disagreement_count": len(disagreements),
            "raw_agreement_pct": raw_agree_pct,
            "cohens_weighted_kappa_quadratic": kappa_quad,
            "cohens_kappa_unweighted": kappa_unweighted,
            "confusion_matrix_rows_rev_a_cols_rev_b": conf_mat,
            "per_query": per_query_stats,
        },
        "readiness_decision": "HOLD_FOR_DISAGREEMENT_ADJUDICATION_AND_REV_B_INDEPENDENCE_CHECK",
    }
    (REPORTS_DIR / "s5c2_audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # 1. Produce S5C2_ANNOTATION_VALIDATION_REPORT.md
    val_lines = [
        "# S5-C2 Annotation Validation Report",
        "",
        "**Date:** 2026-11-19",
        f"**Dataset Pool:** `{pool['version']}` ({len(expected_by_pair)} pairs across {pool['queries_count']} queries)",
        "",
        "## 1. Preserved Original Evidence & Methodology Disclosure",
        "",
        "| Reviewer | Preserved Git-Ignored Path | SHA-256 | AI-Assisted Notes | Independence Status |",
        "|---|---|---|---:|---|",
        f"| **Reviewer A (`REV_A`)** | `data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` | `{rev_a_sha}` | {val_a['ai_assisted_notes_count']} / 254 | No AI-assistance disclosure in notes |",
        f"| **Reviewer B (`REV_B`)** | `data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md` | `{rev_b_sha}` | {val_b['ai_assisted_notes_count']} / 254 | **AI-assisted proposed annotations** (`requires independent human confirmation`); independence from AI suggestions not yet documented |",
        "",
        "> [!WARNING]",
        "> Reviewer B's notes explicitly state `AI-assisted proposed annotation; requires independent human confirmation` on all 254 pairs. These annotations are NOT reported as independent blind human judgments.",
        "",
        "## 2. Programmatic Validation Results",
        "",
        "| Check | Reviewer A (`REV_A`) | Reviewer B (`REV_B`) |",
        "|---|---:|---:|",
        f"| Expected / Parsed Pairs | {val_a['expected_pair_count']} / {val_a['parsed_pair_count']} | {val_b['expected_pair_count']} / {val_b['parsed_pair_count']} |",
        f"| Missing Pairs | {len(val_a['missing_pairs'])} | {len(val_b['missing_pairs'])} |",
        f"| Duplicate Pairs | {len(val_a['duplicate_pairs'])} | {len(val_b['duplicate_pairs'])} |",
        f"| Invalid Grades (outside `0,1,2`) | {len(val_a['invalid_grades'])} | {len(val_b['invalid_grades'])} |",
        f"| Invalid Confidence (outside `HIGH,MEDIUM,LOW`) | {len(val_a['invalid_confidences'])} | {len(val_b['invalid_confidences'])} |",
        f"| Passage ID Mismatches | {len(val_a['passage_id_mismatches'])} | {len(val_b['passage_id_mismatches'])} |",
        f"| SHA-256 Hash Mismatches | {len(val_a['sha_mismatches'])} | {len(val_b['sha_mismatches'])} |",
        f"| Source Text Discrepancies | {val_a['source_text_discrepancies_count']} | {val_b['source_text_discrepancies_count']} |",
        f"| Missing Quotes for Grades 1 & 2 | {len(val_a['missing_quotes_for_grades_1_2'])} | {len(val_b['missing_quotes_for_grades_1_2'])} |",
        f"| Non-Empty Quotes for Grade 0 | {len(val_a['nonempty_quotes_for_grade_0'])} | {len(val_b['nonempty_quotes_for_grade_0'])} |",
        f"| Quote Exact Substring Matches | {val_a['quote_exact_matches']} | {val_b['quote_exact_matches']} |",
        f"| Quote Whitespace-Normalized Matches | {val_a['quote_ws_normalized_matches']} | {val_b['quote_ws_normalized_matches']} |",
        f"| Quote Substring Mismatches | {len(val_a['quote_mismatches'])} | {len(val_b['quote_mismatches'])} |",
        "",
        "### Source & Quote Discrepancy Notes",
        f"- **Reviewer A quote mismatches ({len(val_a['quote_mismatches'])}):** " + (", ".join(f"`{m['pair_id']}`" for m in val_a["quote_mismatches"]) if val_a["quote_mismatches"] else "None"),
        f"- **Reviewer B quote mismatches ({len(val_b['quote_mismatches'])}):** " + (", ".join(f"`{m['pair_id']}`" for m in val_b["quote_mismatches"]) if val_b["quote_mismatches"] else "None"),
        "- **Grade distributions:** "
        f"`REV_A` = {val_a['grade_distribution']}; `REV_B` = {val_b['grade_distribution']}.",
    ]
    (REPORTS_DIR / "S5C2_ANNOTATION_VALIDATION_REPORT.md").write_text("\n".join(val_lines) + "\n", encoding="utf-8")

    # 2. Produce S5C2_INTER_ANNOTATOR_AGREEMENT.md
    agr_lines = [
        "# S5-C2 Descriptive Agreement Report (Pre-Adjudication)",
        "",
        "**Date:** 2026-11-19",
        f"**Evaluated Pool:** `{pool['version']}` (254 pairs)",
        "",
        "> [!IMPORTANT]",
        "> **Descriptive Agreement Only:** Because Reviewer B's submission carries AI-assisted proposed annotations (`254/254` items) without documented independent human re-grading, the statistics below represent **descriptive agreement between the submitted annotation sets**, NOT validated inter-human reliability.",
        "",
        "## 1. Overall Agreement Metrics",
        "",
        f"- **Exact Raw Agreement:** **{raw_agree_count} / {len(y_a)} ({raw_agree_pct}%)**",
        f"- **Disagreements Requiring Adjudication:** **{len(disagreements)} / {len(y_a)}**",
        f"- **Cohen's Weighted Kappa (Quadratic):** **`{kappa_quad}`**",
        f"- **Cohen's Unweighted Kappa:** `{kappa_unweighted}`",
        "",
        "## 2. Confusion Matrix (Rows = `REV_A`, Columns = `REV_B`)",
        "",
        "| `REV_A` \\ `REV_B` | Grade 0 | Grade 1 | Grade 2 | Row Total |",
        "|---|---:|---:|---:|---:|",
        f"| **Grade 0** | {conf_mat[0][0]} | {conf_mat[0][1]} | {conf_mat[0][2]} | {sum(conf_mat[0])} |",
        f"| **Grade 1** | {conf_mat[1][0]} | {conf_mat[1][1]} | {conf_mat[1][2]} | {sum(conf_mat[1])} |",
        f"| **Grade 2** | {conf_mat[2][0]} | {conf_mat[2][1]} | {conf_mat[2][2]} | {sum(conf_mat[2])} |",
        f"| **Col Total** | {sum(conf_mat[r][0] for r in range(3))} | {sum(conf_mat[r][1] for r in range(3))} | {sum(conf_mat[r][2] for r in range(3))} | {len(y_a)} |",
        "",
        "## 3. Grade & Confidence Distributions",
        "",
        f"- **Reviewer A Grades:** `0`: {val_a['grade_distribution'].get(0, 0)}, `1`: {val_a['grade_distribution'].get(1, 0)}, `2`: {val_a['grade_distribution'].get(2, 0)} | Confidence: {val_a['confidence_distribution']}",
        f"- **Reviewer B Grades:** `0`: {val_b['grade_distribution'].get(0, 0)}, `1`: {val_b['grade_distribution'].get(1, 0)}, `2`: {val_b['grade_distribution'].get(2, 0)} | Confidence: {val_b['confidence_distribution']}",
        "",
        "## 4. Per-Query Agreement & Disagreement Breakdown",
        "",
        "| Query ID | Total Pairs | Agree | Disagree | Agreement % |",
        "|---|---:|---:|---:|---:|",
    ]
    for qid in sorted(per_query_stats.keys()):
        st = per_query_stats[qid]
        pct = round(100.0 * st["agree"] / st["total"], 1)
        agr_lines.append(f"| `{qid}` | {st['total']} | {st['agree']} | {st['disagree']} | {pct}% |")

    agr_lines.extend([
        "",
        "## 5. Readiness Decision",
        "",
        "**Decision:** `HOLD_FOR_DISAGREEMENT_ADJUDICATION_AND_REV_B_INDEPENDENCE_CHECK` — Do NOT compute final retrieval metrics or proceed to S5-D until all disagreements are human-adjudicated and Reviewer B's human confirmation is documented.",
    ])
    (REPORTS_DIR / "S5C2_INTER_ANNOTATOR_AGREEMENT.md").write_text("\n".join(agr_lines) + "\n", encoding="utf-8")

    # 3. Produce private S5C2_DISAGREEMENT_ADJUDICATION.md (gitignored)
    dis_lines = [
        "# S5-C2 Private Disagreement Adjudication Docket",
        "",
        "**Status:** PENDING HUMAN ADJUDICATION (Do NOT auto-resolve by majority, higher/lower grade, or AI verdict)",
        f"**Total Disagreements:** {len(disagreements)} / {len(y_a)}",
        "",
        "---",
        "",
    ]
    for d in disagreements:
        dis_lines.extend([
            f"## `{d['pair_id']}` — Query `{d['query_id']}` [{d['domain']}]",
            "",
            f"**Query:** *\"{d['query_text']}\"*",
            "",
            f"**Passage ID:** `{d['passage_id']}`",
            "",
            "**Verified Source Passage Text:**",
            f"> {d['source_text']}",
            "",
            "| Field | Reviewer A (`REV_A`) | Reviewer B (`REV_B`) |",
            "|---|---|---|",
            f"| **Grade** | `{d['rev_a']['grade']}` | `{d['rev_b']['grade']}` |",
            f"| **Confidence** | `{d['rev_a']['confidence']}` | `{d['rev_b']['confidence']}` |",
            f"| **Evidence Quote** | {d['rev_a']['quote'] or '_empty_'} | {d['rev_b']['quote'] or '_empty_'} |",
            f"| **Notes** | {d['rev_a']['notes'] or '_empty_'} | {d['rev_b']['notes'] or '_empty_'} |",
            "",
            "**Human Adjudicator Fields (LEAVE BLANK UNTIL ADJUDICATED):**",
            "- **final_adjudicated_grade (0 | 1 | 2):** ",
            "- **adjudicator_id:** ",
            "- **adjudication_evidence_quote:** ",
            "- **adjudication_rationale:** ",
            "- **adjudication_status:** ",
            "",
            "---",
            "",
        ])
    (LOCAL_OUT / "S5C2_DISAGREEMENT_ADJUDICATION.md").write_text("\n".join(dis_lines), encoding="utf-8")

    # 4. Produce Task 5 Negative-Control Verification Sheet (Public metadata + Private local)
    with open(NEG_AUDIT_JSON, encoding="utf-8") as f:
        neg_audit = json.load(f)

    neg_pub_lines = [
        "# S5-C2 Negative-Control Human Verification Sheet",
        "",
        "**Status:** `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_HUMAN_VERIFICATION`",
        "",
        "Evaluators must independently classify each provisional negative query into one of four categories:",
        "- `NO_ANSWER_IN_SELECTED_PASSAGES`",
        "- `NO_ANSWER_IN_FROZEN_CORPUS`",
        "- `AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION`",
        "- `QUESTION_REQUIRING_REVISION`",
        "",
        "---",
        "",
    ]
    neg_loc_lines = list(neg_pub_lines)

    for nq in neg_audit["queries"]:
        qid = nq["query_id"]
        q_pairs = [expected_by_pair[p] for p in sorted(expected_by_pair) if expected_by_pair[p]["query_id"] == qid]
        pos_a = [p["pair_id"] for p in q_pairs if by_pair_a[p["pair_id"]]["grade"] in {1, 2}]
        pos_b = [p["pair_id"] for p in q_pairs if by_pair_b[p["pair_id"]]["grade"] in {1, 2}]
        dist_a = dict(sorted(collections.Counter(by_pair_a[p["pair_id"]]["grade"] for p in q_pairs).items()))
        dist_b = dict(sorted(collections.Counter(by_pair_b[p["pair_id"]]["grade"] for p in q_pairs).items()))

        block = [
            f"## `{qid}` (Legacy `{nq['legacy_query_id']}`)",
            f"- **Query:** *\"{nq['query_text']}\"*",
            f"- **Pooled Pairs Graded:** {len(q_pairs)}",
            f"- **Reviewer A Grade Distribution:** {dist_a} (Pairs graded 1/2: {pos_a or 'None'})",
            f"- **Reviewer B Grade Distribution:** {dist_b} (Pairs graded 1/2: {pos_b or 'None'})",
            f"- **Search-Selected Candidates Inspected:** {len(nq['search_selected_candidate_passage_ids'])} passages",
            "- **Human Verification Fields (EMPTY):**",
            "  - `human_answerability_classification`: `[ NO_ANSWER_IN_SELECTED_PASSAGES | NO_ANSWER_IN_FROZEN_CORPUS | AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION | QUESTION_REQUIRING_REVISION ]`",
            "  - `verifier_id`: ",
            "  - `checked_passage_ids`: ",
            "  - `verification_rationale`: ",
            "",
        ]
        neg_pub_lines.extend(block)
        neg_loc_lines.extend(block)
        neg_loc_lines.append("**Search-Selected Candidate Excerpts for Human Inspection:**\n")
        for spid in nq["search_selected_candidate_passage_ids"]:
            neg_loc_lines.append(f"- `{spid}`: > {corpus_by_id[spid].text}\n")
        neg_loc_lines.append("\n---\n")

    (REPORTS_DIR / "S5C2_NEGATIVE_CONTROL_VERIFICATION.md").write_text("\n".join(neg_pub_lines), encoding="utf-8")
    (LOCAL_OUT / "S5C2_NEGATIVE_CONTROL_VERIFICATION_LOCAL.md").write_text("\n".join(neg_loc_lines), encoding="utf-8")

    print(f"Parsed REV_A: {len(entries_a)} pairs, REV_B: {len(entries_b)} pairs")
    print(f"Raw agreement: {raw_agree_count}/{len(y_a)} ({raw_agree_pct}%), Quadratic Kappa: {kappa_quad}")
    print(f"Disagreements: {len(disagreements)}")
    print(f"Quote mismatches — REV_A: {len(val_a['quote_mismatches'])}, REV_B: {len(val_b['quote_mismatches'])}")


if __name__ == "__main__":
    main()

"""A/C inter-annotator comparison, blank worksheet generation, and gold v2 assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import (
    ADJUDICATION_SOURCE_ADJUDICATED,
    ADJUDICATION_SOURCE_AGREEMENT,
    FLOAT_ROUND_DIGITS,
    GOLD_STATUS_AC_V2_FINAL,
    GRADE_HIGH,
    GRADE_IRRELEVANT,
    GRADE_PARTIAL,
    LEGACY_REV_B_PRESERVED_SHA256,
    MAX_GRADE_SPAN_SQUARED,
    PROVENANCE_AI_ASSISTED,
    ROLE_REV_A,
    ROLE_REV_B,
    ROLE_REV_C,
    SCHEMA_VERSION_AC_V2,
    WORKSHEET_SCHEMA_VERSION,
    WORKSHEET_STATUS_BLANK,
)
from .pool_index import FrozenPool
from .provenance import (
    validate_investigator_signoff,
    validate_negative_control_verifications,
)
from .validation import (
    ACValidationError,
    validate_adjudication_worksheet,
    validate_gold_v2_payload,
    validate_reviewer_submission,
)

_GRADE_VALUES = (GRADE_IRRELEVANT, GRADE_PARTIAL, GRADE_HIGH)


def compute_inter_annotator_agreement(
    rev_a: dict[str, dict[str, Any]],
    rev_c: dict[str, dict[str, Any]],
    pool: FrozenPool,
) -> dict[str, Any]:
    """Compute exact agreement, unweighted kappa, quadratic weighted kappa, and per-query stats."""
    total = pool.pair_count
    matrix: dict[tuple[int, int], int] = {
        (ga, gc): 0 for ga in _GRADE_VALUES for gc in _GRADE_VALUES
    }
    per_query_totals: dict[str, int] = {}
    per_query_agree: dict[str, int] = {}

    for pid in pool.ordered_pair_ids:
        entry = pool.entries_by_pair_id[pid]
        ga = int(rev_a[pid]["relevance_grade"])
        gc = int(rev_c[pid]["relevance_grade"])
        matrix[(ga, gc)] += 1
        per_query_totals[entry.query_id] = per_query_totals.get(entry.query_id, 0) + 1
        if ga == gc:
            per_query_agree[entry.query_id] = per_query_agree.get(entry.query_id, 0) + 1

    exact_agree = sum(matrix[(g, g)] for g in _GRADE_VALUES)
    disagreements = total - exact_agree
    po = exact_agree / total if total > 0 else 0.0

    margin_a = {g: sum(matrix[(g, gc)] for gc in _GRADE_VALUES) for g in _GRADE_VALUES}
    margin_c = {g: sum(matrix[(ga, g)] for ga in _GRADE_VALUES) for g in _GRADE_VALUES}

    pe_unweighted = (
        sum((margin_a[g] / total) * (margin_c[g] / total) for g in _GRADE_VALUES)
        if total > 0
        else 0.0
    )
    kappa_unweighted: float | None = (
        round((po - pe_unweighted) / (1.0 - pe_unweighted), FLOAT_ROUND_DIGITS)
        if pe_unweighted < 1.0
        else None
    )

    obs_weighted_disagreement = 0.0
    exp_weighted_disagreement = 0.0
    if total > 0:
        for ga in _GRADE_VALUES:
            for gc in _GRADE_VALUES:
                weight = ((ga - gc) ** 2) / MAX_GRADE_SPAN_SQUARED
                obs_weighted_disagreement += weight * (matrix[(ga, gc)] / total)
                exp_weighted_disagreement += weight * (
                    (margin_a[ga] / total) * (margin_c[gc] / total)
                )

    kappa_quad: float | None = (
        round(1.0 - (obs_weighted_disagreement / exp_weighted_disagreement), FLOAT_ROUND_DIGITS)
        if exp_weighted_disagreement > 0.0
        else None
    )

    confusion = {
        f"A{ga}_C{gc}": matrix[(ga, gc)] for ga in _GRADE_VALUES for gc in _GRADE_VALUES
    }
    per_query = {
        qid: {
            "total_pairs": cnt,
            "exact_agreement": per_query_agree.get(qid, 0),
            "disagreements": cnt - per_query_agree.get(qid, 0),
            "exact_agreement_rate": round(per_query_agree.get(qid, 0) / cnt, FLOAT_ROUND_DIGITS),
        }
        for qid, cnt in sorted(per_query_totals.items())
    }

    return {
        "total_pairs": total,
        "exact_agreement_count": exact_agree,
        "disagreement_count": disagreements,
        "exact_agreement_rate": round(po, FLOAT_ROUND_DIGITS),
        "cohens_kappa_unweighted": kappa_unweighted,
        "cohens_kappa_quadratic_weighted": kappa_quad,
        "confusion_matrix": confusion,
        "per_query_agreement": per_query,
    }


def extract_ac_disagreements(
    rev_a: dict[str, dict[str, Any]],
    rev_c: dict[str, dict[str, Any]],
    pool: FrozenPool,
) -> list[dict[str, Any]]:
    """Extract all pairs where valid REV_A and REV_C disagree, with blank human fields."""
    disagreements: list[dict[str, Any]] = []
    for pid in pool.ordered_pair_ids:
        row_a = rev_a[pid]
        row_c = rev_c[pid]
        ga = int(row_a["relevance_grade"])
        gc = int(row_c["relevance_grade"])
        if ga == gc:
            continue
        entry = pool.entries_by_pair_id[pid]
        passage_text = entry.passage_text or row_a.get("passage_text") or row_c.get("passage_text")
        disagreements.append(
            {
                "pair_id": pid,
                "query_id": entry.query_id,
                "domain": entry.domain,
                "query_text": entry.query_text,
                "passage_id": entry.passage_id,
                "doc_id": entry.doc_id,
                "chunk_id": entry.chunk_id,
                "page_number": entry.page_number,
                "passage_sha256": entry.passage_sha256,
                "passage_text": passage_text or "",
                "reviewer_a": {
                    "relevance_grade": ga,
                    "supporting_quotation": str(row_a.get("supporting_quotation", "")),
                    "confidence": str(row_a.get("confidence", "")),
                    "reviewer_notes": str(row_a.get("reviewer_notes", "")),
                },
                "reviewer_c": {
                    "relevance_grade": gc,
                    "supporting_quotation": str(row_c.get("supporting_quotation", "")),
                    "confidence": str(row_c.get("confidence", "")),
                    "reviewer_notes": str(row_c.get("reviewer_notes", "")),
                },
                "adjudicated_grade": None,
                "adjudication_evidence_quote": "",
                "adjudication_rationale": "",
                "adjudicator_id": "",
                "decision_timestamp_utc": "",
            }
        )
    return disagreements


def build_blank_adjudication_worksheet(
    rev_a_payload: dict[str, Any],
    rev_c_payload: dict[str, Any],
    pool: FrozenPool,
    *,
    rev_a_sha256: str,
    rev_c_sha256: str,
) -> dict[str, Any]:
    """Validate both REV_A and REV_C submissions and generate a blank A/C worksheet.

    Refuses to generate any disagreement list unless BOTH A and C pass complete validation.
    Never auto-populates adjudicated grades, rationales, or human provenance.
    """
    rev_a = validate_reviewer_submission(rev_a_payload, pool, expected_role=ROLE_REV_A)
    rev_c = validate_reviewer_submission(rev_c_payload, pool, expected_role=ROLE_REV_C)
    agreement = compute_inter_annotator_agreement(rev_a, rev_c, pool)
    disagreements = extract_ac_disagreements(rev_a, rev_c, pool)

    return {
        "schema_version": WORKSHEET_SCHEMA_VERSION,
        "status": WORKSHEET_STATUS_BLANK,
        "generated_utc": datetime.now(UTC).isoformat(),
        "pool_version": pool.version,
        "pool_sha256": pool.pool_sha256,
        "reviewer_a_submission_sha256": rev_a_sha256,
        "reviewer_c_submission_sha256": rev_c_sha256,
        "inter_annotator_agreement": agreement,
        "adjudicator_provenance": {
            "adjudicator_id": "",
            "provenance_class": "",
            "assistance_declaration": "",
            "human_attestation_signed": False,
            "attestation_signer": "",
            "signed_timestamp_utc": "",
        },
        "disagreements_count": len(disagreements),
        "disagreements": disagreements,
    }


def render_adjudication_worksheet_markdown(worksheet: dict[str, Any]) -> str:
    """Render a blank or in-progress A/C adjudication worksheet as structured Markdown."""
    agreement = worksheet["inter_annotator_agreement"]
    lines = [
        "# S5-C3 — Independent A/C Disagreement Adjudication Worksheet",
        "",
        f"- **Status:** `{worksheet['status']}`",
        f"- **Pool Version:** `{worksheet['pool_version']}`",
        f"- **Pool SHA-256:** `{worksheet['pool_sha256']}`",
        f"- **Total Pairs:** {agreement['total_pairs']}",
        f"- **Exact Agreement:** {agreement['exact_agreement_count']} ({agreement['exact_agreement_rate']})",
        f"- **Disagreements Requiring Human Adjudication:** {worksheet['disagreements_count']}",
        "",
        "## Human Adjudicator Provenance (Must Be Completed & Signed By Human)",
        "",
        "- `adjudicator_id`: ",
        "- `provenance_class`: `ADJUDICATED_HUMAN`",
        "- `assistance_declaration`: `NONE_INDEPENDENT_HUMAN`",
        "- `human_attestation_signed`: `false`",
        "- `attestation_signer`: ",
        "- `signed_timestamp_utc`: ",
        "",
        "---",
        "",
    ]

    for idx, item in enumerate(worksheet["disagreements"], start=1):
        lines.extend(
            [
                f"## Item {idx}: `{item['pair_id']}` (`{item['query_id']}`)",
                "",
                f"- **Query:** {item['query_text']}",
                f"- **Passage ID:** `{item['passage_id']}` (`sha256: {item['passage_sha256']}`)",
                f"- **REV_A Grade:** `{item['reviewer_a']['relevance_grade']}` | Quote: `{item['reviewer_a']['supporting_quotation']}`",
                f"- **REV_C Grade:** `{item['reviewer_c']['relevance_grade']}` | Quote: `{item['reviewer_c']['supporting_quotation']}`",
                "- **adjudicated_grade (0 | 1 | 2):** ",
                "- **adjudication_evidence_quote (verbatim for 1/2; blank for 0):** ",
                "- **adjudication_rationale (required human rationale):** ",
                "- **adjudicator_id:** ",
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def assemble_gold_v2(
    *,
    rev_a_payload: dict[str, Any],
    rev_c_payload: dict[str, Any],
    worksheet_payload: dict[str, Any],
    neg_controls_payload: dict[str, Any],
    investigator_signoff_payload: dict[str, Any],
    pool: FrozenPool,
    rev_a_sha256: str,
    rev_c_sha256: str,
    worksheet_sha256: str | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Assemble and validate final `s5d1_adjudicated_gold_ac_v2` payload.

    Refuses unless REV_A, REV_C, human adjudication (if any disagreements),
    negative-control verifications, and human investigator sign-off all pass.
    """
    rev_a = validate_reviewer_submission(rev_a_payload, pool, expected_role=ROLE_REV_A)
    rev_c = validate_reviewer_submission(rev_c_payload, pool, expected_role=ROLE_REV_C)
    agreement = compute_inter_annotator_agreement(rev_a, rev_c, pool)
    disagreement_pairs = [
        pid
        for pid in pool.ordered_pair_ids
        if int(rev_a[pid]["relevance_grade"]) != int(rev_c[pid]["relevance_grade"])
    ]
    resolved = validate_adjudication_worksheet(worksheet_payload, disagreement_pairs, pool)

    neg_errors = validate_negative_control_verifications(neg_controls_payload)
    signoff_errors = validate_investigator_signoff(investigator_signoff_payload)
    if neg_errors or signoff_errors:
        raise ACValidationError(
            "Gold v2 prerequisites failed:\n- " + "\n- ".join(neg_errors + signoff_errors)
        )

    judgments: list[dict[str, Any]] = []
    for pid in pool.ordered_pair_ids:
        entry = pool.entries_by_pair_id[pid]
        row_a = rev_a[pid]
        row_c = rev_c[pid]
        ga = int(row_a["relevance_grade"])
        gc = int(row_c["relevance_grade"])

        if ga == gc:
            quote = str(row_a.get("supporting_quotation", "")) or str(
                row_c.get("supporting_quotation", "")
            )
            judgments.append(
                {
                    "pair_id": pid,
                    "query_id": entry.query_id,
                    "passage_id": entry.passage_id,
                    "passage_sha256": entry.passage_sha256,
                    "reviewer_a_grade": ga,
                    "reviewer_c_grade": gc,
                    "final_grade": ga,
                    "adjudication_source": ADJUDICATION_SOURCE_AGREEMENT,
                    "supporting_quotation": quote,
                    "adjudication_rationale": None,
                    "adjudicator_id": None,
                }
            )
        else:
            adj = resolved[pid]
            judgments.append(
                {
                    "pair_id": pid,
                    "query_id": entry.query_id,
                    "passage_id": entry.passage_id,
                    "passage_sha256": entry.passage_sha256,
                    "reviewer_a_grade": ga,
                    "reviewer_c_grade": gc,
                    "final_grade": int(adj["adjudicated_grade"]),
                    "adjudication_source": ADJUDICATION_SOURCE_ADJUDICATED,
                    "supporting_quotation": str(adj.get("adjudication_evidence_quote", "")),
                    "adjudication_rationale": str(adj["adjudication_rationale"]).strip(),
                    "adjudicator_id": str(adj["adjudicator_id"]).strip(),
                }
            )

    prov_a = dict(rev_a_payload["provenance"])
    prov_a["submission_sha256"] = rev_a_sha256
    prov_c = dict(rev_c_payload["provenance"])
    prov_c["submission_sha256"] = rev_c_sha256

    gold_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_AC_V2,
        "status": GOLD_STATUS_AC_V2_FINAL,
        "pool_version": pool.version,
        "pool_sha256": pool.pool_sha256,
        "primary_human_assessor_pair": [ROLE_REV_A, ROLE_REV_C],
        "historical_reviewer_b_excluded_from_gold": True,
        "legacy_reviewer_b_provenance": {
            "reviewer_id": ROLE_REV_B,
            "provenance_class": PROVENANCE_AI_ASSISTED,
            "excluded_from_gold": True,
            "legacy_v1_contract_preserved": True,
            "preserved_workbook_sha256": LEGACY_REV_B_PRESERVED_SHA256,
            "notes": (
                "Historical Reviewer B disclosed AI assistance on 254/254 pairs; "
                "preserved unchanged for audit traceability and excluded from A/C v2 gold."
            ),
        },
        "reviewer_a_provenance": prov_a,
        "reviewer_c_provenance": prov_c,
        "inter_annotator_agreement": agreement,
        "adjudication_summary": {
            "all_ac_disagreements_adjudicated": True,
            "total_disagreements": len(disagreement_pairs),
            "adjudicated_count": len(resolved),
            "adjudication_worksheet_sha256": worksheet_sha256,
            "adjudicator_provenance": dict(worksheet_payload["adjudicator_provenance"]),
        },
        "investigator_signoff": dict(investigator_signoff_payload),
        "negative_control_verifications": dict(neg_controls_payload),
        "judgments": judgments,
    }

    validate_gold_v2_payload(gold_payload, pool, schema_path=schema_path)
    return gold_payload

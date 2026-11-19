"""Generator for S5-v3.1 blinded human query-audit workbooks & JSON Schema."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .constants import (
    AUDIT_SCHEMA_VERSION,
    BLINDING_SALT,
    DECISION_ACCEPT,
    DECISION_REJECT,
    DECISION_REVISE,
    EXCERPT_MAX_CHARS,
    PROVISIONAL_STATUS,
    VALID_NC_CLASSIFICATIONS,
    WORKBOOK_STATUS_BLANK,
    WORKBOOK_STATUS_SUBMITTED,
)
from .corpus_index import compute_file_sha256


def _blind_sort_key(query_id: str) -> str:
    raw = f"{BLINDING_SALT}::{query_id}".encode()
    return hashlib.sha256(raw).hexdigest()


def _load_passages(corpus_jsonl: Path) -> dict[str, dict[str, Any]]:
    passages: dict[str, dict[str, Any]] = {}
    with corpus_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rec = json.loads(stripped)
            passages[str(rec["passage_id"])] = rec
    return passages


def build_audit_json_schema() -> dict[str, Any]:
    """Build the public JSON Schema for S5-v3.1 blinded query-audit workbooks."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "S5-v3.1 Blinded Human Query Audit Workbook",
        "type": "object",
        "required": [
            "schema_version",
            "workbook_status",
            "blinding_policy",
            "proposed_manifest_sha256",
            "corpus_v31_jsonl_sha256",
            "reviewer_attestation",
            "items",
        ],
        "properties": {
            "schema_version": {"const": AUDIT_SCHEMA_VERSION},
            "workbook_status": {
                "enum": [WORKBOOK_STATUS_BLANK, WORKBOOK_STATUS_SUBMITTED]
            },
            "reviewer_attestation": {
                "type": "object",
                "required": [
                    "reviewer_id",
                    "assistance_declaration",
                    "reviewer_attestation_signed",
                    "attestation_signer",
                    "signed_timestamp_utc",
                ],
                "properties": {
                    "reviewer_id": {"type": "string"},
                    "assistance_declaration": {"type": "string"},
                    "reviewer_attestation_signed": {"type": "boolean"},
                    "attestation_signer": {"type": "string"},
                    "signed_timestamp_utc": {"type": "string"},
                },
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "blinded_item_id",
                        "query_id",
                        "query_text",
                        "proposed_category",
                        "category_status",
                        "domain",
                        "evidence_references",
                        "claimed_passage_necessity",
                        "potential_single_passage_shortcut",
                        "source_provenance_concerns",
                        "human_decision",
                        "human_necessity_verified",
                        "human_shortcut_found",
                        "human_negative_control_classification",
                        "human_correction_or_rationale",
                    ],
                    "properties": {
                        "category_status": {"const": PROVISIONAL_STATUS},
                        "human_decision": {
                            "enum": [
                                "",
                                DECISION_ACCEPT,
                                DECISION_REVISE,
                                DECISION_REJECT,
                            ]
                        },
                        "human_necessity_verified": {
                            "enum": ["", "YES", "NO", "NA"]
                        },
                        "human_shortcut_found": {
                            "enum": ["", "YES", "NO", "NA"]
                        },
                        "human_negative_control_classification": {
                            "enum": ["", *sorted(VALID_NC_CLASSIFICATIONS)]
                        },
                        "human_correction_or_rationale": {"type": "string"},
                    },
                },
            },
        },
    }


def _derive_concerns(
    query: dict[str, Any], corpus: dict[str, dict[str, Any]]
) -> list[str]:
    concerns: list[str] = [
        "AI_PROPOSED_CANDIDATE: authored with corpus visibility; verify "
        "naturalness, domain balance, and absence of lexical cueing."
    ]
    if query["category"] == "negative_control":
        concerns.append(
            "NEGATIVE_CONTROL_UNVERIFIED: absence checked by programmatic "
            "scan only; human must classify true unanswerability."
        )
        return concerns

    for ev in query.get("supporting_evidence", []):
        pid = str(ev["passage_id"])
        rec = corpus.get(pid, {})
        flags = rec.get("quality_flags", [])
        if flags:
            concerns.append(
                f"CORPUS_QUALITY_FLAG ({pid}): {', '.join(flags)}."
            )
        if ev.get("page_start") is None:
            concerns.append(
                f"WEB_OR_MARKDOWN_SECTION_REF ({pid}): source has section "
                "reference without PDF pagination (page_start=null)."
            )
    return concerns


def _build_item(
    blinded_item_id: str,
    query: dict[str, Any],
    corpus: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    evs: list[dict[str, Any]] = []
    for ev in query.get("supporting_evidence", []):
        pid = str(ev["passage_id"])
        rec = corpus.get(pid, {})
        raw_text = str(rec.get("text", "")).strip()
        excerpt = (
            raw_text[:EXCERPT_MAX_CHARS] + "..."
            if len(raw_text) > EXCERPT_MAX_CHARS
            else raw_text
        )
        evs.append(
            {
                "passage_id": pid,
                "source_doc_id": str(ev["source_doc_id"]),
                "domain": str(ev.get("domain", "")),
                "page_start": ev.get("page_start"),
                "page_end": ev.get("page_end"),
                "section_ref": str(ev.get("section_ref", "")),
                "passage_sha256": str(ev["passage_sha256"]),
                "corpus_quality_flags": list(rec.get("quality_flags", [])),
                "passage_excerpt": excerpt,
            }
        )
    sc = query.get("single_passage_shortcut_check", {})
    return {
        "blinded_item_id": blinded_item_id,
        "query_id": str(query["query_id"]),
        "query_text": str(query["query_text"]),
        "proposed_category": str(query["category"]),
        "category_status": PROVISIONAL_STATUS,
        "domain": str(query["domain"]),
        "domain_topic": str(query["domain_topic"]),
        "exact_information_need": str(query["exact_information_need"]),
        "evidence_references": evs,
        "claimed_passage_necessity": {
            "minimum_required_evidence_set": list(
                query.get("minimum_required_evidence_set", [])
            ),
            "multi_document_truly_necessary": bool(
                query.get("multi_document_truly_necessary", False)
            ),
            "necessity_status": PROVISIONAL_STATUS,
        },
        "potential_single_passage_shortcut": {
            "ai_claimed_shortcut_found": bool(sc.get("shortcut_found", False)),
            "ai_shortcut_rationale": str(sc.get("rationale", "")),
        },
        "source_provenance_concerns": _derive_concerns(query, corpus),
        "human_decision": "",
        "human_necessity_verified": "",
        "human_shortcut_found": "",
        "human_negative_control_classification": "",
        "human_correction_or_rationale": "",
    }


def _render_md(payload: dict[str, Any]) -> str:
    lines: list[str] = [
        "# S5-v3.1 Blinded Human Query Audit Workbook (PRIVATE — DO NOT COMMIT)",
        "",
        f"- **Schema Version:** `{payload['schema_version']}`",
        f"- **Status:** `{payload['workbook_status']}`",
        f"- **Proposed Manifest SHA-256:** `{payload['proposed_manifest_sha256']}`",
        f"- **Corpus v3.1 JSONL SHA-256:** `{payload['corpus_v31_jsonl_sha256']}`",
        "- **Blinding:** Order is deterministically shuffled; `split` and "
        "`graph_anchor_regime` are hidden. **Zero relevance grades** included.",
        "",
        "## Reviewer Attestation (Complete Independently Before Submission)",
        "- `reviewer_id`: `____________________`",
        "- `assistance_declaration`: `NONE_INDEPENDENT_HUMAN`",
        "- `reviewer_attestation_signed`: `[ ] true`",
        "- `attestation_signer`: `____________________`",
        "- `signed_timestamp_utc`: `____________________`",
        "",
        "---",
        "",
    ]
    for item in payload["items"]:
        lines.append(f"## {item['blinded_item_id']} (`{item['query_id']}`)")
        lines.append(f"- **Domain:** {item['domain']} ({item['domain_topic']})")
        lines.append(f"- **Question:** {item['query_text']}")
        lines.append(
            f"- **Provisional Category:** `{item['proposed_category']}` "
            f"(`{item['category_status']}`)"
        )
        lines.append(
            f"- **Exact Information Need:** {item['exact_information_need']}"
        )
        nec = item["claimed_passage_necessity"]
        lines.append(
            "- **Claimed Necessity (Provisional):** "
            f"`min_required={nec['minimum_required_evidence_set']}`, "
            f"`multi_doc={nec['multi_document_truly_necessary']}`"
        )
        sc = item["potential_single_passage_shortcut"]
        lines.append(
            "- **Shortcut Check (AI Claim):** "
            f"`shortcut_found={sc['ai_claimed_shortcut_found']}` — "
            f"{sc['ai_shortcut_rationale']}"
        )
        lines.append("- **Source-Provenance Concerns:**")
        for c in item["source_provenance_concerns"]:
            lines.append(f"  - {c}")
        lines.append("- **Evidence Passages:**")
        if not item["evidence_references"]:
            lines.append("  - *(None — proposed negative control)*")
        for ev in item["evidence_references"]:
            loc = (
                f"pp. {ev['page_start']}-{ev['page_end']}"
                if ev["page_start"] is not None
                else f"section '{ev['section_ref']}'"
            )
            lines.append(
                f"  - `{ev['passage_id']}` (`{ev['source_doc_id']}`, {loc}, "
                f"sha256 `{ev['passage_sha256'][:12]}...`)"
            )
            excerpt = str(ev["passage_excerpt"]).replace("\n", " ")
            lines.append(f"    > {excerpt}")
        lines.extend(
            [
                "",
                "### Human Decision (BLANK)",
                "- `human_decision` (`ACCEPT`/`REVISE`/`REJECT`): `______`",
                "- `human_necessity_verified` (`YES`/`NO`/`NA`): `______`",
                "- `human_shortcut_found` (`YES`/`NO`/`NA`): `______`",
                "- `human_negative_control_classification`: `______`",
                "- `human_correction_or_rationale`: `______________________`",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def _write_csv(payload: dict[str, Any], csv_path: Path) -> None:
    fieldnames = [
        "blinded_item_id",
        "query_id",
        "domain",
        "proposed_category",
        "query_text",
        "evidence_passage_ids",
        "evidence_locations",
        "multi_document_truly_necessary",
        "ai_claimed_shortcut_found",
        "human_decision",
        "human_necessity_verified",
        "human_shortcut_found",
        "human_negative_control_classification",
        "human_correction_or_rationale",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in payload["items"]:
            evs = item["evidence_references"]
            locs = "; ".join(
                f"p.{e['page_start']}-{e['page_end']}"
                if e["page_start"] is not None
                else f"sec:{e['section_ref']}"
                for e in evs
            )
            writer.writerow(
                {
                    "blinded_item_id": item["blinded_item_id"],
                    "query_id": item["query_id"],
                    "domain": item["domain"],
                    "proposed_category": item["proposed_category"],
                    "query_text": item["query_text"],
                    "evidence_passage_ids": "; ".join(
                        e["passage_id"] for e in evs
                    ),
                    "evidence_locations": locs,
                    "multi_document_truly_necessary": item[
                        "claimed_passage_necessity"
                    ]["multi_document_truly_necessary"],
                    "ai_claimed_shortcut_found": item[
                        "potential_single_passage_shortcut"
                    ]["ai_claimed_shortcut_found"],
                    "human_decision": "",
                    "human_necessity_verified": "",
                    "human_shortcut_found": "",
                    "human_negative_control_classification": "",
                    "human_correction_or_rationale": "",
                }
            )


def generate_private_audit_workbooks(
    proposed_manifest_path: Path,
    corpus_jsonl_path: Path,
    private_audit_dir: Path,
    public_schema_path: Path,
) -> dict[str, Any]:
    """Generate private MD/CSV/JSON blinded workbooks and public JSON Schema."""
    manifest = json.loads(proposed_manifest_path.read_text(encoding="utf-8"))
    corpus = _load_passages(corpus_jsonl_path)
    blinded = sorted(
        manifest.get("queries", []),
        key=lambda q: _blind_sort_key(str(q["query_id"])),
    )

    payload: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "workbook_status": WORKBOOK_STATUS_BLANK,
        "blinding_policy": (
            "Queries are presented in deterministic SHA-256 blinded order. "
            "Split (dev/test) and graph_anchor_regime are omitted. "
            "No relevance grades are included. Nothing is marked validated."
        ),
        "proposed_manifest_sha256": compute_file_sha256(proposed_manifest_path),
        "corpus_v31_jsonl_sha256": compute_file_sha256(corpus_jsonl_path),
        "total_items": len(blinded),
        "reviewer_attestation": {
            "reviewer_id": "",
            "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
            "reviewer_attestation_signed": False,
            "attestation_signer": "",
            "signed_timestamp_utc": "",
        },
        "items": [
            _build_item(f"AUDIT-{idx:02d}", q, corpus)
            for idx, q in enumerate(blinded, start=1)
        ],
    }

    private_audit_dir.mkdir(parents=True, exist_ok=True)
    public_schema_path.parent.mkdir(parents=True, exist_ok=True)

    priv_json = private_audit_dir / "s5v31_query_audit_workbook.json"
    priv_csv = private_audit_dir / "s5v31_query_audit_workbook.csv"
    priv_md = private_audit_dir / "s5v31_query_audit_workbook.md"

    priv_json.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(payload, priv_csv)
    priv_md.write_text(_render_md(payload), encoding="utf-8")
    public_schema_path.write_text(
        json.dumps(build_audit_json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "total_items": len(blinded),
        "private_json": str(priv_json),
        "private_json_sha256": compute_file_sha256(priv_json),
        "private_csv": str(priv_csv),
        "private_csv_sha256": compute_file_sha256(priv_csv),
        "private_md": str(priv_md),
        "private_md_sha256": compute_file_sha256(priv_md),
        "public_schema": str(public_schema_path),
        "public_schema_sha256": compute_file_sha256(public_schema_path),
    }

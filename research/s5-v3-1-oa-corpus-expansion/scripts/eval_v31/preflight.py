"""Fail-closed preflight validator for S5-v3.1 gold labels, pool, NCs, and retrieval runs."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from eval_v31.auth_gate import is_valid_human_id
from eval_v31.constants import (
    ALL_NC_CLASSES,
    BENCHMARK_VERSION_V31,
    GOLD_SCHEMA_VERSION_V31,
    GOLD_STATUS_FINAL,
    GOLD_STATUS_SYNTHETIC,
    LEGACY_V21_POOL_MARKER,
    LEGACY_V21_QID_PREFIX,
    MIN_DECLARATION_CHARS,
    NC_CONFIRMED_UNANSWERABLE,
    NC_EXCLUDED_CLASSES,
    NC_RECLASSIFIED_ANSWERABLE,
    REQUIRED_ASSISTANCE_DECLARATION,
    REQUIRED_REVIEWER_PROVENANCE_CLASS,
    SHA256_RE,
    VALID_ADJUDICATION_SOURCES,
    VALID_ADJUDICATOR_PROVENANCE_CLASSES,
    VALID_GRADES,
    VALID_POOL_DEPTHS,
    VALID_SPLITS,
)

HASH_CHUNK_BYTES = 65536


class V31PreflightError(ValueError):
    """Raised when S5-v3.1 preflight or evaluation encounters a fail-closed integrity violation."""


@dataclass(frozen=True)
class V31PreflightFinding:
    """Single structured preflight error or warning."""

    code: str
    message: str


@dataclass
class V31PreflightResult:
    """Complete result of S5-v3.1 preflight validation."""

    passed: bool
    is_synthetic: bool = False
    pool_depth_k: int = 0
    split: str = ""
    gold_labels_sha256: str = ""
    retrieval_diagnostics_sha256: str = ""
    verified_negative_controls: list[str] = field(default_factory=list)
    reclassified_answerable_controls: list[str] = field(default_factory=list)
    excluded_negative_controls: list[str] = field(default_factory=list)
    nc_classifications: dict[str, str] = field(default_factory=dict)
    expected_hashes: dict[str, str] = field(default_factory=dict)
    errors: list[V31PreflightFinding] = field(default_factory=list)
    warnings: list[V31PreflightFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize preflight result to JSON-compatible dict."""
        return {
            "passed": self.passed,
            "is_synthetic": self.is_synthetic,
            "pool_depth_k": self.pool_depth_k,
            "split": self.split,
            "gold_labels_sha256": self.gold_labels_sha256,
            "retrieval_diagnostics_sha256": self.retrieval_diagnostics_sha256,
            "verified_negative_controls": list(self.verified_negative_controls),
            "reclassified_answerable_controls": list(self.reclassified_answerable_controls),
            "excluded_negative_controls": list(self.excluded_negative_controls),
            "nc_classifications": dict(self.nc_classifications),
            "expected_hashes": dict(self.expected_hashes),
            "errors": [{"code": e.code, "message": e.message} for e in self.errors],
            "warnings": [{"code": w.code, "message": w.message} for w in self.warnings],
        }


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _is_sha256(val: Any) -> bool:
    return isinstance(val, str) and bool(SHA256_RE.match(val))


def _check_reviewer_provenance(
    prov: Any, label: str, errors: list[V31PreflightFinding]
) -> None:
    if not isinstance(prov, dict):
        errors.append(V31PreflightFinding("MISSING_PROVENANCE", f"Missing {label}."))
        return
    if not is_valid_human_id(prov.get("reviewer_id")):
        errors.append(
            V31PreflightFinding("INVALID_PROVENANCE", f"{label}.reviewer_id invalid.")
        )
    if prov.get("provenance_class") != REQUIRED_REVIEWER_PROVENANCE_CLASS:
        errors.append(
            V31PreflightFinding(
                "INVALID_PROVENANCE",
                f"{label}.provenance_class must be {REQUIRED_REVIEWER_PROVENANCE_CLASS!r}.",
            )
        )
    if prov.get("assistance_declaration") != REQUIRED_ASSISTANCE_DECLARATION:
        errors.append(
            V31PreflightFinding(
                "INVALID_PROVENANCE",
                f"{label}.assistance_declaration must be {REQUIRED_ASSISTANCE_DECLARATION!r}.",
            )
        )
    if prov.get("human_attestation_signed") is not True:
        errors.append(
            V31PreflightFinding("UNSIGNED_PROVENANCE", f"{label}.human_attestation_signed != True.")
        )
    if not is_valid_human_id(prov.get("attestation_signer")):
        errors.append(
            V31PreflightFinding("INVALID_PROVENANCE", f"{label}.attestation_signer invalid.")
        )
    if not _is_sha256(prov.get("submission_sha256")):
        errors.append(
            V31PreflightFinding("INVALID_PROVENANCE", f"{label}.submission_sha256 invalid.")
        )


def _check_adjudication_and_signoff(
    gold: dict[str, Any],
    cfg: dict[str, Any],
    errors: list[V31PreflightFinding],
) -> None:
    adj = gold.get("adjudication_summary")
    if not isinstance(adj, dict):
        errors.append(V31PreflightFinding("UNSIGNED_ADJUDICATION", "Missing adjudication_summary."))
    else:
        if adj.get("all_disagreements_adjudicated") is not True:
            errors.append(
                V31PreflightFinding("INCOMPLETE_ADJUDICATION", "all_disagreements_adjudicated != True.")
            )
        if adj.get("adjudicated_count") != adj.get("total_disagreements"):
            errors.append(
                V31PreflightFinding(
                    "INCOMPLETE_ADJUDICATION",
                    "adjudicated_count does not match total_disagreements.",
                )
            )
        ap = adj.get("adjudicator_provenance")
        if not isinstance(ap, dict):
            errors.append(V31PreflightFinding("UNSIGNED_ADJUDICATION", "Missing adjudicator_provenance."))
        else:
            if ap.get("provenance_class") not in VALID_ADJUDICATOR_PROVENANCE_CLASSES:
                errors.append(
                    V31PreflightFinding("UNSIGNED_ADJUDICATION", "Invalid adjudicator provenance_class.")
                )
            if ap.get("assistance_declaration") != REQUIRED_ASSISTANCE_DECLARATION:
                errors.append(
                    V31PreflightFinding("UNSIGNED_ADJUDICATION", "Invalid adjudicator assistance_declaration.")
                )
            if ap.get("human_attestation_signed") is not True:
                errors.append(
                    V31PreflightFinding("UNSIGNED_ADJUDICATION", "Adjudicator attestation not signed.")
                )
            if not is_valid_human_id(ap.get("adjudicator_id")) or not is_valid_human_id(
                ap.get("attestation_signer")
            ):
                errors.append(
                    V31PreflightFinding("UNSIGNED_ADJUDICATION", "Invalid adjudicator_id or signer.")
                )

    signoff = gold.get("investigator_signoff")
    if not isinstance(signoff, dict):
        errors.append(V31PreflightFinding("INVALID_SIGNOFF", "Missing investigator_signoff."))
        return
    if signoff.get("human_signoff_confirmed") is not True:
        errors.append(V31PreflightFinding("INVALID_SIGNOFF", "investigator_signoff not confirmed."))
    if not is_valid_human_id(signoff.get("investigator_id")):
        errors.append(V31PreflightFinding("INVALID_SIGNOFF", "Invalid investigator_id in signoff."))
    for hkey in ("corpus_sha256", "query_manifest_sha256", "pool_sha256", "retrieval_manifest_sha256"):
        if signoff.get(hkey) != cfg.get(hkey):
            errors.append(
                V31PreflightFinding(
                    "HASH_MISMATCH", f"investigator_signoff.{hkey} != benchmark_config.{hkey}."
                )
            )
    if not _is_sha256(signoff.get("nc_verification_sha256")):
        errors.append(V31PreflightFinding("INVALID_SIGNOFF", "Invalid nc_verification_sha256."))


def _check_negative_controls(
    gold: dict[str, Any],
    cfg: dict[str, Any],
    result: V31PreflightResult,
) -> None:
    approved_ncs = cfg.get("approved_negative_control_ids")
    if not isinstance(approved_ncs, list):
        result.errors.append(
            V31PreflightFinding("MISSING_NEGATIVE_CONTROLS", "approved_negative_control_ids missing.")
        )
        return
    nc_map = gold.get("negative_control_verifications")
    if not isinstance(nc_map, dict):
        result.errors.append(
            V31PreflightFinding("MISSING_NEGATIVE_CONTROLS", "negative_control_verifications missing.")
        )
        return

    approved_set = set(approved_ncs)
    extra_keys = sorted(set(nc_map.keys()) - approved_set)
    if extra_keys:
        result.errors.append(
            V31PreflightFinding(
                "UNEXPECTED_NEGATIVE_CONTROLS",
                f"Unexpected NC verifications not in approved_negative_control_ids: {extra_keys}",
            )
        )

    for qid in approved_ncs:
        rec = nc_map.get(qid)
        if not isinstance(rec, dict):
            result.errors.append(
                V31PreflightFinding("MISSING_NEGATIVE_CONTROLS", f"Missing NC verification for {qid}.")
            )
            continue
        cls = rec.get("human_nc_classification")
        if cls not in ALL_NC_CLASSES:
            result.errors.append(
                V31PreflightFinding("INVALID_NC_CLASSIFICATION", f"{qid}: invalid class {cls!r}.")
            )
            continue
        if rec.get("provenance_class") != REQUIRED_REVIEWER_PROVENANCE_CLASS:
            result.errors.append(
                V31PreflightFinding("INVALID_PROVENANCE", f"{qid}: NC provenance_class not human.")
            )
        if rec.get("assistance_declaration") != REQUIRED_ASSISTANCE_DECLARATION:
            result.errors.append(
                V31PreflightFinding("INVALID_PROVENANCE", f"{qid}: NC assistance_declaration invalid.")
            )
        if rec.get("human_attestation_signed") is not True:
            result.errors.append(
                V31PreflightFinding("UNSIGNED_PROVENANCE", f"{qid}: NC attestation not signed.")
            )
        if not is_valid_human_id(rec.get("verifier_id")):
            result.errors.append(
                V31PreflightFinding("INVALID_PROVENANCE", f"{qid}: invalid NC verifier_id.")
            )
        if rec.get("corpus_sha256") != cfg.get("corpus_sha256"):
            result.errors.append(
                V31PreflightFinding("CORPUS_SHA_MISMATCH", f"{qid}: NC corpus_sha256 mismatch.")
            )
        if not isinstance(rec.get("rationale"), str) or len(rec["rationale"].strip()) < MIN_DECLARATION_CHARS:
            result.errors.append(
                V31PreflightFinding("INVALID_NC_RATIONALE", f"{qid}: NC rationale missing/too short.")
            )

        result.nc_classifications[qid] = str(cls)
        if cls in NC_CONFIRMED_UNANSWERABLE:
            result.verified_negative_controls.append(qid)
        elif cls in NC_RECLASSIFIED_ANSWERABLE:
            result.reclassified_answerable_controls.append(qid)
            result.warnings.append(
                V31PreflightFinding("NC_RECLASSIFIED", f"{qid} reclassified as answerable_in_corpus.")
            )
        elif cls in NC_EXCLUDED_CLASSES:
            result.excluded_negative_controls.append(qid)
            result.warnings.append(
                V31PreflightFinding("NC_EXCLUDED", f"{qid} excluded ({cls}).")
            )


def _check_judgments_and_topk(
    gold: dict[str, Any],
    cfg: dict[str, Any],
    retrieval_diag: dict[str, Any],
    pool_json: dict[str, Any] | None,
    errors: list[V31PreflightFinding],
) -> None:
    judgments = gold.get("judgments")
    if not isinstance(judgments, list) or not judgments:
        errors.append(V31PreflightFinding("MISSING_JUDGMENTS", "judgments array missing or empty."))
        return

    expected_pairs = int(cfg.get("expected_pair_count", -1))
    if len(judgments) != expected_pairs:
        errors.append(
            V31PreflightFinding(
                "PAIR_COUNT_MISMATCH",
                f"Expected {expected_pairs} judgments, got {len(judgments)}.",
            )
        )

    iaa = gold.get("inter_annotator_agreement")
    if isinstance(iaa, dict) and iaa.get("total_pairs") != len(judgments):
        errors.append(
            V31PreflightFinding(
                "PAIR_COUNT_MISMATCH",
                f"inter_annotator_agreement.total_pairs ({iaa.get('total_pairs')}) != {len(judgments)}.",
            )
        )

    approved_qids = set(cfg.get("approved_query_ids") or [])
    qrels_by_qid: dict[str, set[str]] = {}
    seen_pairs: set[str] = set()
    adjudicated_rows = 0

    for idx, row in enumerate(judgments):
        if not isinstance(row, dict):
            errors.append(V31PreflightFinding("INVALID_JUDGMENT", f"Judgment[{idx}] not an object."))
            continue
        pid = str(row.get("pair_id") or "")
        qid = str(row.get("query_id") or "")
        pass_id = str(row.get("passage_id") or "")
        if pid in seen_pairs:
            errors.append(V31PreflightFinding("DUPLICATE_PAIR_ID", f"Duplicate pair_id {pid}."))
        seen_pairs.add(pid)
        if qid not in approved_qids:
            errors.append(
                V31PreflightFinding("UNAPPROVED_QUERY_ID", f"Judgment {pid} references unapproved {qid}.")
            )
        for gfield in ("reviewer_a_grade", "reviewer_c_grade", "final_grade"):
            if row.get(gfield) not in VALID_GRADES:
                errors.append(
                    V31PreflightFinding("INVALID_GRADE", f"{pid}: invalid {gfield}={row.get(gfield)!r}.")
                )
        src = row.get("adjudication_source")
        if src not in VALID_ADJUDICATION_SOURCES:
            errors.append(V31PreflightFinding("INVALID_JUDGMENT", f"{pid}: invalid adjudication_source."))
        if row.get("reviewer_a_grade") != row.get("reviewer_c_grade"):
            adjudicated_rows += 1
            if src != "ADJUDICATED_HUMAN" or not is_valid_human_id(row.get("adjudicator_id")):
                errors.append(
                    V31PreflightFinding(
                        "UNSIGNED_ADJUDICATION",
                        f"{pid}: disagreement lacks signed ADJUDICATED_HUMAN adjudicator_id.",
                    )
                )
            if not str(row.get("adjudication_rationale") or "").strip():
                errors.append(
                    V31PreflightFinding("UNSIGNED_ADJUDICATION", f"{pid}: missing adjudication_rationale.")
                )
        qrels_by_qid.setdefault(qid, set()).add(pass_id)

    if pool_json is not None:
        pool_pairs = pool_json.get("pairs") or []
        if len(pool_pairs) != len(judgments):
            errors.append(
                V31PreflightFinding(
                    "PAIR_COUNT_MISMATCH",
                    f"Blinded pool has {len(pool_pairs)} pairs, gold has {len(judgments)}.",
                )
            )
        else:
            pool_key_set = {
                (str(p.get("pair_id")), str(p.get("query_id")), str(p.get("passage_id")))
                for p in pool_pairs
            }
            gold_key_set = {
                (str(r.get("pair_id")), str(r.get("query_id")), str(r.get("passage_id")))
                for r in judgments
            }
            if pool_key_set != gold_key_set:
                errors.append(
                    V31PreflightFinding(
                        "PAIR_ID_MISALIGNMENT",
                        "Gold judgment (pair_id, query_id, passage_id) set differs from blinded pool.",
                    )
                )

    # Dynamic Top-K unjudged check across all configured retrieval systems
    depth_k = int(cfg.get("pool_depth_k", 0))
    variants = retrieval_diag.get("variants") or {}
    for sys_name in sorted(cfg.get("system_hashes") or {}):
        vdata = variants.get(sys_name)
        if not isinstance(vdata, dict):
            errors.append(
                V31PreflightFinding("MISSING_SYSTEM", f"System {sys_name} missing in retrieval diagnostics.")
            )
            continue
        by_qid = {
            str(entry["query_id"]): entry for entry in (vdata.get("per_query_diagnostics") or [])
        }
        for qid in sorted(approved_qids):
            if qid not in by_qid:
                errors.append(
                    V31PreflightFinding(
                        "MISSING_QUERY_RANKING", f"{sys_name} missing ranking for approved query {qid}."
                    )
                )
                continue
            judged_pids = qrels_by_qid.get(qid, set())
            top_hits = (by_qid[qid].get("results") or [])[:depth_k]
            unjudged = [h["passage_id"] for h in top_hits if h["passage_id"] not in judged_pids]
            if unjudged:
                errors.append(
                    V31PreflightFinding(
                        "UNJUDGED_TOP_K",
                        f"{sys_name} query {qid} has {len(unjudged)} unjudged passage(s) in Top-{depth_k}.",
                    )
                )


def validate_v31_preflight(
    *,
    gold_labels_path: Path,
    retrieval_diagnostics_path: Path,
    corpus_path: Path | None = None,
    query_manifest_path: Path | None = None,
    pool_path: Path | None = None,
    retrieval_manifest_path: Path | None = None,
    nc_verification_path: Path | None = None,
    is_synthetic: bool = False,
) -> V31PreflightResult:
    """Run all fail-closed S5-v3.1 preflight integrity checks."""
    result = V31PreflightResult(passed=False, is_synthetic=is_synthetic)

    for label, path in (
        ("gold_labels_path", gold_labels_path),
        ("retrieval_diagnostics_path", retrieval_diagnostics_path),
    ):
        if not path.exists() or not path.is_file():
            result.errors.append(V31PreflightFinding("MISSING_FILE", f"Missing {label}: {path}"))
    if result.errors:
        return result

    result.gold_labels_sha256 = sha256_file(gold_labels_path)
    result.retrieval_diagnostics_sha256 = sha256_file(retrieval_diagnostics_path)

    try:
        gold = json.loads(gold_labels_path.read_text(encoding="utf-8"))
        retrieval_diag = json.loads(retrieval_diagnostics_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        result.errors.append(V31PreflightFinding("INVALID_JSON", f"JSON parse error: {exc}"))
        return result

    # Legacy mixing guard
    if gold.get("schema_version") != GOLD_SCHEMA_VERSION_V31:
        result.errors.append(
            V31PreflightFinding(
                "LEGACY_VERSION_MIXING",
                f"Expected schema_version {GOLD_SCHEMA_VERSION_V31!r}, got {gold.get('schema_version')!r}.",
            )
        )

    expected_status = GOLD_STATUS_SYNTHETIC if is_synthetic else GOLD_STATUS_FINAL
    if gold.get("status") != expected_status:
        result.errors.append(
            V31PreflightFinding(
                "INVALID_GOLD_STATUS",
                f"Expected status {expected_status!r} (is_synthetic={is_synthetic}), got {gold.get('status')!r}.",
            )
        )

    cfg = gold.get("benchmark_config")
    if not isinstance(cfg, dict):
        result.errors.append(V31PreflightFinding("INVALID_CONFIG", "Missing benchmark_config."))
        return result

    if cfg.get("benchmark_version") != BENCHMARK_VERSION_V31:
        result.errors.append(
            V31PreflightFinding(
                "LEGACY_VERSION_MIXING",
                f"Expected benchmark_version {BENCHMARK_VERSION_V31!r}, got {cfg.get('benchmark_version')!r}.",
            )
        )
    if LEGACY_V21_POOL_MARKER in str(cfg.get("pool_id") or ""):
        result.errors.append(
            V31PreflightFinding("LEGACY_VERSION_MIXING", "Legacy v2.1 pool_id rejected in v3.1.")
        )
    approved_qids = cfg.get("approved_query_ids") or []
    if any(str(q).startswith(LEGACY_V21_QID_PREFIX) for q in approved_qids):
        result.errors.append(
            V31PreflightFinding("LEGACY_VERSION_MIXING", "Legacy Q-S5B2-* query IDs rejected in v3.1.")
        )

    split = str(cfg.get("split") or "")
    if split not in VALID_SPLITS:
        result.errors.append(V31PreflightFinding("INVALID_SPLIT", f"Invalid split {split!r}."))
    result.split = split

    depth_k = cfg.get("pool_depth_k")
    if depth_k not in VALID_POOL_DEPTHS:
        result.errors.append(
            V31PreflightFinding("INVALID_POOL_DEPTH", f"pool_depth_k must be 5 or 10, got {depth_k!r}.")
        )
    else:
        result.pool_depth_k = int(depth_k)

    # Corpus SHA-256 verification
    diag_corpus_sha = (retrieval_diag.get("inputs") or {}).get("corpus_sha256")
    if diag_corpus_sha and cfg.get("corpus_sha256") != diag_corpus_sha:
        result.errors.append(
            V31PreflightFinding(
                "CORPUS_SHA_MISMATCH",
                f"benchmark_config.corpus_sha256 != retrieval_diagnostics corpus_sha256.",
            )
        )
    if corpus_path is not None:
        if not corpus_path.exists():
            result.errors.append(V31PreflightFinding("MISSING_FILE", f"Missing corpus: {corpus_path}"))
        elif sha256_file(corpus_path) != cfg.get("corpus_sha256"):
            result.errors.append(
                V31PreflightFinding("CORPUS_SHA_MISMATCH", "Actual corpus file SHA-256 mismatch.")
            )

    # Query manifest SHA-256 and split membership verification
    if query_manifest_path is not None:
        if not query_manifest_path.exists():
            result.errors.append(
                V31PreflightFinding("MISSING_FILE", f"Missing query manifest: {query_manifest_path}")
            )
        else:
            if sha256_file(query_manifest_path) != cfg.get("query_manifest_sha256"):
                result.errors.append(
                    V31PreflightFinding("QUERY_MANIFEST_SHA_MISMATCH", "Query manifest SHA-256 mismatch.")
                )
            q_manifest = json.loads(query_manifest_path.read_text(encoding="utf-8"))
            q_split_map = {
                str(q["query_id"]): str(q.get("split") or "")
                for q in (q_manifest.get("queries") or [])
            }
            allowed_splits = {"dev", "test"} if split == "dev_and_test" else {split}
            for qid in approved_qids:
                if qid not in q_split_map or q_split_map[qid] not in allowed_splits:
                    result.errors.append(
                        V31PreflightFinding(
                            "INCORRECT_QUERY_SPLIT",
                            f"Query {qid} split={q_split_map.get(qid)!r} incompatible with split={split!r}.",
                        )
                    )

    # Retrieval manifest & system config hash verification
    if retrieval_manifest_path is not None:
        if not retrieval_manifest_path.exists():
            result.errors.append(
                V31PreflightFinding("MISSING_FILE", f"Missing retrieval manifest: {retrieval_manifest_path}")
            )
        elif sha256_file(retrieval_manifest_path) != cfg.get("retrieval_manifest_sha256"):
            result.errors.append(
                V31PreflightFinding("RETRIEVAL_HASH_MISMATCH", "Retrieval manifest SHA-256 mismatch.")
            )

    diag_sys_hashes = retrieval_diag.get("variant_config_hashes") or {}
    for sys_name, expected_sys_sha in (cfg.get("system_hashes") or {}).items():
        if diag_sys_hashes.get(sys_name) != expected_sys_sha:
            result.errors.append(
                V31PreflightFinding(
                    "RANKING_HASH_MISMATCH",
                    f"System {sys_name} hash changed: config={expected_sys_sha!r}, "
                    f"diagnostics={diag_sys_hashes.get(sys_name)!r}.",
                )
            )

    pool_json: dict[str, Any] | None = None
    if pool_path is not None:
        if not pool_path.exists():
            result.errors.append(V31PreflightFinding("MISSING_FILE", f"Missing pool: {pool_path}"))
        else:
            if sha256_file(pool_path) != cfg.get("pool_sha256"):
                result.errors.append(
                    V31PreflightFinding("POOL_SHA_MISMATCH", "Blinded pool SHA-256 mismatch.")
                )
            pool_json = json.loads(pool_path.read_text(encoding="utf-8"))

    if nc_verification_path is not None:
        if not nc_verification_path.exists():
            result.errors.append(
                V31PreflightFinding("MISSING_FILE", f"Missing NC verification file: {nc_verification_path}")
            )
        else:
            signoff_nc_sha = (gold.get("investigator_signoff") or {}).get("nc_verification_sha256")
            if sha256_file(nc_verification_path) != signoff_nc_sha:
                result.errors.append(
                    V31PreflightFinding("NC_SHA_MISMATCH", "NC verification file SHA-256 mismatch.")
                )

    _check_reviewer_provenance(gold.get("reviewer_a_provenance"), "reviewer_a_provenance", result.errors)
    _check_reviewer_provenance(gold.get("reviewer_c_provenance"), "reviewer_c_provenance", result.errors)
    _check_adjudication_and_signoff(gold, cfg, result.errors)
    _check_negative_controls(gold, cfg, result)
    _check_judgments_and_topk(gold, cfg, retrieval_diag, pool_json, result.errors)

    result.expected_hashes = {
        "corpus_sha256": str(cfg.get("corpus_sha256") or ""),
        "query_manifest_sha256": str(cfg.get("query_manifest_sha256") or ""),
        "pool_sha256": str(cfg.get("pool_sha256") or ""),
        "gold_labels_sha256": result.gold_labels_sha256,
        "nc_verification_sha256": str(
            (gold.get("investigator_signoff") or {}).get("nc_verification_sha256") or ""
        ),
        "retrieval_manifest_sha256": str(cfg.get("retrieval_manifest_sha256") or ""),
    }
    result.passed = len(result.errors) == 0
    return result

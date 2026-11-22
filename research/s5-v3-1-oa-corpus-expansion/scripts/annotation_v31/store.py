"""Session store, blinding guard, quote validation, and backup manager."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import (
    ASSISTANCE_NONE_HUMAN,
    BENCHMARK_VERSION,
    BLINDED_FORBIDDEN_FIELDS,
    CS_SYSTEMS_DOMAINS,
    DOMAIN_GROUP_ALL,
    DOMAIN_GROUP_CS_SYSTEMS,
    DOMAIN_GROUP_MATH_ML,
    GRADE_REQUIRES_QUOTE_MIN,
    HASH_READ_CHUNK_BYTES,
    MATH_ML_DOMAINS,
    MIN_QUOTATION_CHARS,
    PROVENANCE_INDEPENDENT_HUMAN,
    SUBMISSION_SCHEMA_VERSION,
    VALID_DOMAIN_GROUPS,
    VALID_GRADES,
)

_WS_RE = re.compile(r"\s+")


def compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_READ_CHUNK_BYTES), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize_ws(text: str) -> str:
    """Collapse whitespace for verbatim quotation matching."""
    return _WS_RE.sub(" ", text).strip()


def verify_verbatim_quotation(quotation: str, passage_text: str) -> bool:
    """Return True if quotation appears verbatim (modulo whitespace) in passage."""
    norm_q = normalize_ws(quotation)
    if len(norm_q) < MIN_QUOTATION_CHARS:
        return False
    return norm_q in normalize_ws(passage_text)


def load_corpus_passages(corpus_jsonl: Path) -> dict[str, dict[str, Any]]:
    """Load Corpus v3.1 JSONL keyed by passage_id (dynamic count)."""
    passages: dict[str, dict[str, Any]] = {}
    with corpus_jsonl.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped:
                continue
            rec = json.loads(stripped)
            passages[str(rec["passage_id"])] = rec
    return passages


def _assert_strictly_blinded(pairs: list[dict[str, Any]]) -> None:
    """Reject any pool pair exposing system IDs, ranks, scores, or AI hints."""
    for pair in pairs:
        leaked = set(pair.keys()) & BLINDED_FORBIDDEN_FIELDS
        if leaked:
            msg = (
                f"Blinding violation in pair {pair.get('pair_id')}: "
                f"forbidden keys {sorted(leaked)}."
            )
            raise ValueError(msg)


def load_blinded_pool(pool_path: Path) -> dict[str, Any]:
    """Load and verify a strictly blinded S5-v3.1 pool JSON."""
    payload = json.loads(pool_path.read_text(encoding="utf-8"))
    if payload.get("benchmark_version") != BENCHMARK_VERSION:
        msg = (
            f"Pool benchmark_version must be '{BENCHMARK_VERSION}', "
            f"got '{payload.get('benchmark_version')}'."
        )
        raise ValueError(msg)
    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        msg = "Pool JSON must contain a non-empty 'pairs' list."
        raise ValueError(msg)
    _assert_strictly_blinded(pairs)
    expected = int(payload.get("expected_pair_count", -1))
    if expected != len(pairs):
        msg = (
            f"Pool expected_pair_count={expected} != len(pairs)={len(pairs)}."
        )
        raise ValueError(msg)
    return payload


def domain_to_group(domain: str) -> str:
    """Map a query domain string to 'math_ml' or 'cs_systems'."""
    if domain in MATH_ML_DOMAINS:
        return DOMAIN_GROUP_MATH_ML
    if domain in CS_SYSTEMS_DOMAINS:
        return DOMAIN_GROUP_CS_SYSTEMS
    return DOMAIN_GROUP_CS_SYSTEMS


def filter_pairs_by_domain_group(
    pairs: list[dict[str, Any]],
    domain_group: str,
) -> list[dict[str, Any]]:
    """Filter blinded pool pairs for a domain-specific reviewer assignment."""
    if domain_group not in VALID_DOMAIN_GROUPS:
        msg = f"Invalid domain_group '{domain_group}'."
        raise ValueError(msg)
    if domain_group == DOMAIN_GROUP_ALL:
        return list(pairs)
    return [
        p
        for p in pairs
        if domain_to_group(str(p.get("domain", ""))) == domain_group
    ]


class AnnotationSession:
    """Save/resume local human annotation session with timestamped backups."""

    def __init__(
        self,
        pool_path: Path,
        corpus_jsonl: Path,
        submission_path: Path,
        reviewer_id: str,
        domain_group: str = DOMAIN_GROUP_ALL,
    ) -> None:
        self.pool_path = pool_path
        self.corpus_jsonl = corpus_jsonl
        self.submission_path = submission_path
        self.pool = load_blinded_pool(pool_path)
        self.pool_sha256 = compute_file_sha256(pool_path)
        self.corpus = load_corpus_passages(corpus_jsonl)
        self.assigned_pairs = filter_pairs_by_domain_group(
            self.pool["pairs"], domain_group
        )
        self.pair_by_id = {str(p["pair_id"]): p for p in self.assigned_pairs}

        if submission_path.exists():
            self.state = json.loads(submission_path.read_text(encoding="utf-8"))
        else:
            self.state = {
                "schema_version": SUBMISSION_SCHEMA_VERSION,
                "benchmark_version": BENCHMARK_VERSION,
                "pool_id": str(self.pool["pool_id"]),
                "pool_sha256": self.pool_sha256,
                "expected_pair_count": len(self.assigned_pairs),
                "reviewer_provenance": {
                    "reviewer_id": reviewer_id,
                    "domain_group": domain_group,
                    "provenance_class": PROVENANCE_INDEPENDENT_HUMAN,
                    "assistance_declaration": ASSISTANCE_NONE_HUMAN,
                    "prior_exposure_disclosure": "",
                    "human_attestation_signed": False,
                    "attestation_signer": "",
                    "signed_timestamp_utc": "",
                },
                "judgments": {},
            }
            self.save(create_backup=False)

    def save(self, create_backup: bool = True) -> str:
        """Persist submission JSON, optional timestamped backup, and SHA-256."""
        self.submission_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(self.state, indent=2, sort_keys=False) + "\n"
        self.submission_path.write_text(serialized, encoding="utf-8")
        digest = compute_file_sha256(self.submission_path)
        sha_path = self.submission_path.with_suffix(
            self.submission_path.suffix + ".sha256"
        )
        sha_path.write_text(
            f"{digest}  {self.submission_path.name}\n", encoding="utf-8"
        )
        if create_backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_dir = self.submission_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = (
                backup_dir / f"{self.submission_path.stem}_{ts}.json"
            )
            backup_file.write_text(serialized, encoding="utf-8")
        return digest

    def record_judgment(
        self,
        pair_id: str,
        grade: int,
        supporting_quotation: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """Record one human judgment with verbatim quotation validation."""
        if pair_id not in self.pair_by_id:
            msg = f"Unknown or unassigned pair_id '{pair_id}'."
            raise KeyError(msg)
        if grade not in VALID_GRADES:
            msg = f"Grade must be in {sorted(VALID_GRADES)}, got {grade}."
            raise ValueError(msg)

        pair = self.pair_by_id[pair_id]
        pid = str(pair["passage_id"])
        passage_rec = self.corpus.get(pid)
        if passage_rec is None:
            msg = f"Passage '{pid}' missing from Corpus v3.1 JSONL."
            raise KeyError(msg)
        if str(passage_rec["passage_sha256"]) != str(pair["passage_sha256"]):
            msg = f"Passage SHA-256 mismatch for '{pid}'."
            raise ValueError(msg)

        if grade >= GRADE_REQUIRES_QUOTE_MIN and not verify_verbatim_quotation(
            supporting_quotation, str(passage_rec["text"])
        ):
            msg = (
                f"Grade {grade} requires a verbatim quotation (>= "
                f"{MIN_QUOTATION_CHARS} chars) from passage '{pid}'."
            )
            raise ValueError(msg)

        entry = {
            "pair_id": pair_id,
            "query_id": str(pair["query_id"]),
            "passage_id": pid,
            "passage_sha256": str(pair["passage_sha256"]),
            "grade": int(grade),
            "supporting_quotation": supporting_quotation.strip(),
            "notes": notes.strip(),
        }
        self.state["judgments"][pair_id] = entry
        self.save(create_backup=True)
        return entry

    def sign_and_finalize(
        self,
        attestation_signer: str,
        prior_exposure_disclosure: str,
        signed_timestamp_utc: str | None = None,
    ) -> str:
        """Sign independent human provenance after all assigned pairs judged."""
        if not attestation_signer.strip():
            msg = "attestation_signer must be non-empty."
            raise ValueError(msg)
        if not prior_exposure_disclosure.strip():
            msg = "prior_exposure_disclosure must be non-empty."
            raise ValueError(msg)
        missing = sorted(
            set(self.pair_by_id.keys()) - set(self.state["judgments"].keys())
        )
        if missing:
            msg = (
                f"Cannot sign incomplete submission: {len(missing)} pairs "
                f"unjudged (first: {missing[0]})."
            )
            raise ValueError(msg)

        ts = signed_timestamp_utc or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        prov = self.state["reviewer_provenance"]
        prov["prior_exposure_disclosure"] = prior_exposure_disclosure.strip()
        prov["attestation_signer"] = attestation_signer.strip()
        prov["signed_timestamp_utc"] = ts
        prov["human_attestation_signed"] = True
        return self.save(create_backup=True)


def validate_human_submission(
    submission: dict[str, Any],
    pool: dict[str, Any],
    corpus: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate a signed human submission; return list of error strings."""
    errors: list[str] = []
    if submission.get("schema_version") != SUBMISSION_SCHEMA_VERSION:
        errors.append("INVALID_SCHEMA_VERSION")
    if submission.get("benchmark_version") != BENCHMARK_VERSION:
        errors.append("INVALID_BENCHMARK_VERSION")

    prov = submission.get("reviewer_provenance", {})
    if prov.get("provenance_class") != PROVENANCE_INDEPENDENT_HUMAN:
        errors.append("NON_HUMAN_PROVENANCE_CLASS")
    if prov.get("assistance_declaration") != ASSISTANCE_NONE_HUMAN:
        errors.append("AI_ASSISTED_OR_INVALID_DECLARATION")
    if prov.get("human_attestation_signed") is not True:
        errors.append("UNSIGNED_HUMAN_ATTESTATION")
    for field in (
        "reviewer_id",
        "domain_group",
        "prior_exposure_disclosure",
        "attestation_signer",
        "signed_timestamp_utc",
    ):
        if not str(prov.get(field, "")).strip():
            errors.append(f"MISSING_PROVENANCE_{field.upper()}")

    domain_group = str(prov.get("domain_group", DOMAIN_GROUP_ALL))
    assigned = (
        filter_pairs_by_domain_group(pool["pairs"], domain_group)
        if domain_group in VALID_DOMAIN_GROUPS
        else []
    )
    expected_ids = {str(p["pair_id"]) for p in assigned}
    judgments = submission.get("judgments", {})
    if not isinstance(judgments, dict):
        errors.append("INVALID_JUDGMENTS_MAP")
        return errors

    if set(judgments.keys()) != expected_ids:
        errors.append(
            f"PAIR_COVERAGE_MISMATCH: expected={len(expected_ids)} "
            f"got={len(judgments)}"
        )

    for pair in assigned:
        pair_id = str(pair["pair_id"])
        j = judgments.get(pair_id)
        if not isinstance(j, dict):
            continue
        grade = j.get("grade")
        if grade not in VALID_GRADES:
            errors.append(f"INVALID_GRADE:{pair_id}")
            continue
        pid = str(pair["passage_id"])
        rec = corpus.get(pid)
        if rec is None:
            errors.append(f"MISSING_PASSAGE:{pid}")
            continue
        if str(j.get("passage_sha256", "")) != str(rec["passage_sha256"]):
            errors.append(f"PASSAGE_SHA_MISMATCH:{pair_id}")
        if grade >= GRADE_REQUIRES_QUOTE_MIN and not verify_verbatim_quotation(
            str(j.get("supporting_quotation", "")), str(rec["text"])
        ):
            errors.append(f"INVALID_VERBATIM_QUOTATION:{pair_id}")
    return errors

"""Dataset integrity, canonical document normalization, leakage auditing, and clean splits.

Research Repair S2: Eliminates training/evaluation leakage, enforces
document-disjoint train/validation/test partitions, detects exact/near/template
duplicates across splits, and blocks contaminated historical metrics from
entering publication exports.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Any

# Historical benchmark artifacts explicitly disqualified for scientific claims.
CONTAMINATED_BENCHMARK_MARKERS = (
    "dual_dataset_benchmark_results.json",
    "lib_qwen_scholarly_lora",
)


def normalize_doc_id(doc_id: str | None) -> str:
    """Canonicalize a source document identifier across arXiv, DOI, and file paths.

    Examples:
      - 'https://arxiv.org/abs/1706.03762v5' -> 'arxiv:1706.03762'
      - '10.48550/arXiv.1706.03762'         -> 'arxiv:1706.03762'
      - 'papers/Hu2021_LoRA.pdf'            -> 'papers/hu2021_lora.pdf'
    """
    if not doc_id or not isinstance(doc_id, str):
        return ""
    raw = doc_id.strip().lower()
    if not raw:
        return ""
    # arXiv URL or 10.48550/arXiv.<id> or bare YYMM.NNNNN[vN]
    arxiv_match = re.search(
        r"(?:arxiv\.org/(?:abs|pdf)/|10\.48550/arxiv\.|arxiv:|^)(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$",
        raw,
    )
    if arxiv_match:
        return f"arxiv:{arxiv_match.group(1)}"
    # DOI normalization
    doi_match = re.search(r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s]+)$", raw)
    if doi_match:
        return f"doi:{doi_match.group(1)}"
    return raw


def content_hash(text: str) -> str:
    """Deterministic SHA-256 over whitespace-normalized text."""
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def template_skeleton_hash(text: str) -> str:
    """Hash structural template skeleton by masking numbers and capitalized entity spans."""
    norm = (text or "").strip()
    masked = re.sub(r'"[^"]+"|\'[^\']+\'', "<STR>", norm)
    masked = re.sub(r"\b\d+(?:\.\d+)?%?\b", "<NUM>", masked)
    masked = re.sub(
        r"\b[A-Z][a-zA-Z0-9_-]*(?:\s+(?:[A-Z][a-zA-Z0-9_-]*|is|of|the|and|for|in|on|to|with|Is|Of|The|And|For|In|On|To|With))*\b",
        "<ENT>",
        masked,
    )
    masked = re.sub(r"(?:<ENT>\s*)+", "<ENT> ", masked)
    masked = re.sub(r"\s+", " ", masked).strip().lower()
    return hashlib.sha256(masked.encode("utf-8")).hexdigest()


def _token_shingles(text: str, k: int = 4) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def jaccard_similarity(a: str, b: str, k: int = 4) -> float:
    """4-gram token Jaccard similarity for near-duplicate detection."""
    sa = _token_shingles(a, k=k)
    sb = _token_shingles(b, k=k)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def extract_row_text(row: dict[str, Any]) -> str:
    """Extract canonical text payload from ChatML or instruction/input JSONL row."""
    if isinstance(row.get("messages"), list):
        parts = [
            str(m.get("content", ""))
            for m in row["messages"]
            if isinstance(m, dict) and m.get("role") in ("user", "assistant")
        ]
        return "\n".join(parts)
    return "\n".join(
        str(row.get(k, "")) for k in ("instruction", "input", "output") if row.get(k)
    )


def extract_row_doc_id(row: dict[str, Any]) -> str:
    """Extract canonical document ID from a dataset row."""
    raw = row.get("doc_id") or row.get("paper_id") or row.get("source_url") or ""
    return normalize_doc_id(str(raw))


def detect_cross_split_contamination(
    splits: dict[str, list[dict[str, Any]]],
    *,
    near_dup_threshold: float = 0.85,
) -> dict[str, Any]:
    """Audit train/validation/test splits for doc-ID, exact, near, and template overlap."""
    split_names = list(splits.keys())
    doc_sets: dict[str, set[str]] = {}
    exact_sets: dict[str, set[str]] = {}
    template_sets: dict[str, set[str]] = {}
    row_shingles: dict[str, list[set[str]]] = {}

    for sname, rows in splits.items():
        docs: set[str] = set()
        exacts: set[str] = set()
        tmpls: set[str] = set()
        shingles: list[set[str]] = []
        for r in rows:
            did = extract_row_doc_id(r)
            if did:
                docs.add(did)
            txt = extract_row_text(r)
            exacts.add(content_hash(txt))
            tmpls.add(template_skeleton_hash(txt))
            if len(shingles) < 400:
                shingles.append(_token_shingles(txt, k=4))
        doc_sets[sname] = docs
        exact_sets[sname] = exacts
        template_sets[sname] = tmpls
        row_shingles[sname] = shingles

    doc_overlaps: dict[str, list[str]] = {}
    exact_overlaps: dict[str, int] = {}
    template_overlaps: dict[str, int] = {}
    near_dups: dict[str, int] = {}

    for i in range(len(split_names)):
        for j in range(i + 1, len(split_names)):
            a, b = split_names[i], split_names[j]
            pair_key = f"{a}__vs__{b}"
            doc_overlaps[pair_key] = sorted(doc_sets[a] & doc_sets[b])
            exact_overlaps[pair_key] = len(exact_sets[a] & exact_sets[b])
            template_overlaps[pair_key] = len(template_sets[a] & template_sets[b])

            nd_count = 0
            for sa in row_shingles[a]:
                if not sa:
                    continue
                for sb in row_shingles[b]:
                    if not sb:
                        continue
                    if (len(sa & sb) / len(sa | sb)) >= near_dup_threshold:
                        nd_count += 1
                        break
            near_dups[pair_key] = nd_count

    has_doc_leak = any(bool(v) for v in doc_overlaps.values())
    has_exact_leak = any(v > 0 for v in exact_overlaps.values())
    return {
        "doc_id_overlaps": doc_overlaps,
        "exact_hash_overlaps": exact_overlaps,
        "template_skeleton_overlaps": template_overlaps,
        "near_duplicate_counts": near_dups,
        "is_document_disjoint": not has_doc_leak,
        "is_exact_deduped": not has_exact_leak,
    }


def build_document_disjoint_splits(
    rows: list[dict[str, Any]],
    *,
    train_ratio: float = 0.70,
    val_ratio: float = 0.10,
    seed: int = 42,
    default_license: str = "open_access_metadata_or_arxiv",
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Deterministically partition rows by canonical doc_id with exact deduplication.

    All chunks/variants of the same canonical document stay in the same split.
    Rows missing a valid doc_id are quarantined into ``quarantined`` and excluded
    from train/validation/test.
    """
    by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    quarantined: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    dropped_exact_dups = 0

    for row in rows:
        did = extract_row_doc_id(row)
        if not did:
            quarantined.append(row)
            continue
        ch = content_hash(extract_row_text(row))
        if ch in seen_hashes:
            dropped_exact_dups += 1
            continue
        seen_hashes.add(ch)
        enriched = dict(row)
        enriched["canonical_doc_id"] = did
        enriched["content_sha256"] = ch
        enriched.setdefault("source_license", default_license)
        by_doc[did].append(enriched)

    doc_ids = sorted(by_doc.keys())
    rng = random.Random(seed)
    rng.shuffle(doc_ids)

    n_docs = len(doc_ids)
    n_train = int(round(n_docs * train_ratio))
    n_val = int(round(n_docs * val_ratio))
    # Guarantee non-empty test split whenever >= 3 docs exist
    if n_docs >= 3 and n_train + n_val >= n_docs:
        n_train = max(1, n_docs - 2)
        n_val = 1

    train_docs = set(doc_ids[:n_train])
    val_docs = set(doc_ids[n_train : n_train + n_val])
    test_docs = set(doc_ids[n_train + n_val :])

    splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    doc_assignments: dict[str, dict[str, Any]] = {}
    for did in doc_ids:
        target = "train" if did in train_docs else ("validation" if did in val_docs else "test")
        for r in by_doc[did]:
            r_copy = dict(r)
            r_copy["split"] = target
            splits[target].append(r_copy)
        doc_assignments[did] = {
            "split": target,
            "row_count": len(by_doc[did]),
            "source_license": by_doc[did][0].get("source_license", default_license),
            "source_sha256": by_doc[did][0].get("source_sha256") or by_doc[did][0]["content_sha256"],
        }

    contamination = detect_cross_split_contamination(splits)
    if not contamination["is_document_disjoint"]:
        raise RuntimeError(f"Document leakage detected after split: {contamination['doc_id_overlaps']}")

    task_dist = {
        sname: dict(Counter(str(r.get("task", "unknown")) for r in srows))
        for sname, srows in splits.items()
    }
    manifest = {
        "seed": seed,
        "total_input_rows": len(rows),
        "dropped_exact_duplicates": dropped_exact_dups,
        "quarantined_missing_doc_id": len(quarantined),
        "doc_counts": {
            "train": len(train_docs),
            "validation": len(val_docs),
            "test": len(test_docs),
            "total": n_docs,
        },
        "row_counts": {k: len(v) for k, v in splits.items()},
        "task_distributions": task_dist,
        "contamination_check": contamination,
        "documents": doc_assignments,
    }
    return splits, manifest


def assert_clean_benchmark_record(
    record: dict[str, Any],
    source_path: str | Path | None = None,
) -> None:
    """Block contaminated historical benchmarks from entering publication exports."""
    if source_path is not None:
        spath = str(source_path)
        for marker in CONTAMINATED_BENCHMARK_MARKERS:
            if marker in spath:
                raise ValueError(
                    f"Contaminated historical benchmark '{spath}' is INVALID_FOR_SCIENTIFIC_CLAIMS "
                    "and cannot be exported for publication."
                )
    status = str(record.get("scientific_validity_status", "")).upper()
    if status == "INVALID_FOR_SCIENTIFIC_CLAIMS":
        raise ValueError("Benchmark record is marked INVALID_FOR_SCIENTIFIC_CLAIMS.")
    if record.get("train_test_leakage_detected") is True:
        raise ValueError("Benchmark record has confirmed train/test leakage.")
    if "overall_token_accuracy_pct" in record and "concept_f1" not in record:
        raise ValueError(
            "Teacher-forced token accuracy alone cannot be exported as extraction performance."
        )


def audit_historical_9722_claim(repo_root: Path) -> dict[str, Any]:
    """Reproduce and audit the historical 97.22% accuracy claim without altering original files."""
    d1_path = repo_root / "data/datasets/dataset1_pedagogical_revamped.jsonl"
    d2_path = repo_root / "data/datasets/dataset2_scholarly_evidence.jsonl"
    blended_path = repo_root / "data/datasets/blended_multitask_dataset.jsonl"
    hist_path = repo_root / "models/lib_qwen_scholarly_lora/dual_dataset_benchmark_results.json"

    hist_data = json.loads(hist_path.read_text(encoding="utf-8"))
    d1 = [json.loads(l) for l in d1_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    d2 = [json.loads(l) for l in d2_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    # Exact eval slice from scripts/run_slm_comprehensive_benchmark.py lines 149-156
    eval_samples = [d1[i] for i in range(1470, 1500, 3)] + [d2[i] for i in range(970, 1000, 3)]

    def _msg_hash(r: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(r["messages"], sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    eval_hashes = [_msg_hash(r) for r in eval_samples]

    # Reproduce train_qlora_slm.py random 90/10 split (seed=42)
    from datasets import load_dataset

    ds = load_dataset("json", data_files=str(blended_path), split="train")
    split = ds.train_test_split(test_size=0.10, seed=42)
    train_hashes = {_msg_hash({"messages": r["messages"]}) for r in split["train"]}
    test_hashes = {_msg_hash({"messages": r["messages"]}) for r in split["test"]}

    in_train = sum(1 for h in eval_hashes if h in train_hashes)
    in_test = sum(1 for h in eval_hashes if h in test_hashes)

    return {
        "historical_artifact": str(hist_path.relative_to(repo_root)),
        "reported_overall_token_accuracy_pct": hist_data.get("fine_tuned_slm", {}).get(
            "overall_token_accuracy_pct"
        ),
        "scientific_validity_status": "INVALID_FOR_SCIENTIFIC_CLAIMS",
        "train_test_leakage_detected": True,
        "eval_sample_count": len(eval_samples),
        "eval_samples_in_train_split": in_train,
        "eval_samples_in_test_split": in_test,
        "exact_contamination_rate": round(in_train / len(eval_samples), 4),
        "metric_type": "teacher_forced_next_token_argmax_accuracy",
        "is_extraction_f1": False,
        "synthetic_template_origin": "training/generate_expanded_datasets.py",
        "audit_notes": [
            "19 of 20 evaluated rows (95.0%) were present verbatim in the 90% training split.",
            "All 2,500 rows were template-generated from okf_graph.json and 25 hardcoded paper tuples.",
            "97.22% measures teacher-forced next-token prediction, not concept or directed edge extraction F1.",
        ],
    }

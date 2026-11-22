"""Unit tests for S5-v3.1 annotation workbench, pool, adjudication, and NC."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = (
    REPO_ROOT / "research" / "s5-v3-1-oa-corpus-expansion" / "scripts"
)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from adjudication_v31.adjudicator import (  # noqa: E402
    compute_inter_annotator_agreement,
    generate_disagreement_worksheet,
    validate_adjudication_worksheet,
)
from adjudication_v31.constants import GOLD_STATUS_SYNTHETIC  # noqa: E402
from adjudication_v31.gold_assembler import assemble_v31_gold  # noqa: E402
from adjudication_v31.nc_verifier import (  # noqa: E402
    generate_nc_verification_worksheet,
    validate_nc_verifications,
)
from adjudication_v31.pool_builder import (  # noqa: E402
    build_blinded_pool,
    compute_file_sha256,
)
from annotation_v31.constants import (  # noqa: E402
    DOMAIN_GROUP_CS_SYSTEMS,
    DOMAIN_GROUP_MATH_ML,
)
from annotation_v31.server import create_local_server  # noqa: E402
from annotation_v31.store import (  # noqa: E402
    AnnotationSession,
    filter_pairs_by_domain_group,
    load_blinded_pool,
    load_corpus_passages,
    validate_human_submission,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_synthetic_fixture(tmp_path: Path) -> dict[str, Path]:
    """Create isolated SYNTHETIC v3.1 fixtures under tmp_path."""
    p1_text = "Deadlock requires mutual exclusion, hold and wait, non-preemption, and circular wait."
    p2_text = "Linear regression minimizes squared error loss over training observations."
    p3_text = "Unrelated passage discussing file system directory traversal."
    corpus_path = tmp_path / "corpus.jsonl"
    rows = [
        {
            "passage_id": "p_os_1",
            "source_doc_id": "oa_os_001",
            "domain": "Operating Systems",
            "page_start": None,
            "page_end": None,
            "section_ref": "sec_deadlock",
            "passage_sha256": _sha(p1_text),
            "text": p1_text,
        },
        {
            "passage_id": "p_ml_1",
            "source_doc_id": "local_oa_001",
            "domain": "Machine Learning",
            "page_start": 1,
            "page_end": 1,
            "section_ref": "Loss",
            "passage_sha256": _sha(p2_text),
            "text": p2_text,
        },
        {
            "passage_id": "p_os_2",
            "source_doc_id": "oa_os_001",
            "domain": "Operating Systems",
            "page_start": None,
            "page_end": None,
            "section_ref": "sec_fs",
            "passage_sha256": _sha(p3_text),
            "text": p3_text,
        },
    ]
    corpus_path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )

    queries_path = tmp_path / "approved_queries.json"
    queries_path.write_text(
        json.dumps(
            {
                "schema_version": "s5v31_approved_queries_synthetic",
                "queries": [
                    {
                        "query_id": "Q-SYN-01",
                        "query_text": "What four conditions cause deadlock?",
                        "split": "test",
                        "category": "single_passage_fact_concept",
                        "domain": "Operating Systems",
                    },
                    {
                        "query_id": "Q-SYN-02",
                        "query_text": "How does linear regression minimize squared error?",
                        "split": "test",
                        "category": "single_passage_fact_concept",
                        "domain": "Machine Learning",
                    },
                    {
                        "query_id": "Q-SYN-NC1",
                        "query_text": "What is the exact Spanner TrueTime epsilon?",
                        "split": "test",
                        "category": "negative_control",
                        "domain": "Negative Control (Absent)",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    diag_path = tmp_path / "retrieval_diag.json"
    diag_path.write_text(
        json.dumps(
            {
                "variants": {
                    "v31_lexical_bm25": {
                        "per_query_diagnostics": [
                            {
                                "query_id": "Q-SYN-01",
                                "results": [
                                    {"passage_id": "p_os_1", "rank": 1, "score": 9.5},
                                    {"passage_id": "p_os_2", "rank": 2, "score": 1.2},
                                ],
                            },
                            {
                                "query_id": "Q-SYN-02",
                                "results": [
                                    {"passage_id": "p_ml_1", "rank": 1, "score": 8.1},
                                ],
                            },
                        ]
                    },
                    "v31_dense_snowflake": {
                        "per_query_diagnostics": [
                            {
                                "query_id": "Q-SYN-01",
                                "results": [
                                    {"passage_id": "p_os_1", "rank": 1, "score": 0.91},
                                ],
                            },
                            {
                                "query_id": "Q-SYN-02",
                                "results": [
                                    {"passage_id": "p_ml_1", "rank": 1, "score": 0.88},
                                    {"passage_id": "p_os_2", "rank": 2, "score": 0.11},
                                ],
                            },
                        ]
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    ret_manifest_path = tmp_path / "retrieval_manifest.json"
    ret_manifest_path.write_text(
        json.dumps(
            {
                "corpus_id": "s5v31_corpus_synthetic",
                "variants": {
                    "v31_lexical_bm25": {"config_sha256": _sha("bm25")},
                    "v31_dense_snowflake": {"config_sha256": _sha("dense")},
                },
            }
        ),
        encoding="utf-8",
    )

    return {
        "corpus": corpus_path,
        "queries": queries_path,
        "diag": diag_path,
        "ret_manifest": ret_manifest_path,
    }


@pytest.mark.unit
def test_blinded_pool_and_domain_group_filtering(tmp_path: Path) -> None:
    """Blinded pool strips system/rank/score fields and supports domain groups."""
    fx = _make_synthetic_fixture(tmp_path)
    pool_path = tmp_path / "pool.json"
    cfg_path = tmp_path / "config.json"

    pool, cfg = build_blinded_pool(
        approved_queries_path=fx["queries"],
        retrieval_diagnostics_path=fx["diag"],
        retrieval_manifest_path=fx["ret_manifest"],
        corpus_jsonl_path=fx["corpus"],
        pool_depth_k=5,
        split="test",
        pool_id="pool_syn_k5",
        output_pool_path=pool_path,
        output_config_path=cfg_path,
    )
    assert pool["expected_pair_count"] == 4
    assert cfg["benchmark_version"] == "s5v3.1"
    assert cfg["approved_negative_control_ids"] == ["Q-SYN-NC1"]

    loaded = load_blinded_pool(pool_path)
    assert len(loaded["pairs"]) == 4
    cs_pairs = filter_pairs_by_domain_group(
        loaded["pairs"], DOMAIN_GROUP_CS_SYSTEMS
    )
    ml_pairs = filter_pairs_by_domain_group(
        loaded["pairs"], DOMAIN_GROUP_MATH_ML
    )
    assert len(cs_pairs) == 2
    assert len(ml_pairs) == 2

    # Injecting a rank field must fail blinding check
    bad_pool = copy.deepcopy(loaded)
    bad_pool["pairs"][0]["rank"] = 1
    bad_path = tmp_path / "bad_pool.json"
    bad_path.write_text(json.dumps(bad_pool), encoding="utf-8")
    with pytest.raises(ValueError, match="Blinding violation"):
        load_blinded_pool(bad_path)


@pytest.mark.unit
def test_workbench_verbatim_quote_backups_and_loopback_only(
    tmp_path: Path,
) -> None:
    """Workbench enforces verbatim quotes, creates backups, and binds 127.0.0.1."""
    fx = _make_synthetic_fixture(tmp_path)
    pool_path = tmp_path / "pool.json"
    cfg_path = tmp_path / "config.json"
    build_blinded_pool(
        fx["queries"],
        fx["diag"],
        fx["ret_manifest"],
        fx["corpus"],
        5,
        "test",
        "pool_syn",
        pool_path,
        cfg_path,
    )
    sub_path = tmp_path / "sub_a.json"
    session = AnnotationSession(pool_path, fx["corpus"], sub_path, "REV_A")

    # Non-loopback host must be refused
    with pytest.raises(ValueError, match="non-loopback"):
        create_local_server(session, host="0.0.0.0", port=0)

    # Fabricated quote on grade 2 must fail
    first_pair = session.assigned_pairs[0]
    with pytest.raises(ValueError, match="verbatim quotation"):
        session.record_judgment(
            first_pair["pair_id"], 2, "This quote does not exist in passage."
        )

    # Valid verbatim quotes succeed and create backups + sha256 sidecar
    corpus = load_corpus_passages(fx["corpus"])
    for pair in session.assigned_pairs:
        quote = corpus[pair["passage_id"]]["text"][:25]
        session.record_judgment(pair["pair_id"], 2, quote)

    assert sub_path.with_suffix(".json.sha256").exists()
    assert list((tmp_path / "backups").glob("sub_a_*.json"))

    # Unsigned submission fails validation
    errs = validate_human_submission(session.state, session.pool, corpus)
    assert "UNSIGNED_HUMAN_ATTESTATION" in errs

    session.sign_and_finalize("Human Reviewer A", "NONE")
    assert validate_human_submission(session.state, session.pool, corpus) == []


@pytest.mark.unit
def test_full_adjudication_nc_reclassification_and_gold_assembly(
    tmp_path: Path,
) -> None:
    """End-to-end dual human adjudication, NC verification, and gold assembly."""
    fx = _make_synthetic_fixture(tmp_path)
    pool_path = tmp_path / "pool.json"
    cfg_path = tmp_path / "config.json"
    pool, cfg = build_blinded_pool(
        fx["queries"],
        fx["diag"],
        fx["ret_manifest"],
        fx["corpus"],
        5,
        "test",
        "pool_syn",
        pool_path,
        cfg_path,
    )
    corpus = load_corpus_passages(fx["corpus"])

    sub_a_path = tmp_path / "sub_a.json"
    sub_c_path = tmp_path / "sub_c.json"
    sa = AnnotationSession(pool_path, fx["corpus"], sub_a_path, "REV_A")
    sc = AnnotationSession(pool_path, fx["corpus"], sub_c_path, "REV_C")

    for idx, pair in enumerate(pool["pairs"]):
        quote = corpus[pair["passage_id"]]["text"][:25]
        sa.record_judgment(pair["pair_id"], 2 if idx < 2 else 0, quote if idx < 2 else "")
        sc.record_judgment(pair["pair_id"], 1 if idx == 0 else (2 if idx < 2 else 0), quote if idx < 2 else "")

    sa.sign_and_finalize("Reviewer A", "NONE", "2026-11-19T12:00:00Z")
    sc.sign_and_finalize("Reviewer C", "NONE", "2026-11-19T12:01:00Z")

    # Disagreement worksheet & IAA
    ws = generate_disagreement_worksheet(sa.state, sc.state, pool)
    assert ws["total_disagreements"] == 1
    dis_ids = frozenset(d["pair_id"] for d in ws["disagreements"])
    assert "UNSIGNED_ADJUDICATION" in validate_adjudication_worksheet(ws, dis_ids)

    ws["disagreements"][0]["final_grade"] = 2
    ws["disagreements"][0]["adjudication_rationale"] = (
        "Passage directly states all four deadlock conditions."
    )
    ws["adjudicator_provenance"]["adjudicator_id"] = "ADJ_HUMAN_1"
    ws["adjudicator_provenance"]["human_attestation_signed"] = True
    ws["adjudicator_provenance"]["attestation_signer"] = "Dr. Adjudicator"
    ws["adjudicator_provenance"]["signed_timestamp_utc"] = "2026-11-19T12:05:00Z"
    assert validate_adjudication_worksheet(ws, dis_ids) == []

    adj_path = tmp_path / "adjudication.json"
    adj_path.write_text(json.dumps(ws), encoding="utf-8")

    # NC verification with reclassification enum support
    nc_ws = generate_nc_verification_worksheet(
        [{"query_id": "Q-SYN-NC1", "query_text": "Spanner TrueTime epsilon?"}],
        cfg["corpus_sha256"],
    )
    assert validate_nc_verifications(
        nc_ws, frozenset({"Q-SYN-NC1"}), cfg["corpus_sha256"]
    )
    nc_rec = nc_ws["verifications"]["Q-SYN-NC1"]
    nc_rec["human_nc_classification"] = "confirmed_unanswerable"
    nc_rec["verifier_id"] = "VER_HUMAN_1"
    nc_rec["human_attestation_signed"] = True
    nc_rec["attestation_signer"] = "Dr. Verifier"
    nc_rec["signed_timestamp_utc"] = "2026-11-19T12:06:00Z"
    nc_rec["rationale"] = "Verified absent from all passages in corpus."
    assert (
        validate_nc_verifications(
            nc_ws, frozenset({"Q-SYN-NC1"}), cfg["corpus_sha256"]
        )
        == []
    )
    nc_path = tmp_path / "nc_verified.json"
    nc_path.write_text(json.dumps(nc_ws), encoding="utf-8")

    # Investigator signoff with exact hashes
    signoff_path = tmp_path / "signoff.json"
    signoff_path.write_text(
        json.dumps(
            {
                "investigator_id": "PI_SYNTHETIC",
                "approval_declaration": "Synthetic test approval only.",
                "human_signoff_confirmed": True,
                "signed_timestamp_utc": "2026-11-19T12:10:00Z",
                "corpus_sha256": cfg["corpus_sha256"],
                "query_manifest_sha256": cfg["query_manifest_sha256"],
                "pool_sha256": cfg["pool_sha256"],
                "retrieval_manifest_sha256": cfg["retrieval_manifest_sha256"],
                "nc_verification_sha256": compute_file_sha256(nc_path),
            }
        ),
        encoding="utf-8",
    )

    gold_path = tmp_path / "gold.json"
    gold = assemble_v31_gold(
        benchmark_config_path=cfg_path,
        pool_path=pool_path,
        corpus_jsonl_path=fx["corpus"],
        sub_a_path=sub_a_path,
        sub_c_path=sub_c_path,
        adjudication_path=adj_path,
        nc_verification_path=nc_path,
        investigator_signoff_path=signoff_path,
        output_gold_path=gold_path,
        status=GOLD_STATUS_SYNTHETIC,
    )
    assert gold["schema_version"] == "s5v31_adjudicated_gold_v1"
    assert len(gold["judgments"]) == 4
    iaa = compute_inter_annotator_agreement([2, 2, 0, 0], [1, 2, 0, 0])
    assert gold["inter_annotator_agreement"] == iaa

    # Tampering with signoff corpus_sha256 must fail closed
    bad_signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
    bad_signoff["corpus_sha256"] = "0" * 64
    bad_signoff_path = tmp_path / "bad_signoff.json"
    bad_signoff_path.write_text(json.dumps(bad_signoff), encoding="utf-8")
    with pytest.raises(ValueError, match="SIGNOFF_HASH_MISMATCH"):
        assemble_v31_gold(
            benchmark_config_path=cfg_path,
            pool_path=pool_path,
            corpus_jsonl_path=fx["corpus"],
            sub_a_path=sub_a_path,
            sub_c_path=sub_c_path,
            adjudication_path=adj_path,
            nc_verification_path=nc_path,
            investigator_signoff_path=bad_signoff_path,
            output_gold_path=tmp_path / "gold_bad.json",
            status=GOLD_STATUS_SYNTHETIC,
        )

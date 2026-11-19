"""New CS-domain test-split cross-doc (3) & negative-control (3) drafts."""

from __future__ import annotations

from .builder import QueryDraft
from .constants import (
    CAT_CROSS_DOC_MULTI,
    CAT_NEGATIVE_CONTROL,
    SPLIT_TEST,
)


def get_new_cs_test_cross_nc_drafts() -> list[QueryDraft]:
    """Return 6 test-split queries (3 cross-doc CS, 3 negative controls)."""
    return [
        QueryDraft(
            query_id="Q-S5V31-67",
            query_text=(
                "Compare how operating systems organize cache, main, and "
                "secondary storage in a memory hierarchy with why file-based "
                "application systems suffer from data-structure coupling "
                "compared to database management systems."
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain="Cross-Domain (CS Systems)",
            domain_topic="OS & Databases / Storage Abstraction",
            exact_information_need=(
                "Connect OS memory hierarchy trade-offs across cache, main, "
                "and secondary memory (oa_os_001 c0080) with file-based "
                "system rigidity where file formats are hardcoded in "
                "applications (oa_db_001 c0018)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_os_001_s0000_c0080",
                "s5v31_oa_db_001_s0000_c0018",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_os_001_s0000_c0080",
                "s5v31_oa_db_001_s0000_c0018",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "oa_os_001 c0080 describes the memory hierarchy while "
                "oa_db_001 c0018 describes file-based application coupling."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-68",
            query_text=(
                "Contrast single-table entity integrity constraints on "
                "primary keys in relational databases with how two-phase "
                "commit (2PC) ensures atomic commitment across multiple "
                "distributed nodes rather than serializable isolation (2PL)."
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain="Cross-Domain (CS Systems)",
            domain_topic="Databases & Distributed Systems / Integrity",
            exact_information_need=(
                "Connect relational entity integrity requiring non-null "
                "primary keys (oa_db_001 c0114) with 2PC atomic commitment "
                "across nodes distinguished from 2PL serializability "
                "(oa_ds_001 c0145)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_db_001_s0000_c0114",
                "s5v31_oa_ds_001_s0000_c0145",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_db_001_s0000_c0114",
                "s5v31_oa_ds_001_s0000_c0145",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "oa_db_001 c0114 covers entity integrity while oa_ds_001 "
                "c0145 contrasts 2PC atomic commit with 2PL isolation."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-69",
            query_text=(
                "How do client-perceived operation start and finish intervals "
                "define linearizability across quorum reads in distributed "
                "systems, and how does this compare to centralized database "
                "architectures where the DBMS resides at a single site?"
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain="Cross-Domain (CS Systems)",
            domain_topic="Databases & Distributed Systems / Consistency",
            exact_information_need=(
                "Connect linearizability across get/set and quorum read "
                "intervals (oa_ds_001 c0154, c0157) with single-site "
                "centralized database systems (oa_db_001 c0058)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_ds_001_s0000_c0154",
                "s5v31_oa_ds_001_s0000_c0157",
                "s5v31_oa_db_001_s0000_c0058",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_ds_001_s0000_c0157",
                "s5v31_oa_db_001_s0000_c0058",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "oa_ds_001 c0154/c0157 define linearizability for quorum "
                "reads while oa_db_001 c0058 describes centralized single-site "
                "DBMS architecture."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-70",
            query_text=(
                "How does RFC 9000 QUIC 0-RTT handshake mitigate replay "
                "attacks using server-side anti-replay Bloom filters?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain="Negative Control (Absent)",
            domain_topic="Computer Networks (Absent)",
            exact_information_need=(
                "Negative control: RFC 9000 QUIC 0-RTT anti-replay details "
                "are absent from CNP3 (Release 9/2011) and all Corpus v3.1 "
                "passages."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of QUIC, RFC 9000, or 0-RTT across all "
                "1,958 Corpus v3.1 passages."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-71",
            query_text=(
                "What exact GPS and atomic-clock uncertainty bound epsilon "
                "in milliseconds does Google Spanner TrueTime report during "
                "commit-wait?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain="Negative Control (Absent)",
            domain_topic="Distributed Systems (Absent)",
            exact_information_need=(
                "Negative control: Google Spanner TrueTime epsilon numbers "
                "are absent from all 1,958 Corpus v3.1 passages."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of Spanner or TrueTime across all 1,958 "
                "Corpus v3.1 passages."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-72",
            query_text=(
                "How does RocksDB tune LSM-tree leveled compaction write "
                "amplification factors and per-level Bloom filter "
                "bits-per-key?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain="Negative Control (Absent)",
            domain_topic="Databases / Storage Engines (Absent)",
            exact_information_need=(
                "Negative control: RocksDB LSM-tree compaction and write "
                "amplification tuning are absent from all 1,958 Corpus v3.1 "
                "passages."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of RocksDB, LSM-tree, or write "
                "amplification across all 1,958 Corpus v3.1 passages."
            ),
        ),
    ]

"""New CS-domain test-split core queries (12 queries: Q-S5V31-55..66)."""

from __future__ import annotations

from .builder import QueryDraft
from .constants import (
    CAT_SAME_DOC_MULTI,
    CAT_SINGLE_PASSAGE,
    CAT_TECH_PARAPHRASE,
    SPLIT_TEST,
)


def get_new_cs_test_core_drafts() -> list[QueryDraft]:
    """Return 12 test-split queries covering OS, DB, Networks, DS."""
    return [
        # --- Operating Systems (3) ---
        QueryDraft(
            query_id="Q-S5V31-55",
            query_text=(
                "What are the three interprocess communication methods "
                "described for sharing memory and resources between processes?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain="Operating Systems",
            domain_topic="OS / IPC",
            exact_information_need=(
                "List Sockets, Remote Procedure Calls (RPC), and Pipelining "
                "from oa_os_001 c0043."
            ),
            evidence_passage_ids=("s5v31_oa_os_001_s0000_c0043",),
            minimum_required_evidence_ids=("s5v31_oa_os_001_s0000_c0043",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage c0043 lists all three IPC methods.",
        ),
        QueryDraft(
            query_id="Q-S5V31-56",
            query_text=(
                "How does time-slice CPU scheduling transition an unfinished "
                "process to the waiting state, and how does deferred thread "
                "cancellation differ from asynchronous cancellation?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain="Operating Systems",
            domain_topic="OS / Scheduling & Threads",
            exact_information_need=(
                "Combine time-slice expiration moving a process to the "
                "blocked/waiting queue (c0035) with deferred vs asynchronous "
                "thread termination (c0062)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_os_001_s0000_c0035",
                "s5v31_oa_os_001_s0000_c0062",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_os_001_s0000_c0035",
                "s5v31_oa_os_001_s0000_c0062",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0035 covers time-slice scheduling transitions while c0062 "
                "covers thread cancellation modes."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-57",
            query_text=(
                "How does non-contiguous memory allocation eliminate external "
                "fragmentation when placing program instructions in RAM?"
            ),
            split=SPLIT_TEST,
            category=CAT_TECH_PARAPHRASE,
            domain="Operating Systems",
            domain_topic="OS / Memory Management",
            exact_information_need=(
                "Explain that N-CMA (implemented via paging and segmentation) "
                "avoids external fragmentation because program instructions "
                "need not be placed contiguously."
            ),
            evidence_passage_ids=("s5v31_oa_os_001_s0000_c0098",),
            minimum_required_evidence_ids=("s5v31_oa_os_001_s0000_c0098",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Paraphrase directly answered by c0098.",
        ),
        # --- Databases (3) ---
        QueryDraft(
            query_id="Q-S5V31-58",
            query_text=(
                "How should a many-to-many relationship be transformed so it "
                "can be implemented in the relational database model?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain="Databases",
            domain_topic="Databases / ER Modeling",
            exact_information_need=(
                "State that an M:N relationship cannot be implemented "
                "directly and must be broken into two 1:M relationships."
            ),
            evidence_passage_ids=("s5v31_oa_db_001_s0000_c0102",),
            minimum_required_evidence_ids=("s5v31_oa_db_001_s0000_c0102",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage c0102 explains M:N decomposition.",
        ),
        QueryDraft(
            query_id="Q-S5V31-59",
            query_text=(
                "What conditions define Third Normal Form (3NF) in relational "
                "normalization, and what steps are required to eliminate "
                "transitive dependencies?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain="Databases",
            domain_topic="Databases / Normalization",
            exact_information_need=(
                "Combine the 3NF definition (in 2NF with no non-key attribute "
                "functionally dependent on another non-key attribute in "
                "c0165) with the decomposition steps creating new tables for "
                "removed transitive dependencies (c0166)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_db_001_s0000_c0165",
                "s5v31_oa_db_001_s0000_c0166",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_db_001_s0000_c0165",
                "s5v31_oa_db_001_s0000_c0166",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0165 states the 3NF rule while c0166 lists the table "
                "decomposition procedure."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-60",
            query_text=(
                "Which SQL data definition commands construct or modify "
                "database schemas, and in what clause sequence is a SQL "
                "SELECT query processed?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain="Databases",
            domain_topic="Databases / SQL DDL & DML",
            exact_information_need=(
                "Combine major SQL DDL statements (CREATE DATABASE, "
                "CREATE/DROP/ALTER TABLE in c0203) with the SELECT "
                "processing sequence (SELECT DISTINCT, FROM, WHERE, GROUP BY "
                "in c0223)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_db_001_s0000_c0203",
                "s5v31_oa_db_001_s0000_c0223",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_db_001_s0000_c0203",
                "s5v31_oa_db_001_s0000_c0223",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0203 covers DDL statements while c0223 specifies SELECT "
                "clause order."
            ),
        ),
        # --- Computer Networks (3) ---
        QueryDraft(
            query_id="Q-S5V31-61",
            query_text=(
                "How does the Go-Back-N sliding window recovery protocol "
                "keep receiver logic simple?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain="Computer Networks",
            domain_topic="Networks / Transport Reliability",
            exact_information_need=(
                "Explain Go-Back-N receiver behavior and recovery operation "
                "on p. 80 c0188."
            ),
            evidence_passage_ids=("s5v31_oa_net_001_p0080_c0188",),
            minimum_required_evidence_ids=("s5v31_oa_net_001_p0080_c0188",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage p. 80 c0188 covers Go-Back-N.",
        ),
        QueryDraft(
            query_id="Q-S5V31-62",
            query_text=(
                "What role does the Border Gateway Protocol play in "
                "interdomain routing, and how does the AS-Path attribute "
                "evolve as a prefix advertisement traverses autonomous "
                "systems?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain="Computer Networks",
            domain_topic="Networks / BGP Interdomain Routing",
            exact_information_need=(
                "Combine BGP's role as the Internet's single interdomain "
                "routing protocol (p. 184 c0452) with how AS1 originates a "
                "prefix and AS4 prepends its AS number to the AS-Path when "
                "re-announcing to AS2 (p. 184 c0453)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_net_001_p0184_c0452",
                "s5v31_oa_net_001_p0184_c0453",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_net_001_p0184_c0452",
                "s5v31_oa_net_001_p0184_c0453",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0452 defines BGP's interdomain role while c0453 traces "
                "AS-Path propagation across AS1, AS4, and AS2."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-63",
            query_text=(
                "Why do top-level domain lookups rely on synchronized root "
                "nameservers while local DNS resolvers cache answers for "
                "client hosts?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain="Computer Networks",
            domain_topic="Networks / DNS Hierarchy",
            exact_information_need=(
                "Combine root nameservers maintaining synchronized TLD "
                "nameserver lists (p. 38 c0080) with caching resolvers "
                "sparing hosts from querying global nameservers (p. 38 c0081)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_net_001_p0038_c0080",
                "s5v31_oa_net_001_p0038_c0081",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_net_001_p0038_c0080",
                "s5v31_oa_net_001_p0038_c0081",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0080 covers root nameservers while c0081 explains resolver "
                "caching benefits."
            ),
        ),
        # --- Distributed Systems (3) ---
        QueryDraft(
            query_id="Q-S5V31-64",
            query_text=(
                "How do FIFO broadcast and causal broadcast differ in the "
                "delivery ordering guarantees they impose on broadcast "
                "messages?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain="Distributed Systems",
            domain_topic="Distributed Systems / Broadcast",
            exact_information_need=(
                "Contrast FIFO broadcast (same-sender order) with causal "
                "broadcast (happens-before broadcast order) in c0102."
            ),
            evidence_passage_ids=("s5v31_oa_ds_001_s0000_c0102",),
            minimum_required_evidence_ids=("s5v31_oa_ds_001_s0000_c0102",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage c0102 defines both forms.",
        ),
        QueryDraft(
            query_id="Q-S5V31-65",
            query_text=(
                "How do practical distributed consensus protocols circumvent "
                "the FLP impossibility result using timeouts, and what "
                "triggers a candidate node to initiate leader election?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain="Distributed Systems",
            domain_topic="Distributed Systems / Consensus & Elections",
            exact_information_need=(
                "Combine avoiding FLP non-termination via clocks/timeouts or "
                "randomization (c0173) with leader election triggered when "
                "followers suspect leader failure after missing messages "
                "(c0174)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_ds_001_s0000_c0173",
                "s5v31_oa_ds_001_s0000_c0174",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_ds_001_s0000_c0173",
                "s5v31_oa_ds_001_s0000_c0174",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0173 explains circumventing FLP while c0174 details "
                "timeout-triggered candidate leader elections."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-66",
            query_text=(
                "How does two-phase commit recover from a coordinator crash "
                "by persisting its commit or abort decision to stable "
                "storage?"
            ),
            split=SPLIT_TEST,
            category=CAT_TECH_PARAPHRASE,
            domain="Distributed Systems",
            domain_topic="Distributed Systems / Atomic Commit",
            exact_information_need=(
                "Explain that the 2PC coordinator writes its decision to disk "
                "and upon recovery reads the decision from disk to send to "
                "replicas (or aborts if none was recorded)."
            ),
            evidence_passage_ids=("s5v31_oa_ds_001_s0000_c0147",),
            minimum_required_evidence_ids=("s5v31_oa_ds_001_s0000_c0147",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Paraphrase ('stable storage' = disk) directly answered by "
                "c0147."
            ),
        ),
    ]

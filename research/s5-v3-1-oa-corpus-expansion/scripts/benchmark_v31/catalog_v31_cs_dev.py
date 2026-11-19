"""New CS-domain dev-split query drafts (10 queries: Q-S5V31-45..54)."""

from __future__ import annotations

from .builder import QueryDraft
from .constants import (
    CAT_CROSS_DOC_MULTI,
    CAT_NEGATIVE_CONTROL,
    CAT_SAME_DOC_MULTI,
    CAT_SINGLE_PASSAGE,
    CAT_TECH_PARAPHRASE,
    SPLIT_DEV,
)


def get_new_cs_dev_drafts() -> list[QueryDraft]:
    """Return 10 new dev-split queries covering OS, DB, Networks, DS + NC."""
    return [
        QueryDraft(
            query_id="Q-S5V31-45",
            query_text=(
                "What are the respective roles of the fork(), exit(), kill(), "
                "and nice() system calls in operating system process control?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain="Operating Systems",
            domain_topic="OS / Process System Calls",
            exact_information_need=(
                "State that fork() creates a child process, exit() terminates "
                "a process, kill() terminates a process abnormally, and "
                "nice() adjusts process priority."
            ),
            evidence_passage_ids=("s5v31_oa_os_001_s0000_c0018",),
            minimum_required_evidence_ids=("s5v31_oa_os_001_s0000_c0018",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage c0018 lists all four syscalls.",
        ),
        QueryDraft(
            query_id="Q-S5V31-46",
            query_text=(
                "What four necessary conditions cause deadlock in an "
                "operating system, and what four general strategies exist to "
                "handle deadlocks?"
            ),
            split=SPLIT_DEV,
            category=CAT_SAME_DOC_MULTI,
            domain="Operating Systems",
            domain_topic="OS / Deadlocks",
            exact_information_need=(
                "Combine the four deadlock characteristics (Mutual Exclusion, "
                "Hold and Wait, Non-Preemption, Circular Wait in c0069) with "
                "the four handling methods (Prevention, Avoidance, Detection "
                "and Recovery, Ignorance in c0071)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_os_001_s0000_c0069",
                "s5v31_oa_os_001_s0000_c0071",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_os_001_s0000_c0069",
                "s5v31_oa_os_001_s0000_c0071",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0069 lists the four conditions while c0071 lists the four "
                "handling strategies; both passages are required."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-47",
            query_text=(
                "How is a primary key selected from candidate keys in "
                "relational database design, and what uniqueness and null "
                "constraints must it satisfy?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain="Databases",
            domain_topic="Databases / Keys",
            exact_information_need=(
                "Explain that a primary key is a candidate key chosen by the "
                "designer to uniquely identify tuples in a table and must "
                "never be null."
            ),
            evidence_passage_ids=("s5v31_oa_db_001_s0000_c0092",),
            minimum_required_evidence_ids=("s5v31_oa_db_001_s0000_c0092",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage c0092 defines primary keys.",
        ),
        QueryDraft(
            query_id="Q-S5V31-48",
            query_text=(
                "How do logical data independence and physical data "
                "independence differ across the external, logical, and "
                "internal database schemas?"
            ),
            split=SPLIT_DEV,
            category=CAT_SAME_DOC_MULTI,
            domain="Databases",
            domain_topic="Databases / Schema Architecture",
            exact_information_need=(
                "Contrast logical data independence (changing the logical "
                "schema without altering external user views in c0048) with "
                "physical data independence (internal/logical schema immunity "
                "to storage structure changes in c0049)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_db_001_s0000_c0048",
                "s5v31_oa_db_001_s0000_c0049",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_db_001_s0000_c0048",
                "s5v31_oa_db_001_s0000_c0049",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0048 defines logical schema/independence while c0049 "
                "defines physical data independence."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-49",
            query_text=(
                "How does TCP establish a new transport connection using a "
                "three-way handshake?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain="Computer Networks",
            domain_topic="Networks / TCP Connection Setup",
            exact_information_need=(
                "Describe the TCP three-way handshake connection "
                "establishment phase on p. 95."
            ),
            evidence_passage_ids=("s5v31_oa_net_001_p0095_c0219",),
            minimum_required_evidence_ids=("s5v31_oa_net_001_p0095_c0219",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage p. 95 c0219 covers TCP 3-way.",
        ),
        QueryDraft(
            query_id="Q-S5V31-50",
            query_text=(
                "What routing-table aggregation challenge arises with "
                "variable-length prefix allocation under classless "
                "inter-domain routing?"
            ),
            split=SPLIT_DEV,
            category=CAT_TECH_PARAPHRASE,
            domain="Computer Networks",
            domain_topic="Networks / CIDR Subnetting",
            exact_information_need=(
                "Explain the difficulty with aggregatable variable-length "
                "subnets in CIDR (paraphrasing 'CIDR' as classless "
                "inter-domain routing)."
            ),
            evidence_passage_ids=("s5v31_oa_net_001_p0149_c0357",),
            minimum_required_evidence_ids=("s5v31_oa_net_001_p0149_c0357",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Paraphrase directly answered by p. 149 c0357.",
        ),
        QueryDraft(
            query_id="Q-S5V31-51",
            query_text=(
                "How does the Byzantine generals problem extend the setting "
                "of the two generals problem to three or more participants?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain="Distributed Systems",
            domain_topic="Distributed Systems / Fault Models",
            exact_information_need=(
                "Explain Lamport (1982) Byzantine generals problem setting "
                "with three or more armies communicating via messengers."
            ),
            evidence_passage_ids=("s5v31_oa_ds_001_s0000_c0037",),
            minimum_required_evidence_ids=("s5v31_oa_ds_001_s0000_c0037",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage c0037 describes Byzantine setup.",
        ),
        QueryDraft(
            query_id="Q-S5V31-52",
            query_text=(
                "How do Lamport timestamps construct a total order over "
                "events using (L(e), N(e)) pairs, and how do vector clocks "
                "generalize them to a per-node integer list?"
            ),
            split=SPLIT_DEV,
            category=CAT_SAME_DOC_MULTI,
            domain="Distributed Systems",
            domain_topic="Distributed Systems / Logical Time",
            exact_information_need=(
                "Combine Lamport timestamp total ordering via (L(e), N(e)) "
                "(c0088) with vector timestamps storing one integer per node "
                "in a vector (c0091)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_ds_001_s0000_c0088",
                "s5v31_oa_ds_001_s0000_c0091",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_ds_001_s0000_c0088",
                "s5v31_oa_ds_001_s0000_c0091",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0088 covers Lamport total order pairs while c0091 defines "
                "vector timestamps as per-node integer lists."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-53",
            query_text=(
                "Compare how transport-layer pipelining protocols like "
                "Go-Back-N and Selective Repeat handle reliable delivery over "
                "unreliable links with how the Two Generals problem models "
                "unreliable network faults in distributed system models."
            ),
            split=SPLIT_DEV,
            category=CAT_CROSS_DOC_MULTI,
            domain="Cross-Domain (CS Systems)",
            domain_topic="Networks & Distributed Systems / Reliability",
            exact_information_need=(
                "Connect CNP3's pipelined transport reliability (Go-Back-N / "
                "Selective Repeat over alternating bit in oa_net_001 p. 78) "
                "with Kleppmann's system-model abstraction of unreliable "
                "network faults in the Two Generals problem (oa_ds_001 c0042)."
            ),
            evidence_passage_ids=(
                "s5v31_oa_net_001_p0078_c0185",
                "s5v31_oa_ds_001_s0000_c0042",
            ),
            minimum_required_evidence_ids=(
                "s5v31_oa_net_001_p0078_c0185",
                "s5v31_oa_ds_001_s0000_c0042",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "oa_net_001 p. 78 covers transport pipelining protocols while "
                "oa_ds_001 c0042 formalizes Two Generals system models; both "
                "documents are required."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V31-54",
            query_text=(
                "What is the exact Linux kernel eBPF XDP packet-drop "
                "throughput in millions of packets per second measured on a "
                "Mellanox ConnectX-7 NIC?"
            ),
            split=SPLIT_DEV,
            category=CAT_NEGATIVE_CONTROL,
            domain="Negative Control (Absent)",
            domain_topic="OS & Networks Hardware (Absent)",
            exact_information_need=(
                "Negative control: eBPF XDP throughput benchmarks on Mellanox "
                "ConnectX-7 NICs are absent from all 1,958 Corpus v3.1 "
                "passages."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Verified absent across all 1,958 Corpus v3.1 passages."
            ),
        ),
    ]

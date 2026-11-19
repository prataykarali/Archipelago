"""Test-split terminology/paraphrase (5) and negative-control (5) drafts."""

from __future__ import annotations

from .builder import QueryDraft
from .constants import (
    CAT_NEGATIVE_CONTROL,
    CAT_TECH_PARAPHRASE,
    SPLIT_TEST,
)


def get_test_paraphrase_and_neg_drafts() -> list[QueryDraft]:
    """Return 10 test-split queries (5 paraphrase, 5 negative controls)."""
    return [
        # --- Technical terminology & paraphrase (5) ---
        QueryDraft(
            query_id="Q-S5V3-39",
            query_text=(
                "What alternative name is used in the signal processing "
                "literature for principal component analysis?"
            ),
            split=SPLIT_TEST,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="Math for ML / Terminology",
            exact_information_need=(
                "Identify that PCA is also known as the Karhunen-Loeve "
                "transform in the signal processing community."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0324_c0571",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0324_c0571",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Terminology lookup directly answered by MML p. 324 c0571."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-40",
            query_text=(
                "Which sparse L1-norm penalty regularizer for linear "
                "regression was introduced by Tibshirani (1996) for variable "
                "selection?"
            ),
            split=SPLIT_TEST,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="Math for ML / Regularization",
            exact_information_need=(
                "Identify LASSO (least absolute shrinkage and selection "
                "operator) for p = 1 regularization."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0309_c0542",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0309_c0542",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Terminology paraphrase directly answered by MML p. 309 c0542."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-41",
            query_text=(
                "Why do contemporary machine learning systems avoid hand "
                "determinant computations when checking matrix invertibility?"
            ),
            split=SPLIT_TEST,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="Math for ML / Numerical Linear Algebra",
            exact_information_need=(
                "Explain that direct numerical methods have superseded "
                "explicit determinant calculation for analyzing matrix "
                "invertibility in modern machine learning."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0109_c0177",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0109_c0177",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Paraphrased conceptual question directly answered by MML "
                "p. 109 c0177."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-42",
            query_text=(
                "In constrained text decoding, what architectural "
                "optimization do Willard and Louf suggest by lifting token "
                "masks higher up into the language model?"
            ),
            split=SPLIT_TEST,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="NLP / Guided Generation",
            exact_information_need=(
                "Explain that lifting masks higher into the model "
                "architecture could modulate which parameter slices are "
                "needed before performing unnecessary computations."
            ),
            evidence_passage_ids=("s5v3_local_oa_002_p0016_c0021",),
            minimum_required_evidence_ids=("s5v3_local_oa_002_p0016_c0021",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Paraphrase of 'guided generation' as 'constrained text "
                "decoding', directly answered by p. 16 c0021."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-43",
            query_text=(
                "How does METATRON represent environmental furniture and "
                "obstacles offline so the humanoid controller can interact "
                "with scenes?"
            ),
            split=SPLIT_TEST,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="Robotics / Scene Interaction",
            exact_information_need=(
                "State that each scene element is decomposed offline into "
                "geometric primitives / bounding boxes b_t specified by "
                "measured dimensions and poses."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_004_p0002_c0003",
                "s5v3_local_oa_004_p0003_c0008",
            ),
            minimum_required_evidence_ids=("s5v3_local_oa_004_p0003_c0008",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "METATRON p. 3 c0008 directly states offline decomposition "
                "into bounding boxes b_t; p. 2 c0003 adds supporting detail."
            ),
        ),
        # --- Negative controls (5) ---
        QueryDraft(
            query_id="Q-S5V3-44",
            query_text=(
                "How does the BBR congestion control algorithm estimate "
                "bottleneck bandwidth and round-trip propagation time to "
                "pace TCP packets?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="Computer Networks (Deferred)",
            exact_information_need=(
                "Negative control: TCP BBR congestion control is absent from "
                "all four verified OA documents in Corpus v3."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Verified absent across all 858 Corpus v3 passages; Computer "
                "Networks OA texts are deferred."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-45",
            query_text=(
                "How does FlashAttention-2 tile query, key, and value blocks "
                "into GPU SRAM to reduce HBM memory reads during Transformer "
                "self-attention?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="ML Systems (Absent)",
            exact_information_need=(
                "Negative control: FlashAttention-2 GPU SRAM/HBM tiling is "
                "absent from all four verified OA documents in Corpus v3."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of FlashAttention, SRAM, or HBM in all 858 "
                "Corpus v3 passages."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-46",
            query_text=(
                "What is the exact knee actuator peak torque in Newton-meters "
                "for the Boston Dynamics electric Atlas humanoid robot?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="Robotics (Absent)",
            exact_information_need=(
                "Negative control: Boston Dynamics electric Atlas specs do "
                "not appear in METATRON or any other Corpus v3 document."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of Boston Dynamics or Atlas across all 858 "
                "Corpus v3 passages (METATRON evaluates Unitree G1 and SOMA)."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-47",
            query_text=(
                "How does the Completely Fair Scheduler (CFS) in the Linux "
                "kernel use a red-black tree keyed by virtual runtime to "
                "schedule runnable processes?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="Operating Systems (Deferred)",
            exact_information_need=(
                "Negative control: Linux CFS scheduling is absent from all "
                "four verified OA documents in Corpus v3."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of Completely Fair Scheduler, virtual "
                "runtime, or red-black tree in all 858 Corpus v3 passages."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-48",
            query_text=(
                "What are the exact token-per-second throughput numbers for "
                "vLLM PagedAttention serving Mixtral-8x7B on an NVIDIA B200 "
                "GPU?"
            ),
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="LLM Serving (Absent)",
            exact_information_need=(
                "Negative control: vLLM PagedAttention and Mixtral-8x7B B200 "
                "benchmarks are absent from all four verified OA documents."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of vLLM, PagedAttention, Mixtral, or B200 "
                "across all 858 Corpus v3 passages."
            ),
        ),
    ]

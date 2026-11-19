"""Dev-split proposed query drafts (16 queries) grounded in Corpus v3."""

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


def get_dev_query_drafts() -> list[QueryDraft]:
    """Return the 16 proposed dev-split queries grounded in Corpus v3."""
    return [
        # --- Single-passage fact & concept (4) ---
        QueryDraft(
            query_id="Q-S5V3-01",
            query_text=(
                "In Dive into Deep Learning Chapter 3, under what matrix "
                "invertibility condition is the analytic solution for linear "
                "regression unique?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Machine Learning / Linear Regression",
            exact_information_need=(
                "State that w* = (X^T X)^(-1) X^T y is unique only when "
                "X^T X is invertible, i.e., when the columns of design "
                "matrix X are linearly independent."
            ),
            evidence_passage_ids=("s5v3_local_oa_001_p0001_c0008",),
            minimum_required_evidence_ids=("s5v3_local_oa_001_p0001_c0008",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query: c0008 states both the closed-form "
                "equation and the linear independence invertibility condition."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-02",
            query_text=(
                "How does Willard and Louf's Algorithm 2 apply a boolean mask "
                "to LLM output logits before sampling from the categorical "
                "distribution?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="NLP / Guided Generation",
            exact_information_need=(
                "Describe the per-step loop in Algorithm 2: compute logits "
                "alpha = LLM(s, theta), build mask m(s), apply elementwise "
                "product alpha_tilde = m * alpha, and sample from Categorical."
            ),
            evidence_passage_ids=("s5v3_local_oa_002_p0005_c0007",),
            minimum_required_evidence_ids=("s5v3_local_oa_002_p0005_c0007",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query: Algorithm 2 on p. 5 directly specifies "
                "the masking and Categorical sampling steps."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-03",
            query_text=(
                "How does Mathematics for Machine Learning define a symmetric "
                "positive definite matrix from an inner product?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Math for ML / Analytic Geometry",
            exact_information_need=(
                "State Definition 3.4: a symmetric matrix A in R^(n x n) "
                "satisfying x^T A x > 0 for all nonzero vectors x."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0080_c0124",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0080_c0124",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query: p. 80 contains Definition 3.4 and "
                "inequality (3.11)."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-04",
            query_text=(
                "What PPO discount factor and generalized advantage estimation "
                "parameter are used to train the METATRON expert trackers?"
            ),
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Robotics / Humanoid Control",
            exact_information_need=(
                "Report PPO discount factor 0.99 and GAE parameter 0.95 "
                "used for both METATRON expert trackers."
            ),
            evidence_passage_ids=("s5v3_local_oa_004_p0010_c0034",),
            minimum_required_evidence_ids=("s5v3_local_oa_004_p0010_c0034",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query: p. 10 Appendix I explicitly lists "
                "discount 0.99 and GAE 0.95."
            ),
        ),
        # --- Same-document multi-passage (3) ---
        QueryDraft(
            query_id="Q-S5V3-05",
            query_text=(
                "In Mathematics for Machine Learning, how do the prior, "
                "marginal likelihood (evidence), and Bayes' theorem fit "
                "together to form a posterior distribution?"
            ),
            split=SPLIT_DEV,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Math for ML / Probability",
            exact_information_need=(
                "Combine the definition of the prior p(x) in Bayes' theorem "
                "(p. 191) with the integral definition of marginal likelihood "
                "or evidence p(y) = integral p(y|x)p(x)dx (p. 192)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0191_c0321",
                "s5v3_local_oa_003_p0192_c0322",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0191_c0321",
                "s5v3_local_oa_003_p0192_c0322",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 191 defines the prior role in Bayes' theorem without the "
                "evidence integral, while p. 192 defines marginal likelihood "
                "p(y) = E_X[p(y|x)]; both passages are needed."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-06",
            query_text=(
                "How does Mathematics for Machine Learning connect the "
                "characteristic polynomial of a matrix to its determinant, "
                "trace, and eigenvalues?"
            ),
            split=SPLIT_DEV,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Math for ML / Matrix Decompositions",
            exact_information_need=(
                "Connect the characteristic polynomial coefficients c_0 = det(A) "
                "and c_{n-1} = (-1)^(n-1) tr(A) (p. 111) with Theorem 4.8 "
                "stating lambda is an eigenvalue iff it is a root of p_A(lambda) "
                "(p. 112)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0111_c0180",
                "s5v3_local_oa_003_p0112_c0182",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0111_c0180",
                "s5v3_local_oa_003_p0112_c0182",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 111 gives the determinant/trace coefficients of the "
                "characteristic polynomial, whereas Theorem 4.8 linking roots "
                "to eigenvalues appears on p. 112."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-07",
            query_text=(
                "In Willard and Louf's FSM-guided LLM generation, how does "
                "sub-sequence matching in Algorithm 3 enable constructing the "
                "state-to-vocabulary map in Algorithm 4?"
            ),
            split=SPLIT_DEV,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="NLP / Guided Generation",
            exact_information_need=(
                "Explain that Algorithm 3 finds FSM state sub-sequences "
                "accepting a vocabulary string from any state, and Algorithm 4 "
                "iterates over all v in V calling Algorithm 3 to populate "
                "state-to-token sets sigma."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_002_p0007_c0009",
                "s5v3_local_oa_002_p0008_c0010",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_002_p0007_c0009",
                "s5v3_local_oa_002_p0008_c0010",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Algorithm 3 (p. 7) defines sub-sequence matching while "
                "Algorithm 4 (p. 8) defines the map construction loop calling "
                "it; neither passage alone covers both stages."
            ),
        ),
        # --- Cross-document multi-passage (3) ---
        QueryDraft(
            query_id="Q-S5V3-08",
            query_text=(
                "Compare how Dive into Deep Learning Chapter 3 motivates "
                "squared loss via Gaussian noise with how Mathematics for "
                "Machine Learning Chapter 9 derives the maximum likelihood "
                "noise variance estimate sigma_ML^2."
            ),
            split=SPLIT_DEV,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="Machine Learning / Linear Regression",
            exact_information_need=(
                "Contrast D2L's fixed-sigma negative log-likelihood motivation "
                "for squared loss under N(0, sigma^2) noise (local_oa_001) "
                "with MML's partial derivative of log-likelihood w.r.t. "
                "sigma^2 to obtain sigma_ML^2 (local_oa_003)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_001_p0001_c0018",
                "s5v3_local_oa_003_p0304_c0532",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_001_p0001_c0018",
                "s5v3_local_oa_003_p0304_c0532",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "D2L c0018 assumes sigma is fixed to drop constant terms, "
                "whereas MML p. 304 explicitly differentiates w.r.t. sigma^2 "
                "for sigma_ML^2; neither document contains the other's treatment."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-09",
            query_text=(
                "How does the conditional distribution construction in "
                "Mathematics for Machine Learning Chapter 6 relate to "
                "forming an un-normalized conditional next-token distribution "
                "by masking logits in Willard and Louf?"
            ),
            split=SPLIT_DEV,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="NLP / Probabilistic Modeling",
            exact_information_need=(
                "Link MML's sum/product rule factorization into marginal and "
                "conditional distributions (local_oa_003 p. 191) with "
                "Willard & Louf's discrete logit-masking formulation of an "
                "un-normalized conditional distribution (local_oa_002 p. 4)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0191_c0320",
                "s5v3_local_oa_002_p0004_c0005",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0191_c0320",
                "s5v3_local_oa_002_p0004_c0005",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "MML p. 191 provides general probabilistic factorization while "
                "Willard & Louf p. 4 applies boolean masks to discrete LLM "
                "logits; cross-document synthesis is strictly required."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-10",
            query_text=(
                "How does METATRON's deployment architecture separate a "
                "training-only privileged posterior encoder from a prior "
                "encoder, and how does this compare to Bayesian inference "
                "over latent parameters in Mathematics for Machine Learning?"
            ),
            split=SPLIT_DEV,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="Robotics / Probabilistic Inference",
            exact_information_need=(
                "Combine METATRON's training-only privileged posterior vs "
                "deployment-time prior path (local_oa_004 p. 3, p. 11) with "
                "MML's Bayesian inference over unknown parameters using a "
                "posterior distribution for prediction (local_oa_003 p. 309)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_004_p0003_c0010",
                "s5v3_local_oa_004_p0011_c0038",
                "s5v3_local_oa_003_p0309_c0543",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_004_p0011_c0038",
                "s5v3_local_oa_003_p0309_c0543",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "METATRON p. 11 specifies deployment using the prior path "
                "without the privileged posterior, while MML p. 309 explains "
                "using the posterior distribution for prediction; both docs "
                "are required."
            ),
        ),
        # --- Technical terminology & paraphrase (3) ---
        QueryDraft(
            query_id="Q-S5V3-11",
            query_text=(
                "Why are user-configured settings like batch cardinality and "
                "step size distinguished from learned weights in iterative "
                "minibatch optimization?"
            ),
            split=SPLIT_DEV,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="Machine Learning / Optimization",
            exact_information_need=(
                "Identify that minibatch size and learning rate are "
                "hyperparameters not updated inside the training loop, and "
                "that minibatch gradients are normalized by |B|."
            ),
            evidence_passage_ids=("s5v3_local_oa_001_p0001_c0012",),
            minimum_required_evidence_ids=("s5v3_local_oa_001_p0001_c0012",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Paraphrase of hyperparameters/minibatch normalization "
                "directly answered by D2L c0012."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-12",
            query_text=(
                "Why is reverse-mode automatic differentiation preferred for "
                "computing parameter sensitivities in multi-layer neural "
                "networks?"
            ),
            split=SPLIT_DEV,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="Math for ML / Vector Calculus",
            exact_information_need=(
                "Explain that reverse-mode automatic differentiation is "
                "backpropagation and is favored when input/parameter "
                "dimensionality is much larger than scalar loss output."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0168_c0279",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0168_c0279",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Terminology paraphrase ('parameter sensitivities' = loss "
                "gradients) answered directly by MML p. 168."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-13",
            query_text=(
                "At what control frequency and simulator physics sub-stepping "
                "ratio does the frozen METATRON controller emit joint targets?"
            ),
            split=SPLIT_DEV,
            category=CAT_TECH_PARAPHRASE,
            domain_topic="Robotics / Humanoid Control",
            exact_information_need=(
                "State that the policy updates targets every 20 ms (50 Hz) "
                "with four simulator physics steps per action."
            ),
            evidence_passage_ids=("s5v3_local_oa_004_p0014_c0049",),
            minimum_required_evidence_ids=("s5v3_local_oa_004_p0014_c0049",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage paraphrase answered directly by METATRON "
                "p. 14 c0049."
            ),
        ),
        # --- Negative controls (3) ---
        QueryDraft(
            query_id="Q-S5V3-14",
            query_text=(
                "How does the Raft consensus protocol use term numbers and "
                "leader heartbeats to prevent split-brain elections in "
                "replicated state machines?"
            ),
            split=SPLIT_DEV,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="Distributed Systems (Deferred)",
            exact_information_need=(
                "Negative control: Raft consensus protocol is absent from all "
                "four verified OA documents in Corpus v3."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Verified absent across all 858 Corpus v3 passages; "
                "Distributed Systems OA texts are deferred."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-15",
            query_text=(
                "What is the exact NVMe PCIe Gen5 sequential read bandwidth "
                "limit reported for Samsung 990 Pro SSDs in Linux io_uring "
                "benchmarks?"
            ),
            split=SPLIT_DEV,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="Systems / Storage (Absent)",
            exact_information_need=(
                "Negative control: NVMe/io_uring hardware benchmarks do not "
                "appear anywhere in Corpus v3."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of NVMe, io_uring, or Samsung 990 in all "
                "858 Corpus v3 passages."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-16",
            query_text=(
                "How does Multi-Version Concurrency Control (MVCC) in "
                "PostgreSQL use transaction IDs and vacuuming to implement "
                "snapshot isolation?"
            ),
            split=SPLIT_DEV,
            category=CAT_NEGATIVE_CONTROL,
            domain_topic="Databases (Deferred)",
            exact_information_need=(
                "Negative control: PostgreSQL MVCC and snapshot isolation are "
                "absent from all four verified OA documents in Corpus v3."
            ),
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "Zero occurrences of PostgreSQL, MVCC, or snapshot isolation "
                "in all 858 Corpus v3 passages; Databases OA texts deferred."
            ),
        ),
    ]

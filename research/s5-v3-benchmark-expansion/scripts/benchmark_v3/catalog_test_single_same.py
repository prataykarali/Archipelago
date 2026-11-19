"""Test-split single-passage (8) and same-doc multi-passage (7) drafts."""

from __future__ import annotations

from .builder import QueryDraft
from .constants import (
    CAT_SAME_DOC_MULTI,
    CAT_SINGLE_PASSAGE,
    SPLIT_TEST,
)


def get_test_single_and_same_doc_drafts() -> list[QueryDraft]:
    """Return 15 test-split queries (8 single-passage, 7 same-doc multi)."""
    return [
        # --- Single-passage fact & concept (8) ---
        QueryDraft(
            query_id="Q-S5V3-17",
            query_text=(
                "Why is the quadratic form of squared error loss described as "
                "a double-edged sword in Dive into Deep Learning Chapter 3?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Machine Learning / Loss Functions",
            exact_information_need=(
                "Explain that large differences between estimates and targets "
                "produce disproportionately large loss contributions due to "
                "the quadratic form."
            ),
            evidence_passage_ids=("s5v3_local_oa_001_p0001_c0006",),
            minimum_required_evidence_ids=("s5v3_local_oa_001_p0001_c0006",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query directly answered by D2L c0006."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-18",
            query_text=(
                "What tuple of components defines a pushdown automaton in "
                "Willard and Louf's CFG-guided generation formulation?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="NLP / Formal Grammars",
            exact_information_need=(
                "State the 6-tuple (Q, Sigma, Gamma, delta, q0, F) where "
                "Gamma is the finite stack alphabet and delta maps Q x "
                "Sigma_eps x Gamma_eps to subsets of Q x Gamma_eps."
            ),
            evidence_passage_ids=("s5v3_local_oa_002_p0014_c0017",),
            minimum_required_evidence_ids=("s5v3_local_oa_002_p0014_c0017",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query: p. 14 c0017 gives the complete PDA "
                "formal definition."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-19",
            query_text=(
                "In Willard and Louf's Python grammar experiments, roughly "
                "how large in megabytes are naively constructed parser and "
                "FSM state indices?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="NLP / Guided Generation",
            exact_information_need=(
                "Report that even naively constructed indices containing "
                "unused and redundant parser/FSM state configurations are "
                "only around 50 MB."
            ),
            evidence_passage_ids=("s5v3_local_oa_002_p0016_c0020",),
            minimum_required_evidence_ids=("s5v3_local_oa_002_p0016_c0020",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage factual query directly answered on p. 16 c0020."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-20",
            query_text=(
                "What is the Cholesky factor L of a symmetric positive "
                "definite matrix in Mathematics for Machine Learning, and is "
                "it unique?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Math for ML / Matrix Decompositions",
            exact_information_need=(
                "State that L is the lower-triangular Cholesky factor of an "
                "SPD matrix A = L L^T and that L is unique."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0120_c0198",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0120_c0198",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query answered directly by MML p. 120 c0198."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-21",
            query_text=(
                "How does Mathematics for Machine Learning relate the "
                "singular value decomposition of a symmetric positive "
                "definite matrix to its eigendecomposition?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Math for ML / Matrix Decompositions",
            exact_information_need=(
                "Explain that for an SPD matrix S = U Sigma V^T, setting "
                "U = P = V and D = Sigma shows that the SVD of an SPD matrix "
                "is its eigendecomposition."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0129_c0213",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0129_c0213",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query answered directly by MML p. 129 c0213."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-22",
            query_text=(
                "Why is hinge loss used as a surrogate objective in soft "
                "margin support vector machines according to Mathematics for "
                "Machine Learning?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Math for ML / Support Vector Machines",
            exact_information_need=(
                "Explain that hinge loss max{0, 1 - t} is a convex upper "
                "bound of zero-one loss."
            ),
            evidence_passage_ids=("s5v3_local_oa_003_p0388_c0694",),
            minimum_required_evidence_ids=("s5v3_local_oa_003_p0388_c0694",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query directly answered by MML p. 388 c0694."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-23",
            query_text=(
                "How does the METATRON push robustness benchmark define "
                "success for horizontal torso pushes during XY waypoint "
                "reaching?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Robotics / Evaluation",
            exact_information_need=(
                "State that pushes last 100 ms every 1-2 s during the first "
                "5 s, and success requires reaching within 0.5 m of the goal "
                "within 10 s while keeping relative torso height >= 0.45."
            ),
            evidence_passage_ids=("s5v3_local_oa_004_p0008_c0024",),
            minimum_required_evidence_ids=("s5v3_local_oa_004_p0008_c0024",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query directly answered by Table III caption "
                "on METATRON p. 8 c0024."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-24",
            query_text=(
                "At what relative torso height thresholds does METATRON's "
                "automatic recovery state machine begin and end?"
            ),
            split=SPLIT_TEST,
            category=CAT_SINGLE_PASSAGE,
            domain_topic="Robotics / Humanoid Control",
            exact_information_need=(
                "State that torso height is computed by FK relative to the "
                "lowest reconstructed body point, and recovery begins below "
                "0.65H."
            ),
            evidence_passage_ids=("s5v3_local_oa_004_p0013_c0047",),
            minimum_required_evidence_ids=("s5v3_local_oa_004_p0013_c0047",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale=(
                "Single-passage query directly answered by METATRON p. 13 c0047."
            ),
        ),
        # --- Same-document multi-passage (7) ---
        QueryDraft(
            query_id="Q-S5V3-25",
            query_text=(
                "In Dive into Deep Learning Chapter 3, how does minibatch "
                "stochastic gradient descent bridge single-example SGD and "
                "why does linear regression's global minimum differ from deep "
                "network loss surfaces?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Machine Learning / Optimization",
            exact_information_need=(
                "Combine the minibatch sampling and gradient averaging step "
                "(c0010-c0011) with the contrast between linear regression's "
                "global minimum (full-rank X) and deep network loss surfaces "
                "(c0013)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_001_p0001_c0010",
                "s5v3_local_oa_001_p0001_c0011",
                "s5v3_local_oa_001_p0001_c0013",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_001_p0001_c0011",
                "s5v3_local_oa_001_p0001_c0013",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "c0011 describes minibatch sampling/gradient averaging while "
                "c0013 contrasts linear regression's global minimum with "
                "deep network loss surfaces."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-26",
            query_text=(
                "In Willard and Louf, why does naive per-step partial "
                "matching incur O(N) vocabulary cost, and how does extending "
                "FSM indexing to LALR(1) parser REDUCE configurations enable "
                "CFG-guided generation?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="NLP / Guided Generation",
            exact_information_need=(
                "Combine the O(N) per-iteration vocabulary scaling problem "
                "(p. 4 c0006) with the LALR(1) sub-stack REDUCE parser "
                "configuration extension for CFGs (p. 15 c0019)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_002_p0004_c0006",
                "s5v3_local_oa_002_p0015_c0019",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_002_p0004_c0006",
                "s5v3_local_oa_002_p0015_c0019",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 4 states the O(N) scaling bottleneck of naive partial "
                "matching, while p. 15 details LALR(1) REDUCE sub-stack "
                "configurations; both are needed."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-27",
            query_text=(
                "How does Mathematics for Machine Learning formulate "
                "principal component analysis both as a constrained maximum "
                "variance Lagrangian problem and as a low-rank reconstruction "
                "approximation?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Math for ML / Dimensionality Reduction",
            exact_information_need=(
                "Combine the maximum-variance Lagrangian L(b1, lambda) = "
                "b1^T S b1 + lambda1(1 - b1^T b1) (p. 328) with the low-rank "
                "matrix approximation / average squared reconstruction error "
                "equivalence (p. 340)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0328_c0579",
                "s5v3_local_oa_003_p0340_c0602",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0328_c0579",
                "s5v3_local_oa_003_p0340_c0602",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 328 derives the constrained variance Lagrangian while "
                "p. 340 connects PCA to low-rank reconstruction; both are "
                "needed for the dual formulation."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-28",
            query_text=(
                "In Mathematics for Machine Learning Chapter 11, why is a "
                "Gaussian mixture model more expressive than a single "
                "Gaussian, and how does the EM algorithm iteratively learn "
                "its parameters?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Math for ML / Density Estimation",
            exact_information_need=(
                "Combine the convex-combination expressiveness of GMMs over "
                "a single Gaussian (p. 356) with Dempster et al.'s iterative "
                "EM scheme for maximum likelihood/MAP parameter estimation "
                "(p. 367)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0356_c0636",
                "s5v3_local_oa_003_p0367_c0655",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0356_c0636",
                "s5v3_local_oa_003_p0367_c0655",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 356 introduces the GMM convex combination while p. 367 "
                "presents the EM algorithm; neither passage covers both."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-29",
            query_text=(
                "How does Mathematics for Machine Learning transform the "
                "primal soft-margin support vector machine into its dual via "
                "Lagrange multipliers and then apply nonlinear kernels?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Math for ML / Support Vector Machines",
            exact_information_need=(
                "Combine the Lagrange-multiplier dual formulation D(xi, "
                "alpha, gamma) from primal variables w, b, xi (p. 389, 391) "
                "with replacing feature maps phi(x) by nonlinear kernels "
                "(p. 394)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0389_c0697",
                "s5v3_local_oa_003_p0391_c0700",
                "s5v3_local_oa_003_p0394_c0707",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0389_c0697",
                "s5v3_local_oa_003_p0394_c0707",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 389/391 derive the dual Lagrangian while p. 394 explains "
                "how nonlinear kernels yield nonlinear boundaries within the "
                "linear SVM framework."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-30",
            query_text=(
                "In Mathematics for Machine Learning Chapter 7, how are "
                "constrained optimization problems converted using Lagrange "
                "multipliers and how do Legendre-Fenchel conjugates connect "
                "to convex duality?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Math for ML / Continuous Optimization",
            exact_information_need=(
                "Combine the min-max duality inequality with Lagrange "
                "multipliers (p. 241) and the Legendre-Fenchel conjugate "
                "connection to dual convex optimization problems (p. 251)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0241_c0414",
                "s5v3_local_oa_003_p0251_c0429",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0241_c0414",
                "s5v3_local_oa_003_p0251_c0429",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 241 proves the min-max weak duality inequality while "
                "p. 251 links Legendre-Fenchel conjugates to the dual problem."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-31",
            query_text=(
                "How does METATRON's three-stage pipeline separate PPO "
                "motion-tracking expert training from supervised student "
                "distillation and runtime prompt-constructing skills?"
            ),
            split=SPLIT_TEST,
            category=CAT_SAME_DOC_MULTI,
            domain_topic="Robotics / Humanoid Control",
            exact_information_need=(
                "Combine the three-stage separation (PPO experts, supervised "
                "distillation, runtime skills on p. 10 c0032) with the "
                "distilled student architecture and action-smoothness/dynamics "
                "training setup (p. 5 c0017 and p. 11 c0039)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_004_p0010_c0032",
                "s5v3_local_oa_004_p0005_c0017",
                "s5v3_local_oa_004_p0011_c0039",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_004_p0010_c0032",
                "s5v3_local_oa_004_p0005_c0017",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale=(
                "p. 10 c0032 summarizes the three stages while p. 5 c0017 "
                "details the four-expert policy distillation and frozen "
                "skill execution without retraining."
            ),
        ),
    ]

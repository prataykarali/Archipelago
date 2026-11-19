"""Test-split cross-document multi-passage (7) query drafts."""

from __future__ import annotations

from .builder import QueryDraft
from .constants import CAT_CROSS_DOC_MULTI, SPLIT_TEST


def get_test_cross_doc_drafts() -> list[QueryDraft]:
    """Return 7 test-split cross-document multi-passage queries."""
    return [
        QueryDraft(
            query_id="Q-S5V3-32",
            query_text=(
                "Compare how Dive into Deep Learning Chapter 3 introduces "
                "linear regression with squared loss against how Mathematics "
                "for Machine Learning Chapter 9 prevents MLE overfitting "
                "using MAP estimation and regularized least squares."
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="Machine Learning / Linear Regression",
            exact_information_need=(
                "Contrast D2L's squared-loss linear regression objective "
                "(local_oa_001 c0005) with MML's MAP log-posterior and "
                "regularized least squares ||y - Phi theta||^2 + lambda "
                "||theta||_2^2 ensuring invertibility (local_oa_003 p. 308)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_001_p0001_c0005",
                "s5v3_local_oa_003_p0308_c0540",
                "s5v3_local_oa_003_p0308_c0541",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_001_p0001_c0005",
                "s5v3_local_oa_003_p0308_c0541",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "D2L c0005 covers unregularized squared loss while MML p. 308 "
                "introduces MAP/regularized least squares; both docs required."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-33",
            query_text=(
                "How does Dive into Deep Learning Chapter 3's treatment of "
                "minibatch stochastic gradient descent compare with the "
                "momentum-based gradient descent update rule presented in "
                "Mathematics for Machine Learning Chapter 7?"
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="Machine Learning / Optimization",
            exact_information_need=(
                "Contrast D2L's minibatch SGD motivation (local_oa_001 c0009) "
                "with MML's momentum update rule combining current and "
                "previous gradients via Delta x_i (local_oa_003 p. 237)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_001_p0001_c0009",
                "s5v3_local_oa_003_p0237_c0407",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_001_p0001_c0009",
                "s5v3_local_oa_003_p0237_c0407",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "D2L c0009 motivates minibatch SGD without momentum, whereas "
                "MML p. 237 defines the momentum update equation; both docs "
                "are required."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-34",
            query_text=(
                "How does Dive into Deep Learning Chapter 3 frame linear "
                "regression as a single-layer neural network, and how does "
                "Mathematics for Machine Learning Chapter 5 generalize "
                "gradient computation across multi-layer neural networks "
                "using backpropagation?"
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="Machine Learning / Neural Networks",
            exact_information_need=(
                "Connect D2L's subsumption of linear regression inside "
                "neural network notation (local_oa_001 c0019) with MML's "
                "multi-layer backward pass computing loss gradients via the "
                "chain rule (local_oa_003 p. 167, p. 170)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_001_p0001_c0019",
                "s5v3_local_oa_003_p0167_c0277",
                "s5v3_local_oa_003_p0170_c0282",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_001_p0001_c0019",
                "s5v3_local_oa_003_p0167_c0277",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "D2L c0019 frames linear regression as a neural network "
                "without multi-layer backprop, while MML p. 167 shows the "
                "multi-layer backward pass."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-35",
            query_text=(
                "How does Mathematics for Machine Learning Chapter 3 define "
                "the Euclidean L2 norm, and how does METATRON use L2 "
                "normalization to project sampled latent vectors onto the "
                "unit sphere and regularize action diversity?"
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="Robotics / Geometry",
            exact_information_need=(
                "Combine MML's definition of the Euclidean L2 norm "
                "(local_oa_003 p. 77) with METATRON's unit-sphere latent "
                "projection z_t = z_tilde / ||z_tilde||_2 (local_oa_004 p. 3) "
                "and L2 diversity loss L_div (p. 12)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0077_c0118",
                "s5v3_local_oa_004_p0003_c0009",
                "s5v3_local_oa_004_p0012_c0040",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0077_c0118",
                "s5v3_local_oa_004_p0003_c0009",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "MML p. 77 defines Euclidean vs Manhattan norms while "
                "METATRON p. 3 applies L2 normalization onto the unit sphere; "
                "neither doc covers the other."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-36",
            query_text=(
                "Compare how Willard and Louf guide an LLM to produce valid "
                "Python syntax using CFG/LALR(1) token masking with how "
                "METATRON uses an LLM coding agent to iteratively refine "
                "skill code via simulation feedback."
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="NLP & Robotics / LLM Code Generation",
            exact_information_need=(
                "Contrast Willard & Louf's syntax-constrained decoding for "
                "Python via CFG/LALR(1) parsers (local_oa_002 p. 2, p. 13) "
                "with METATRON's closed-loop LLM coding agent refining skill "
                "code from simulation evaluation feedback (local_oa_004 p. 4)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_002_p0002_c0003",
                "s5v3_local_oa_002_p0013_c0014",
                "s5v3_local_oa_004_p0004_c0013",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_002_p0002_c0003",
                "s5v3_local_oa_004_p0004_c0013",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "Willard & Louf p. 2 covers syntactic CFG/LALR(1) guidance "
                "while METATRON p. 4 covers iterative simulation-feedback "
                "skill refinement; cross-document comparison is necessary."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-37",
            query_text=(
                "How does Mathematics for Machine Learning Chapter 9's "
                "maximum likelihood estimation over nonlinear basis features "
                "Phi(x) extend the vectorized linear model y_hat = Xw + b "
                "presented in Dive into Deep Learning Chapter 3?"
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="Machine Learning / Linear Regression",
            exact_information_need=(
                "Connect D2L's vectorized affine prediction y_hat = Xw + b "
                "(local_oa_001 c0004) with MML's polynomial/nonlinear feature "
                "mapping f(x) = phi^T(x) theta that remains linear in "
                "parameters theta (local_oa_003 p. 302)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_001_p0001_c0004",
                "s5v3_local_oa_003_p0302_c0528",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_001_p0001_c0004",
                "s5v3_local_oa_003_p0302_c0528",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "D2L c0004 gives the raw-feature matrix equation Xw + b while "
                "MML p. 302 generalizes to nonlinear basis features phi(x)."
            ),
        ),
        QueryDraft(
            query_id="Q-S5V3-38",
            query_text=(
                "Contrast how Mathematics for Machine Learning Chapter 8 "
                "distinguishes non-probabilistic empirical risk minimization "
                "from Bayesian inference with how Willard and Louf treat an "
                "LLM as a function returning a discrete next-token "
                "probability distribution."
            ),
            split=SPLIT_TEST,
            category=CAT_CROSS_DOC_MULTI,
            domain_topic="ML Theory & NLP / Probabilistic Models",
            exact_information_need=(
                "Combine MML's distinction between ERM point estimates and "
                "probabilistic models (local_oa_003 p. 263) with Willard & "
                "Louf's definition of LLM(s, theta) returning next-token "
                "logits alpha in R^N defining a discrete probability "
                "distribution (local_oa_002 p. 3)."
            ),
            evidence_passage_ids=(
                "s5v3_local_oa_003_p0263_c0450",
                "s5v3_local_oa_002_p0003_c0004",
            ),
            minimum_required_evidence_ids=(
                "s5v3_local_oa_003_p0263_c0450",
                "s5v3_local_oa_002_p0003_c0004",
            ),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=True,
            shortcut_found=False,
            shortcut_rationale=(
                "MML p. 263 contrasts ERM vs probabilistic predictors while "
                "Willard & Louf p. 3 formalizes LLM next-token distributions; "
                "both documents are required."
            ),
        ),
    ]

"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
import os
import random
import re
from typing import Any
from . import _deps as _rt  # noqa: F401


logger = logging.getLogger(__name__)


@dataclass
class DiagnosticMCQ:
    id: str
    concept_id: str
    concept_name: str
    question: str
    options: dict[str, str]  # Exactly 4 options: {"A": ..., "B": ..., "C": ..., "D": ...}
    correct_option: str       # "A" | "B" | "C" | "D"
    explanation: str
    citation: str
    difficulty: str = "intermediate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_VERIFIED_QUESTION_BANK: dict[str, dict[str, Any]] = {
    "transformer": {
        "question": "According to Vaswani et al. (2017), what fundamental architectural choice allows the Transformer to discard recurrence and convolutions entirely?",
        "options": {
            "A": "Stacked recurrent LSTM gates with bidirectional hidden memory cells",
            "B": "Multi-head self-attention mechanisms capturing global token dependencies in parallel",
            "C": "Iterative graph convolutional filters operating on adjacency matrices",
            "D": "Contractive autoencoding projections with localized receptive fields",
        },
        "correct_option": "B",
        "explanation": "Vaswani et al. (2017) demonstrated that multi-head self-attention allows modeling arbitrary token interactions in constant sequential operations without recurrence.",
        "citation": "Vaswani et al. (2017) 'Attention Is All You Need', NeurIPS 2017.",
        "difficulty": "intermediate",
    },
    "attention_mechanism": {
        "question": "In the scaled dot-product attention formula Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V, why is the dot product divided by sqrt(d_k)?",
        "options": {
            "A": "To ensure orthogonal projection between query and key vector subspaces",
            "B": "To prevent large dot products from pushing the softmax function into regions with vanishing gradients",
            "C": "To enforce sparsity by zeroing out low-magnitude activation coordinates",
            "D": "To normalize the trace of the query-key covariance matrix to unit variance",
        },
        "correct_option": "B",
        "explanation": "As key dimension d_k grows large, dot products grow in magnitude, pushing softmax into regions with extremely small gradients. Scaling by 1/sqrt(d_k) counteracts this effect.",
        "citation": "Vaswani et al. (2017) 'Attention Is All You Need', Section 3.2.1.",
        "difficulty": "intermediate",
    },
    "neural_network": {
        "question": "What is the primary role of non-linear activation functions in multi-layer feedforward neural networks?",
        "options": {
            "A": "They enforce numerical precision limits on floating-point weight updates",
            "B": "They allow the network to approximate non-linear functions rather than collapsing into a single linear map",
            "C": "They eliminate the requirement for backpropagating error gradients",
            "D": "They guarantee convex optimization landscapes across all loss surfaces",
        },
        "correct_option": "B",
        "explanation": "Without non-linearities, any composition of linear matrix transformations remains purely linear. Non-linear activations grant universal function approximation capacity.",
        "citation": "Goodfellow, Bengio, & Courville (2016) 'Deep Learning', Chapter 6.",
        "difficulty": "foundational",
    },
    "fine_tuning": {
        "question": "How does parameter-efficient fine-tuning (PEFT) fundamentally differ from traditional full fine-tuning of large pre-trained language models?",
        "options": {
            "A": "It freezes pre-trained backbone weights and only updates a small subset or adapter parameters",
            "B": "It retraining all model weights from random initialization on task-specific supervision",
            "C": "It quantizes all float32 weights into 1-bit integers without gradient computation",
            "D": "It replaces all attention heads with static n-gram probability lookup tables",
        },
        "correct_option": "A",
        "explanation": "PEFT methods like LoRA freeze the bulk of pre-trained model weights and inject trainable low-rank decomposition matrices, dramatically reducing memory and storage overhead.",
        "citation": "Hu et al. (2021) 'LoRA: Low-Rank Adaptation of Large Language Models', ICLR 2022.",
        "difficulty": "intermediate",
    },
    "low_rank_adaptation": {
        "question": "In LoRA (Hu et al., 2021), how is the weight update matrix Delta W in R^{d x k} parameterized during adaptation?",
        "options": {
            "A": "As a full-rank dense matrix Delta W updated via standard Adam momentum",
            "B": "As a low-rank factorization Delta W = B * A, where B in R^{d x r} and A in R^{r x k} with rank r << min(d, k)",
            "C": "As an orthogonal Givens rotation matrix with unit determinant",
            "D": "As a diagonal sparse projection matrix containing strictly binary masks",
        },
        "correct_option": "B",
        "explanation": "LoRA hypothesizes that parameter updates have low intrinsic dimension, parameterizing Delta W = B * A with rank r << min(d, k), reducing trainable parameters by up to 10,000x.",
        "citation": "Hu et al. (2021) 'LoRA: Low-Rank Adaptation of Large Language Models', Section 4.1.",
        "difficulty": "intermediate",
    },
    "linear_algebra": {
        "question": "What mathematical property characterizes two orthogonal vectors u and v in Euclidean space R^n?",
        "options": {
            "A": "Their vector cross product produces a scalar value of 1.0",
            "B": "Their inner product (dot product) u^T v equals exactly zero",
            "C": "Their Euclidean norms must both be equal to 1.0",
            "D": "Their linear combination spans the entire n-dimensional coordinate space",
        },
        "correct_option": "B",
        "explanation": "Two non-zero vectors are defined to be orthogonal if and only if their inner product equals zero: <u, v> = u^T v = 0.",
        "citation": "Strang, G. (2016) 'Introduction to Linear Algebra', 5th Edition, Chapter 4.",
        "difficulty": "foundational",
    },
    "matrix_multiplication": {
        "question": "For a matrix multiplication C = A * B to be mathematically defined, which dimensional compatibility condition must be satisfied?",
        "options": {
            "A": "The number of columns in A must equal the number of rows in B",
            "B": "Both matrices A and B must be square matrices of identical dimension",
            "C": "The determinant of both A and B must be strictly non-zero",
            "D": "The number of rows in A must equal the number of columns in B",
        },
        "correct_option": "A",
        "explanation": "If A is of size (m x k), then B must be of size (k x n) for the matrix product C of size (m x n) to exist.",
        "citation": "Strang, G. (2016) 'Introduction to Linear Algebra', Chapter 2.",
        "difficulty": "foundational",
    },
    "gradient_descent": {
        "question": "What does the negative gradient -grad_theta L(theta) of a differentiable loss function indicate during parameter optimization?",
        "options": {
            "A": "The global minimum coordinates of the parameter objective space",
            "B": "The direction of steepest local descent in the parameter space",
            "C": "The condition number of the Hessian curvature tensor",
            "D": "The rate of variance convergence across mini-batch samples",
        },
        "correct_option": "B",
        "explanation": "The gradient vector points in the direction of greatest instantaneous increase of a function; therefore, its negative points in the direction of steepest descent.",
        "citation": "Rumelhart, Hinton, & Williams (1986) 'Learning representations by back-propagating errors', Nature 323.",
        "difficulty": "foundational",
    },
    "loss_function": {
        "question": "Why is cross-entropy loss preferred over mean squared error (MSE) for multi-class classification with softmax outputs?",
        "options": {
            "A": "It converts multi-class problems into independent binary regression steps",
            "B": "Its derivative avoids saturation and vanishing gradients when predicted probabilities diverge from target labels",
            "C": "It guarantees that model parameters converge within a fixed polynomial number of epochs",
            "D": "It eliminates the need for computing matrix transpositions during backpropagation",
        },
        "correct_option": "B",
        "explanation": "Combining cross-entropy loss with softmax yields linear error terms (p - y), avoiding the gradient saturation that occurs when MSE is paired with sigmoidal/softmax activations.",
        "citation": "Goodfellow, Bengio, & Courville (2016) 'Deep Learning', Chapter 6.2.2.",
        "difficulty": "foundational",
    },
    "bert": {
        "question": "What pre-training objective allows BERT (Devlin et al., 2018) to build deep bidirectional representations unlike standard autoregressive models?",
        "options": {
            "A": "Next Token Prediction with causal upper-triangular masking",
            "B": "Masked Language Modeling (MLM) and Next Sentence Prediction (NSP)",
            "C": "Contrastive Triplet Margin Loss over sentence pairs",
            "D": "Variational Evidence Lower Bound maximization across latent states",
        },
        "correct_option": "B",
        "explanation": "BERT masks a subset of input tokens at random and trains the deep bidirectional Transformer encoder to predict the masked tokens based on both left and right context.",
        "citation": "Devlin et al. (2018) 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding', NAACL 2019.",
        "difficulty": "intermediate",
    },
    "retrieval_augmented_generation": {
        "question": "According to Lewis et al. (2020), what is the core architectural advantage of Retrieval-Augmented Generation (RAG)?",
        "options": {
            "A": "It replaces neural parameter weights with an external database index entirely",
            "B": "It combines parametric memory (pre-trained seq2seq model) with non-parametric memory (dense passage retrieval)",
            "C": "It removes all token limits by compressing input context into scalar eigenvalues",
            "D": "It guarantees zero hallucination risk across arbitrary open-domain prompts",
        },
        "correct_option": "B",
        "explanation": "RAG combines pre-trained parametric generator weights with non-parametric vector retrieval, allowing models to cite external knowledge and update facts without re-training.",
        "citation": "Lewis et al. (2020) 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks', NeurIPS 2020.",
        "difficulty": "intermediate",
    },
    "recurrent_neural_network": {
        "question": "What architectural challenge in standard Vanilla Recurrent Neural Networks (RNNs) do LSTMs specifically address?",
        "options": {
            "A": "Inability to process non-textual input modalities",
            "B": "Exploding and vanishing gradients across long sequential dependency horizons",
            "C": "Requirement of square weight matrices in recurrent hidden states",
            "D": "Incompatibility with stochastic gradient descent optimization",
        },
        "correct_option": "B",
        "explanation": "Standard RNNs suffer from vanishing/exploding gradients when backpropagating through time. LSTMs introduce constant error carousels and gating mechanisms to preserve long-range dependencies.",
        "citation": "Hochreiter & Schmidhuber (1997) 'Long Short-Term Memory', Neural Computation 9(8).",
        "difficulty": "intermediate",
    },
}


def _generate_slm_mcq(
    concept_id: str,
    concept_name: str,
    summary: str,
    difficulty: str = "intermediate",
    citation: str = "",
    q_index: int = 1,
    ollama_host: str | None = None,
) -> DiagnosticMCQ | None:
    """Generate a simple, clear 4-option conceptual MCQ on the spot using the local SLM."""
    host = ollama_host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = os.getenv("ARCHIPELAGO_OLLAMA_MODEL", "qwen3.5:0.8b")
    try:
        from archipelago.inference.llm_gateway import gateway_chat
        prompt = (
            f"Generate 1 simple multiple-choice question testing basic conceptual knowledge of '{concept_name}'.\n"
            f"Concept description: {summary}\n\n"
            f"Write a question specifically about {concept_name}.\n"
            "Rules:\n"
            "- Question must be direct, simple, and test conceptual basics (avoid overly academic jargon).\n"
            "- Exactly 4 options with keys: 'A', 'B', 'C', 'D'.\n"
            "- Exactly 1 option must be correct.\n"
            "- 1-sentence explanation of why that answer is correct.\n"
            "Output JSON with this schema:\n"
            "{\n"
            f'  "question": "<question about {concept_name}>",\n'
            '  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},\n'
            '  "correct_option": "A",\n'
            '  "explanation": "..."\n'
            "}"
        )
        msg_content = gateway_chat(
            messages=[{"role": "user", "content": prompt}],
            purpose="synthesis",
            temperature=0.7,
            max_tokens=280,
            timeout=15,
        ) or ""
        if not msg_content:
            return None
        clean_json = re.sub(r"^```(?:json)?\s*", "", msg_content.strip(), flags=re.IGNORECASE)
        clean_json = re.sub(r"\s*```$", "", clean_json.strip())
        # Remove any trailing commas before } or ]
        clean_json = re.sub(r",\s*([\]\}])", r"\1", clean_json)
        data = json.loads(clean_json)

        q_text = str(data.get("question") or "").strip()
        raw_opts = data.get("options") or {}
        raw_corr = data.get("correct_option")
        expl = str(data.get("explanation") or "").strip()

        # Resilient options parser: handle dict or list
        clean_opts: dict[str, str] = {}
        letters = ["A", "B", "C", "D"]
        if isinstance(raw_opts, dict):
            for k in letters:
                clean_opts[k] = str(raw_opts.get(k) or raw_opts.get(k.lower()) or "").strip()
        elif isinstance(raw_opts, list) and len(raw_opts) >= 4:
            for i, opt in enumerate(raw_opts[:4]):
                clean_opts[letters[i]] = str(opt).strip()

        if len(clean_opts) != 4 or not all(clean_opts[k] for k in letters):
            return None

        # Resilient correct_option parser: handle string or int
        corr = "A"
        if isinstance(raw_corr, int):
            if 0 <= raw_corr <= 3:
                corr = letters[raw_corr]
            elif 1 <= raw_corr <= 4:
                corr = letters[raw_corr - 1]
        elif isinstance(raw_corr, str):
            c_str = raw_corr.strip().upper()
            if c_str in letters:
                corr = c_str
            elif c_str.isdigit():
                idx = int(c_str)
                if 0 <= idx <= 3:
                    corr = letters[idx]
                elif 1 <= idx <= 4:
                    corr = letters[idx - 1]

        if not q_text:
            return None

        cit = citation or "Foundational Machine Learning Literature & OKF Knowledge Graph."

        return DiagnosticMCQ(
            id=f"mcq_{concept_id}_{q_index}_{random.randint(100, 999)}",
            concept_id=concept_id,
            concept_name=concept_name,
            question=q_text,
            options=clean_opts,
            correct_option=corr,
            explanation=expl or f"Option {corr} accurately describes the core concept of {concept_name}.",
            citation=cit,
            difficulty=difficulty,
        )
    except Exception as exc:
        logger.debug("SLM MCQ generation skipped (%s); using dynamic fallback.", exc)
        return None

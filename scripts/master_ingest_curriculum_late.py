"""Master ingestion curriculum, batches 11 through 14."""

from __future__ import annotations

from typing import Any

LATE_BATCHES: dict[int, dict[str, Any]] = {
    11: {
        "domain": "Applied Mathematics & Statistics",
        "subject": "Mathematics",
        "sources": [
            {
                "book_title": "Mathematics for Machine Learning",
                "author": "Marc Peter Deisenroth",
                "chapter": "Matrix Decompositions & SVD",
                "page": 95,
                "text": """
                Chapter 4 Matrix Decompositions.
                Singular Value Decomposition (SVD) is a fundamental matrix factorization applicable to any real m x n matrix A:
                A = U * Sigma * V^T,
                where U is an m x m orthogonal matrix of left singular vectors, Sigma is an m x n diagonal matrix containing non-negative singular values sigma_i sorted in descending order, and V is an n x n orthogonal matrix of right singular vectors.
                The singular values represent the scaling factors of linear transformations along orthogonal principal axes.
                The Eckart-Young-Mirsky Theorem establishes that truncating the SVD to the top k singular values yields the optimal rank-k approximation of matrix A under both Frobenius and spectral norms.
                Prerequisites include Matrix Multiplication, Eigenvalues and Eigenvectors, and Orthogonal Basis.
                Unlocks include Principal Component Analysis, Low-Rank Adaptation, and Latent Semantic Analysis.
                """,
            }
        ],
    },
    12: {
        "domain": "Foundational AI Papers: Transformers & LLMs",
        "subject": "Artificial Intelligence Research",
        "sources": [
            {
                "book_title": "Attention Is All You Need",
                "author": "Ashish Vaswani et al. (2017)",
                "chapter": "Scaled Dot-Product Attention & Multi-Head Attention",
                "page": 3,
                "text": """
                Section 3 Model Architecture.
                The Transformer is a sequence-to-sequence model architecture relying entirely on attention mechanisms to draw global dependencies between input and output without recurrence or convolutions.
                Scaled Dot-Product Attention computes attention weights on packed query matrix Q, key matrix K, and value matrix V:
                Attention(Q, K, V) = softmax((Q * K^T) / sqrt(d_k)) * V.
                Scaling by 1 / sqrt(d_k) prevents dot products from growing excessively large for large dimensions, which would push the softmax function into regions with vanishing gradients.
                Multi-Head Attention projects queries, keys, and values h times with learned parameter projections, allowing the model to jointly attend to information from different representation subspaces at different positions.
                Prerequisites include Matrix Multiplication, Softmax Function, and Sequence-to-Sequence Modeling.
                Unlocks include Transformer Encoder, Masked Self-Attention, and Bidirectional Encoder Representations from Transformers.
                """,
            },
            {
                "book_title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "author": "Jacob Devlin et al. (2018)",
                "chapter": "Masked Language Modeling & Next Sentence Prediction",
                "page": 4,
                "text": """
                Section 3 Pre-training BERT.
                Unlike standard autoregressive language models that process text strictly unidirectionally, BERT pre-trains deep bidirectional representations by jointly conditioning on both left and right context across all layers.
                The core pre-training objective is the Masked Language Model (MLM): 15% of the input tokens are selected at random; of these, 80% are replaced with a special [MASK] token, 10% with a random token, and 10% remain unchanged.
                The model is trained to predict the original vocabulary id of masked tokens using cross-entropy loss.
                Additionally, Next Sentence Prediction (NSP) trains the model to understand sentence relationships by classifying whether sentence B follows sentence A.
                Prerequisites include Transformer Encoder, Cross-Entropy Loss, and Word Embeddings.
                Unlocks include Transfer Learning in NLP, Fine-Tuning Transformers, and Dense Passage Retrieval.
                """,
            },
        ],
    },
    13: {
        "domain": "Foundational AI Papers: PEFT & Serving",
        "subject": "Artificial Intelligence Research",
        "sources": [
            {
                "book_title": "LoRA: Low-Rank Adaptation of Large Language Models",
                "author": "Edward J. Hu et al. (2021)",
                "chapter": "Low-Rank Parameter Efficient Fine-Tuning",
                "page": 3,
                "text": """
                Section 4 Method.
                Low-Rank Adaptation (LoRA) freezes pre-trained model weights W_0 in R^{d x k} and injects trainable rank decomposition matrices into each transformer layer.
                The forward pass updates weights via:
                h = W_0 * x + delta W * x = W_0 * x + (B * A) * x * (alpha / r),
                where B in R^{d x r} and A in R^{r x k} with low rank r << min(d, k).
                Matrix A is initialized with Gaussian noise and B is initialized to zero, ensuring delta W = 0 at the start of training.
                Scaling factor alpha / r stabilizes optimization across choices of rank r.
                LoRA reduces the number of trainable parameters by up to 10,000x and eliminates inference latency overhead by merging weights: W = W_0 + (alpha / r) * B * A.
                Prerequisites include Matrix Factorization, Singular Value Decomposition, and Gradient Descent.
                Unlocks include Quantized Low-Rank Adaptation, Parameter-Efficient Fine-Tuning, and Multi-LoRA Serving.
                """,
            },
            {
                "book_title": "vLLM: Efficient Memory Management for Large Language Model Serving with PagedAttention",
                "author": "Woosuk Kwon et al. (2023)",
                "chapter": "PagedAttention & Virtual KV Cache Paging",
                "page": 4,
                "text": """
                Section 3 PagedAttention.
                Serving Large Language Models is constrained by GPU memory consumption of the dynamic Key-Value (KV) cache.
                Existing systems allocate contiguous physical GPU memory for maximum sequence lengths, resulting in 60% to 80% memory fragmentation and waste.
                PagedAttention partitions the KV cache of each sequence into fixed-size physical memory blocks, drawing inspiration from virtual memory paging in operating systems.
                A Block Table maintains the mapping between logical KV blocks and non-contiguous physical GPU memory pages.
                PagedAttention allows keys and values to be stored in non-contiguous physical blocks and fetched dynamically during attention computation without copying.
                This enables near-zero memory waste (<4%) and facilitates memory sharing across parallel sampling requests and prefix caching.
                Prerequisites include Virtual Memory, Paging and Segmentation, and Multi-Head Attention.
                Unlocks include High-Throughput LLM Serving, Prefix Caching, and Continuous Batching.
                """,
            },
        ],
    },
    14: {
        "domain": "Foundational AI Papers: RAG, GNNs & Alignment",
        "subject": "Artificial Intelligence Research",
        "sources": [
            {
                "book_title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
                "author": "Patrick Lewis et al. (2020)",
                "chapter": "Dense Passage Retrieval & RAG-Sequence",
                "page": 3,
                "text": """
                Section 2 Methods.
                Retrieval-Augmented Generation (RAG) combines pre-trained parametric memory (a sequence-to-sequence transformer generator) with non-parametric memory (a dense vector index of Wikipedia passages retrieved using Dense Passage Retrieval).
                The retriever p_eta(z | x) encodes query x and document passages z using dense dual-encoder embeddings, retrieving top-k candidate passages via maximum inner product search.
                In RAG-Sequence, the model uses the same retrieved document to generate the entire target sequence y:
                p(y | x) = sum_{z in top-k} p_eta(z | x) * prod_{i=1}^N p_theta(y_i | x, z, y_{1:i-1}).
                In RAG-Token, the model marginalizes across different retrieved passages at each token generation step.
                RAG grounds generation in authoritative external documents, reducing hallucinations.
                Prerequisites include Dense Passage Retrieval, Sequence-to-Sequence Modeling, and Approximate Nearest Neighbor Search.
                Unlocks include Graph-Augmented Generation, Self-RAG, and Citation Grounding.
                """,
            },
            {
                "book_title": "Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
                "author": "Rafael Rafailov et al. (2023)",
                "chapter": "Direct Preference Optimization & Bradley-Terry Alignment",
                "page": 4,
                "text": """
                Section 4 Direct Preference Optimization.
                Reinforcement Learning from Human Feedback (RLHF) typically fits a reward model r_phi(x, y) to human preference pairs (y_w > y_l) under the Bradley-Terry preference model, then optimizes the policy pi_theta using PPO.
                Direct Preference Optimization (DPO) derives an exact closed-form analytical expression for optimal policy probabilities without explicitly training a separate reward model or sampling during training.
                The DPO loss directly optimizes the language model policy parameters theta using preference pairs:
                L_DPO(pi_theta; pi_ref) = - E_{(x, y_w, y_l)} [ log sigma(beta * log(pi_theta(y_w | x) / pi_ref(y_w | x)) - beta * log(pi_theta(y_l | x) / pi_ref(y_l | x))) ].
                Parameter beta controls the strength of the implicit KL-divergence penalty relative to reference policy pi_ref.
                Prerequisites include Bradley-Terry Preference Model, Cross-Entropy Loss, and Reinforcement Learning from Human Feedback.
                Unlocks include Direct Alignment, Preference Fine-Tuning, and Constitutional AI.
                """,
            },
        ],
    },
}

# Archipelago — Blinded Human Annotation Workbook

## Overview
This workbook contains 24 academic concept pair candidates extracted from verified corpus documents.
Your task as an annotator is to read each passage carefully and evaluate whether a semantic relationship exists between Concept A and Concept B.

### Allowed Relationship Types
- `REQUIRES`: Concept A requires Concept B as a prerequisite, or vice-versa.
- `UNLOCKS`: Concept A enables or unlocks the learning/application of Concept B.
- `PART_OF`: One concept is a structural subcomponent or element of the other.
- `USES`: One concept applies, employs, or utilizes the other as a tool/technique/hardware.
- `CONTRASTS_WITH`: Concepts are comparative alternatives, competing methods, or contrasting ideas.
- `RELATED`: General associative relationship without prerequisite or compositional structure.
- `UNRELATED`: Concepts co-occur in the passage but have no meaningful semantic relationship.
- `AMBIGUOUS`: The passage lacks sufficient clarity to assert a definite relationship.

### Allowed Directions
- `A_TO_B`: The relation holds from Concept A to Concept B (e.g., A requires B, or A uses B).
- `B_TO_A`: The relation holds from Concept B to Concept A (e.g., B requires A, or B uses A).
- `UNDIRECTED`: Symmetric relation (e.g., CONTRASTS_WITH or mutual association).
- `NONE`: No relation holds.

---

### Item `ANN-01`

- **Concept A:** `Operating System`
- **Concept B:** `Address Spaces`
- **Source Reference:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf` (Chunk: `paging_seed_005`, Page: 2)

> **Verbatim Passage:**
> "2 THE ABSTRACTION: ADDRESS SPACES max 64KB 0KB Current Program (code, data, etc.) Operating System (code, data, etc.) Figure 13.1: Operating Systems: The Early Days tive) program-debug cycles."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-02`

- **Concept A:** `Address Spaces`
- **Concept B:** `code`
- **Source Reference:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf` (Chunk: `paging_seed_005`, Page: 2)

> **Verbatim Passage:**
> "2 THE ABSTRACTION: ADDRESS SPACES max 64KB 0KB Current Program (code, data, etc.) Operating System (code, data, etc.) Figure 13.1: Operating Systems: The Early Days tive) program-debug cycles."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-03`

- **Concept A:** `paging`
- **Concept B:** `segmentation`
- **Source Reference:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` (Chunk: `paging_seed_001`, Page: 1)

> **Verbatim Passage:**
> "18 Paging: Introduction It is sometimes said that the operating system takes one of two ap- proaches when solving most any space-management problem. The ﬁrst approach is to chop things up into variable-sized pieces, as we saw with segmentation in virtual memory. Unfortunately, this solution has inher- ent difﬁculties."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-04`

- **Concept A:** `physical memory`
- **Concept B:** `free list`
- **Source Reference:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` (Chunk: `paging_seed_003`, Page: 3)

> **Verbatim Passage:**
> "For example, when the OS wishes to place our tiny 64-byte address space into our eight-page physical memory, it simply ﬁnds four free pages; perhaps the OS keeps a free list of all free pages for this, and just grabs the ﬁrst four free pages off of this list."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-05`

- **Concept A:** `virtual address space`
- **Concept B:** `physical memory`
- **Source Reference:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` (Chunk: `paging_seed_002`, Page: 2)

> **Verbatim Passage:**
> "2 PAGING: INTRODUCTION 64 48 32 16 0 (page 3) (page 2) (page 1) (page 0 of the address space) Figure 18.1: A Simple 64-byte Address Space Physical memory, as shown in Figure 18.2, also consists of a number of ﬁxed-sized slots, in this case eight page frames (making for a 128-byte physical memory, also ridiculously small). As you can see in the diagram, the pages of the virtual address space have been placed at different loca- tions throughout physical memory; the diagram also shows the OS using some of physical memory for itself."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-06`

- **Concept A:** `Transformer`
- **Concept B:** `attention mechanism`
- **Source Reference:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Chunk: `chunk_005`, Page: 2)

> **Verbatim Passage:**
> "In this work we propose the Transformer, a model architecture eschewing recurrence and instead relying entirely on an attention mechanism to draw global dependencies between input and output."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-07`

- **Concept A:** `Transformer`
- **Concept B:** `self-attention`
- **Source Reference:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Chunk: `chunk_007`, Page: 2)

> **Verbatim Passage:**
> "To the best of our knowledge, however, the Transformer is the first transduction model relying entirely on self-attention to compute representations of its input and output without using sequence- aligned RNNs or convolution."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-08`

- **Concept A:** `encoder`
- **Concept B:** `decoder`
- **Source Reference:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Chunk: `chunk_008`, Page: 2)

> **Verbatim Passage:**
> "Most competitive neural sequence transduction models have an encoder-decoder structure [5, 2, 35]. Here, the encoder maps an input sequence of symbol representations (x1, ..., xn) to a sequence of continuous representations z = (z1, ..., zn)."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-09`

- **Concept A:** `multi-head self-attention`
- **Concept B:** `feed-forward network`
- **Source Reference:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Chunk: `chunk_009`, Page: 3)

> **Verbatim Passage:**
> "Each layer has two sub-layers. The first is a multi-head self-attention mechanism, and the second is a simple, position- wise fully connected feed-forward network. We employ a residual connection [11] around each of the two sub-layers, followed by layer normalization [1]."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-10`

- **Concept A:** `Scaled Dot-Product Attention`
- **Concept B:** `Multi-Head Attention`
- **Source Reference:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Chunk: `chunk_010`, Page: 4)

> **Verbatim Passage:**
> "The output is computed as a weighted sum
3
Scaled Dot-Product Attention
Multi-Head Attention
Figure 2: (left) Scaled Dot-Product Attention."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-11`

- **Concept A:** `LoRA`
- **Concept B:** `low-rank matrices`
- **Source Reference:** `papers/Hu2021_LoRA.pdf` (Chunk: `chunk_005`, Page: 2)

> **Verbatim Passage:**
> "• LoRA makes training more efﬁcient and lowers the hardware barrier to entry by up to 3 times when using adaptive optimizers since we do not need to calculate the gradients or maintain the optimizer states for most parameters. Instead, we only optimize the injected, much smaller low-rank matrices.
• Our simple linear design allows us to merge the trainable matrices with the frozen weights when deployed, introducing no inference latency compare"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-12`

- **Concept A:** `pre-trained model`
- **Concept B:** `downstream task`
- **Source Reference:** `papers/Hu2021_LoRA.pdf` (Chunk: `chunk_007`, Page: 3)

> **Verbatim Passage:**
> "One of the main drawbacks for full ﬁne-tuning is that for each downstream task, we learn a different set of parameters ∆Φ whose dimension |∆Φ| equals |Φ0|. Thus, if the pre-trained model is large (such as GPT-3 with |Φ0| ≈175 Billion), storing and deploying many independent instances of ﬁne-tuned models can be challenging, if at all f"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-13`

- **Concept A:** `4-bit NormalFloat`
- **Concept B:** `Double Quantization`
- **Source Reference:** `papers/Dettmers2023_QLoRA.pdf` (Chunk: `chunk_005`, Page: 2)

> **Verbatim Passage:**
> "QLORA introduces multiple innovations designed to reduce memory use without sacrificing per- formance: (1) 4-bit NormalFloat, an information theoretically optimal quantization data type for normally distributed data that yields better empirical results than 4-bit Integers and 4-bit Floats. (2) Double Quantization, a method that quantizes the quantization constants, saving an average of about 0.37 bits per parameter (approximately 3 GB for a 65B model)."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-14`

- **Concept A:** `QLORA`
- **Concept B:** `instruction finetuning`
- **Source Reference:** `papers/Dettmers2023_QLoRA.pdf` (Chunk: `chunk_006`, Page: 2)

> **Verbatim Passage:**
> "QLORA’s efficiency enables us to perform an in-depth study of instruction finetuning and chatbot performance on model scales that would be impossible using regular finetuning due to memory overhead."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-15`

- **Concept A:** `encoder`
- **Concept B:** `sequence of vectors`
- **Source Reference:** `papers/Bahdanau2014_Attention.pdf` (Chunk: `chunk_005`, Page: 2)

> **Verbatim Passage:**
> "The most important distinguishing feature of this approach from the basic encoder–decoder is that it does not attempt to encode a whole input sentence into a single ﬁxed-length vector. Instead, it en- codes the input sentence into a sequence of vectors and chooses a subset of these vectors adaptively while decoding the translation."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-16`

- **Concept A:** `neural machine translation`
- **Concept B:** `LSTM`
- **Source Reference:** `papers/Bahdanau2014_Attention.pdf` (Chunk: `chunk_007`, Page: 2)

> **Verbatim Passage:**
> "Sutskever et al. (2014) reported that the neural machine translation based on RNNs with long short- term memory (LSTM) units achieves close to the state-of-the-art performance of the conventional phrase-based machine translation system on an English-to-French transla"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-17`

- **Concept A:** `anomaly detection`
- **Concept B:** `signature-based systems`
- **Source Reference:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf` (Chunk: `chunk_006`, Page: 2)

> **Verbatim Passage:**
> "achine learning has become a transformative ap- proach for enhancing NIDS capabilities, particularly through anomaly- based detection methods. Unlike signature-based systems, anomaly de- tection models are designed to identify deviations from normal behav- ior, making them more ﬂexible in detecting previously unseen attacks [5]. Among these, zero-shot learning has emerged as a powerful tech- nique for unsupervised anomaly detection [6]. Zero-shot learning allows a model to generalize beyond known attacks, enabling it to identify new types of attacks without requiring labeled exa"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-18`

- **Concept A:** `Graph Neural Networks`
- **Concept B:** `D-MAGIC`
- **Source Reference:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf` (Chunk: `chunk_008`, Page: 2)

> **Verbatim Passage:**
> "Our proposed D-MAGIC (Dynamic Model for cybersecurity At- tack detection using GNNs Into Clustering) and SAGA (Sophisticated Anomaly detection with GNN into ANN) models enhance detection ca- pabilities by incorporating graph-based learning. Both models leverage Graph Neural Networks (GNNs) to generate node embeddings, captur- ing complex relationships between network entities, which traditional vector-based approaches often overl"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-19`

- **Concept A:** `real-time NIDS`
- **Concept B:** `latency`
- **Source Reference:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf` (Chunk: `chunk_005`, Page: 1)

> **Verbatim Passage:**
> "However, implementing real-time NIDS poses unique challenges. Traditional intrusion detection systems often rely on processing of the whole network data, which introduces latency in detecting attacks. These systems typically analyze large volumes of traﬃc at predeﬁned intervals, which can be too slow for modern threats that ca"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-20`

- **Concept A:** `Physical Layer`
- **Concept B:** `Data Link Layer`
- **Source Reference:** `doc_computer_networks_6_e` (Chunk: `doc_computer_networks_6_e_p42_1`, Page: 42)

> **Verbatim Passage:**
> "The OSI Reference Model defines a 7-layer architecture for computer communications:
                1. Physical Layer: Transmission of raw bits over a physical communications channel.
                2. Data Link Layer: Transforms a raw transmission facility in"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-21`

- **Concept A:** `multinomial sampling`
- **Concept B:** `EOS token`
- **Source Reference:** `papers/Willard2023_Outlines.pdf` (Chunk: `chunk_006`, Page: 4)

> **Verbatim Passage:**
> "Often called multinomial sampling, the procedure recursively generates new tokens by sampling from the categorical distribution defined above until the EOS token is found.
3
2.2 Guiding generation
We can derive other random variables from the next-token distribution by manipulating the output logits α."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-22`

- **Concept A:** `vocabulary`
- **Concept B:** `categorical distribution`
- **Source Reference:** `papers/Willard2023_Outlines.pdf` (Chunk: `chunk_005`, Page: 3)

> **Verbatim Passage:**
> ". . st) represent a sequence of t tokens with st ∈V, V a vocab- ulary, and |V| = N. The vocabularies, V, are composed of strings from a fixed alphabet [Sennrich et al., 2015] and N is often on the order of 104 or larger.
We define the next token st+1 as the following random variable:
α = LLM(St, θ)
st+1 ∼Categorical(α)
2
where θ is the set of trained parameters and α ∈RN."

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-23`

- **Concept A:** `Relational Algebra`
- **Concept B:** `query language`
- **Source Reference:** `doc_fundamentals_of_database_system_7e` (Chunk: `doc_fundamentals_of_database_system_7e_p145_1`, Page: 145)

> **Verbatim Passage:**
> "he Relational Model represents a database as a collection of relations (tables) consisting of tuples (rows) and attributes (columns).
                Relational Algebra is a formal procedural query language consisting of fundamental algebraic"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---

### Item `ANN-24`

- **Concept A:** `parser`
- **Concept B:** `context-free grammar`
- **Source Reference:** `doc_compilers_principles_techniques_and_tools` (Chunk: `doc_compilers_principles_techniques_and_tools_p192_1`, Page: 192)

> **Verbatim Passage:**
> "The parser obtains a string of tokens from the lexical analyzer and verifies that the string can be generated by the context-free grammar for the source language.
                For every context-free grammar G = (V, Sigma, R, S), the parser constructs a parse tree or Abstract Syntax T"

| Field | Your Judgment |
|---|---|
| **Relation Type** | `[ REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED / AMBIGUOUS ]` |
| **Direction** | `[ A_TO_B / B_TO_A / UNDIRECTED / NONE ]` |
| **Confidence** | `[ HIGH / MEDIUM / LOW ]` |
| **Annotator Notes** | *Optional notes or justification* |

---


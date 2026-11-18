# Archipelago — CIKM 2027 Multi-Hop Retrieval Annotation Protocol

**Document Version:** 1.0.0 (S5-A Frozen)  
**Date:** November 18, 2026  
**Audience:** Independent Academic Human Annotators & Adjudicators  

---

## 1. Research Objective & Annotation Purpose

The central research hypothesis of Archipelago is:
> **Does provenance-aware graph retrieval improve multi-hop academic retrieval and evidence quality against BM25, dense, and hybrid retrieval baselines?**

To evaluate this question fairly, retrieval systems cannot be evaluated against synthetic AI answers or proxy metrics. This protocol defines the formal guidelines for independent human relevance grading of passages retrieved for complex academic computer science questions across **Operating Systems**, **AI & Machine Learning**, **Computer Networks**, and **Database Management Systems**.

---

## 2. Graded Relevance Scale (TREC / CIKM Standard)

Annotators assign a discrete integer grade $g \in \{0, 1, 2\}$ to each query-passage pair:

| Grade | Label | Operational Definition |
| :---: | :--- | :--- |
| **0** | **Irrelevant / Distractor** | The passage does not contribute any useful factual or conceptual information toward answering the query. Even if it shares superficial terminology or keywords (e.g., mentioning "network" or "attention"), it does not address the substantive query topic. |
| **1** | **Partially Relevant / Background** | The passage provides useful topical context, background definitions, or related framework details, but **does not by itself furnish a necessary logical step or direct evidence** to resolve the question. |
| **2** | **Highly Relevant / Key Premise** | The passage contains direct, necessary factual or mathematical evidence. For multi-hop questions, it constitutes one of the essential premise hops required to construct a complete, correct answer. |

---

## 3. Question Categories & Multi-Hop Grading Rules

Annotators will evaluate queries belonging to four distinct categories:

### 3.1 Single-Hop Controls (`SINGLE_HOP_CONTROL`)
- **Nature:** Direct questions where a single authoritative passage in the corpus contains the complete answer.
- **Grading Rule:** Exactly one primary passage should be graded **2**; contextual mentions in related chapters may receive **1**; non-answering mentions must receive **0**.

### 3.2 Two-Hop Questions (`TWO_HOP`)
- **Nature:** Questions that require combining two distinct conceptual assertions (e.g., Premise A $\rightarrow$ Premise B).
- **Grading Rule:** Any passage containing one of the required premise hops should be graded **2**. Both premises are equally necessary to synthesize the final answer.

### 3.3 Cross-Document Questions (`CROSS_DOCUMENT`)
- **Nature:** Questions that require synthesizing concepts originating in two separate research papers or distinct textbooks (e.g., Vaswani 2017 Transformer projections combined with Hu 2021 LoRA adapter math).
- **Grading Rule:** Both the foundational paper passage and the derivative/applied paper passage should receive grade **2**.

### 3.4 Unanswerable Questions (`UNANSWERABLE`)
- **Nature:** Legitimate, technically sophisticated academic questions whose answers are intentionally absent from the indexed corpus (e.g., private proprietary benchmarks, unpublished electric utility costs, future hardware revisions).
- **Grading Rule:** **No passage in the corpus should receive grade 2.** If a passage discusses related concepts generally (e.g., general compute costs or general page table lookups), it may receive grade **1** as background context, or grade **0** if unrelated.

---

## 4. Hard Negative & Distractor Passages

To prevent annotators and retrieval models from exploiting surface keyword matching, candidate pools include **hard negative passages**.
- Hard negatives contain identical technical keywords (e.g., "Scaled Dot-Product Attention", "MMU", "Sliding Window") but describe unrelated mechanisms, different architectures, or alternative formulas.
- Annotators must read passages carefully to confirm whether the text actually answers the prompt or merely uses similar jargon. If it does not provide evidence, grade it **0**.

---

## 5. Reviewer Workflow & Double-Blinded Protocol

1. **Blinding:** Annotators are presented only with the Query ID, Domain, Query Text, and Quoted Passage Text.
2. **Hidden System Identity:** Annotators do NOT see which retrieval system returned which passage (BM25, Dense, Hybrid RRF, or Graph Retriever).
3. **Double Annotation:** Each query-passage pair is independently graded by two qualified reviewers ($R_1$ and $R_2$).
4. **Inter-Annotator Agreement:**
   - Inter-annotator agreement is quantified using Cohen's Weighted Kappa ($\kappa_w$) with quadratic weights, and Krippendorff's Alpha ($\alpha$).
   - Target consensus threshold: $\kappa_w \ge 0.70$.
5. **Adjudication Procedure:**
   - Where $|g_{R1} - g_{R2}| = 1$, the pair is reviewed in a joint consensus meeting.
   - Where $|g_{R1} - g_{R2}| \ge 2$, a senior academic domain expert conducts independent adjudication and records the final gold grade with written justification.

---

## 6. Scientific Integrity Directives

- **Zero AI Gold Labels:** Under no circumstances may LLM predictions or automated heuristic scores be used as substitute ground-truth labels.
- **Empty Judgment Fields:** All distributed reviewer templates and candidate CSV files must have completely blank judgment columns (`human_relevance_grade`, `human_evidence_quote`, `human_confidence`, `human_notes`).
- **No Evaluation Before Adjudication:** Retrieval effectiveness metrics (Recall@k, MRR, nDCG@k) shall not be reported until human annotation and adjudication are fully completed and frozen.

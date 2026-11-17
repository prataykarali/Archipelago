# Archipelago — 24-Item Human Evidence Audit

**Purpose:** A small human quality-control exercise for AI-generated passage relevance annotations, **not** independent double-human gold data or proof that all 113 labels are correct.

**Instructions:** Read each question and the four passages shown. Without consulting either AI reviewer’s scores, assign your own relevance score to each passage. You do **not** need to retype the passage. Give one short reason for the choice, using the passage’s actual content. If you are uncertain, still record a provisional score and mark `Uncertain: yes`. Do not ask AI to fill judgments.

**Rubric:** `0` = unrelated/does not meaningfully help answer; `1` = useful context or partial evidence; `2` = directly answers or supplies core evidence necessary to answer.

**Scope:** Judge only the supplied passages. Do not claim a question is absent from the entire corpus on the basis of these four examples. The original AI scores are intentionally not displayed.

**Sampling:** Exactly four candidates per query, chosen reproducibly from the earlier 113-item candidate pool. Selection intentionally includes different preliminary AI score bands where available; it is a **challenging, stratified validation sample**, not a random prevalence estimate. The older worksheets were AI-generated, and this human review is not fully independent of previous exposure.

**Reviewer:** Pratay Karali   **Date:** 17.11.2026

---

## Question 1 — CIKM-PILOT-001

**Question:** What foundational sequence-modeling limitations motivated replacing recurrence with self-attention in the Transformer?

### Passage 1 · CAND-16 (page label 5)
**Section:** 3.2.3 Applications of Attention in our Model

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_013` (Page 5). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):** 0

**Reason (one sentence): Explains how multi-head attention and decoder masking work inside the Transformer, not what sequence-modeling flaws motivated replacing recurrence

**Uncertain? (yes / no):** no

### Passage 2 · CAND-03 (page label 10)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_031` (Page 10). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):** 1

**Reason (one sentence): Mentions in the conclusion that the Transformer trains faster than recurrent models and notes a future goal of making generation less sequential, giving only indirect context on recurrence's limits

**Uncertain? (yes / no):** yes

### Passage 3 · CAND-01 (page label 3)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/wei2022_chainofthought.pdf::chunk_010` (Page 3). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Discusses chain-of-thought prompting for multi-step math word problems in language models and has nothing to do with Transformers or recurrence.

**Uncertain? (yes / no):** no

### Passage 4 · CAND-17 (page label 1)
**Section:** Abstract

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_002` (Page 1). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Notes in the abstract that dropping recurrence and convolutions makes the Transformer more parallelizable and faster to train, offering partial evidence without explaining the underlying sequence-modeling bottlenecks.

**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? No
---

## Question 2 — CIKM-PILOT-005

**Question:** What mathematical assumption about weight updates during fine-tuning justifies LoRA's low-rank matrix decomposition?

### Passage 1 · CAND-10 (page label 3)
**Section:** 3.1 Encoder and Decoder Stacks

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_009` (Page 3). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes the standard Transformer encoder and decoder layer architecture without mentioning LoRA or fine-tuning weight updates.

**Uncertain? (yes / no):no

### Passage 2 · CAND-06 (page label 7)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/hu2021_lora.pdf::chunk_019` (Page 7). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Covers where LoRA inserts rank decomposition matrices, how trainable parameters are counted, and GPT-2 benchmark results rather than the mathematical assumption behind the method.

**Uncertain? (yes / no):no

### Passage 3 · CAND-03 (page label 4)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/hu2021_lora.pdf::chunk_012` (Page 4). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): States that LoRA does not require accumulated gradient updates to weight matrices to have full rank during adaptation, providing partial evidence without explicitly framing the intrinsic-rank hypothesis.

**Uncertain? (yes / no):yes

### Passage 4 · CAND-11 (page label 10)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/hu2021_lora.pdf::chunk_030` (Page 10). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly states that the weight update matrix $\Delta W$ may have a very small "intrinsic rank" and backs this up by measuring singular-vector subspace overlap across ranks


**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? Yes

---

## Question 3 — CIKM-PILOT-013

**Question:** How does PagedAttention apply virtual memory paging concepts to eliminate KV-cache fragmentation in LLM serving?

### Passage 1 · CAND-12 (page label 5)
**Section:** vllm

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/kwon2023_vllm.pdf::vllm_seed_004` (Page 5). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Explains why memory compaction is impractical for massive KV caches and introduces vLLM's block allocators and block tables, giving useful context before detailing the paging mechanism

**Uncertain? (yes / no):no

### Passage 2 · CAND-10 (page label 8)
**Section:** 5.1 Effect of Pre-training Tasks

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/devlin2018_bert.pdf::chunk_030` (Page 8). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Discusses BERT bidirectional pre-training ablations on GLUE and has no connection to PagedAttention or KV-cache fragmentation.

**Uncertain? (yes / no):no

### Passage 3 · CAND-09 (page label 6)
**Section:** 3 KV cache states for request B’s prompt

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/kwon2023_vllm.pdf::chunk_024` (Page 6). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly explains how vLLM dynamically maps logical blocks to non-contiguous physical GPU blocks on demand and keeps internal memory waste within a single block per request.

**Uncertain? (yes / no):no

### Passage 4 · CAND-07 (page label 5)
**Section:** 3 KV cache states for request B’s prompt

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/kwon2023_vllm.pdf::chunk_020` (Page 5). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly answers the question by showing how PagedAttention fetches non-contiguous KV blocks and adapts OS virtual memory pagingfixed-size logical-to-physical block mapping and dynamic allocationto the KV cache.

**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? Yes
---

## Question 4 — CIKM-PILOT-002

**Question:** Why does scaled dot-product attention divide by the square root of the key dimension before applying softmax?

### Passage 1 · CAND-04 (page label 5)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_012` (Page 5). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Focuses on multi-head projections but includes a footnote proving that dot products of unit-variance vectors have variance $d_k$, which supplies partial mathematical evidence without mentioning softmax gradients. 


**Uncertain? (yes / no):no	

### Passage 2 · CAND-13 (page label 4)
**Section:** 3.2.1 Scaled Dot-Product Attention

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_011` (Page 4). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly states that large $d_k$ makes dot products grow large and push softmax into regions with tiny gradients, which dividing by $\sqrt{d_k}$ counteracts. 


**Uncertain? (yes / no):no

### Passage 3 · CAND-09 (page label 3)
**Section:** 3. FlashAttention Algorithm with Tiling and Incremental Softmax

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `upload_17869808::upload_17869808_p3_3` (Page 3). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes FlashAttention's SRAM tiling and online softmax rescaling rather than why scaled dot-product attention divides by $\sqrt{d_k}$. 


**Uncertain? (yes / no):no

### Passage 4 · CAND-08 (page label 4)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010` (Page 4). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Gives only the general definition of attention as a weighted sum of values and does not discuss scaling by $\sqrt{d_k}$ or softmax behavior. 


**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? Yes 
---

## Question 5 — CIKM-PILOT-004

**Question:** How does multi-head self-attention in Vaswani et al. (2017) differ from additive encoder-decoder alignment in Bahdanau et al. (2014)?

### Passage 1 · CAND-17 (page label 5)
**Section:** 3.3 Position-wise Feed-Forward Networks

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_014` (Page 5). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes the Transformer's position-wise feed-forward sub-layer and says nothing about self-attention or Bahdanau alignment.

**Uncertain? (yes / no):no

### Passage 2 · CAND-08 (page label 12)
**Section:** IEEE Transactions on, 45(11), 2673–2681.

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/bahdanau2014_attention.pdf::chunk_031` (Page 12). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Provides half of the comparison by detailing Bahdanau et al.'s single-layer MLP additive alignment formula between decoder and encoder states, without mentioning Vaswani et al.'s multi-head self-attention.

**Uncertain? (yes / no):no

### Passage 3 · CAND-07 (page label 10)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_031` (Page 10). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Gives high-level context that the Transformer replaces recurrent encoder-decoder layers with multi-headed self-attention, but lacks the structural details needed to contrast it with additive alignment.

**Uncertain? (yes / no):yes

### Passage 4 · CAND-16 (page label 5)
**Section:** 3.2.3 Applications of Attention in our Model

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_013` (Page 5). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Contrasts Transformer encoder and decoder self-attention with encoder-decoder cross-attention (citing Bahdanau et al. as [2]), offering partial comparative evidence while omitting multi-head projection and dot-product versus additive scoring differences.

**Uncertain? (yes / no):yes

**Does at least one of these four passages provide a direct answer? No

---

## Question 6 — CIKM-PILOT-023

**Question:** What exact hyperparameters does DeepSeek-R1 use for GRPO reinforcement learning on math benchmarks?

### Passage 1 · CAND-15 (page label 10)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/brown2020_gpt3.pdf::chunk_027` (Page 10). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes few-shot evaluation and beam search parameters from the GPT-3 paper rather than DeepSeek-R1 or GRPO.

**Uncertain? (yes / no):yes

### Passage 2 · CAND-18 (page label 2)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/dettmers2023_qlora.pdf::chunk_004` (Page 2). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Reports Vicuna Elo ratings and GPU memory savings for QLoRA and Guanaco models, which is unrelated to DeepSeek-R1 or GRPO.

**Uncertain? (yes / no):no

### Passage 3 · CAND-13 (page label 9)
**Section:** N/A

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/ouyang2022_instructgpt.pdf::chunk_029` (Page 9). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Covers PPO-ptx KL and pretraining loss coefficients from the InstructGPT paper rather than DeepSeek-R1's GRPO hyperparameters.

**Uncertain? (yes / no):no

### Passage 4 · CAND-03 (page label 1)
**Section:** Abstract

> [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/ouyang2022_instructgpt.pdf::chunk_002` (Page 1). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Summarizes the InstructGPT abstract on fine-tuning GPT-3 with human feedback and contains nothing about DeepSeek-R1 or GRPO.

**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? NO

---

## Submission checklist

- [ ] I personally read all 24 passages and provided 24 original scores.
- [ ] Each score has a brief reason; uncertain judgments are flagged.
- [ ] I did not copy or ask an AI to supply the judgments.
- [ ] I understand this is human validation of an AI-prepared pool, not independent double-human annotation.

**After completion:** Share this filled Markdown file in ChatGPT. We can check completeness first, then compare your locked judgments with AI preannotations and document disagreements without rewriting either set.

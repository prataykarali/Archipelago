# Issue #11 — Evidence and Citation Integrity: Before/After Report

**Branch:** `sigir/swarm-a-citations`  
**Baseline Commit:** `00f38b81351ebaeb5aff2fd36c5e64ea37319524`  
**Scope:** Deterministic citation selection, canonical `chunk_id` provenance verification, withdrawal/metadata-only safety, and provenance-vs-claim-support labeling in `host_inference/engine/`.

> [!IMPORTANT]
> **Provenance Verification != Semantic Claim Support.** Every citation emitted by the deterministic engine now explicitly sets `claim_support_status = "not_assessed"`. No human claim-support grades were generated, prefilled, or fabricated in this report. Independent human claim-support annotation is tracked separately (see **Empirical Annotation Task Pointer** below).

## 1. Summary Delta (D5 Audit Demo + Dev Queries)

| Query ID | Query | Before Cites | After Cites | Before Badge | After Badge | Provenance Status |
|---|---|---:|---:|---|---|---|
| `Q01` | What is Transformer? | 10 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `Q08` | Explain FlashAttention | 6 | 1 | `Passage located · Grounded` | `Passage located (canonical chunk unmatched) · Claim support unassessed` | `chunk_unmatched` |
| `Q21` | How does self-attention relate to the Transformer? | 2 | 2 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `Q23` | How does DPR compare to BM25 in open-domain QA? | 6 | 1 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `Q39` | Explain Spanner TrueTime and its prerequisites. | 0 | 0 | `No Verified Graph Match` | `No Verified Graph Match · Clean abstention` | `none` |
| `DEMO_DEADLOCK` | What is deadlock? | 2 | 1 | `Source linked — not independently audited` | `Metadata only · Provenance and claim support unassessed` | `metadata_only` |
| `DEMO_DPR_RAG` | How does DPR relate to RAG? | 1 | 1 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV01` | What is Multi-Head Attention? | 10 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV02` | Explain Gradient Descent | 10 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV03` | What is LoRA rank r? | 10 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV04` | Explain Vector Similarity Search | 10 | 1 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV05` | What is FAISS index? | 0 | 0 | `No Verified Graph Match` | `No Verified Graph Match · Clean abstention` | `none` |
| `DEV06` | Explain BERT bidirectional attention | 10 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV07` | What is BART seq2seq model in RAG? | 10 | 2 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV08` | Explain KV cache memory overhead in LLMs | 10 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV09` | What is NormalFloat4 quantization in QLoRA? | 6 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV10` | Explain Leiden community detection in GraphRAG | 6 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV11` | What is TF-IDF formula in information retrieval? | 10 | 2 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV12` | Explain approximate nearest neighbors | 7 | 3 | `Passage located · Grounded` | `Provenance verified · Claim support unassessed` | `provenance_verified` |
| `DEV13` | What is MapReduce distributed sorting? | 0 | 0 | `No Verified Graph Match` | `No Verified Graph Match · Clean abstention` | `none` |
| `DEV14` | Explain photosystem II light absorption in plants. | 0 | 0 | `No Verified Graph Match` | `No Verified Graph Match · Clean abstention` | `none` |
| `DEV15` | What is Black-Scholes option pricing model? | 0 | 0 | `No Verified Graph Match` | `No Verified Graph Match · Clean abstention` | `none` |

- **D5 5-query audit slice (`Q01, Q08, Q21, Q23, Q39`) total citations:** 24 -> **7** (eliminated arbitrary padding to 10 and neighborhood dilution from AlexNet, DDPM, ReAct, Bahdanau, GPT-3, Outlines, Constitutional AI, and Vaswani appendix p.13).
- **All 22 dev/demo queries total citations:** 126 -> **38**.
- **Q39 clean abstention:** preserved (`0` citations, `anchor=None`, `render_graph=False`, `provenance_status=none`).
- **Q21 primary Vaswani references:** preserved (`2` citations: `chunk_013` p.5 and `chunk_031` p.10, both `provenance_verified`).

## 2. Detailed Per-Query Evidence (D5 Audit & Key Demo Cases)

### Q01: What is Transformer?
- **Route / Anchor:** `GRAPH_SYNTHESIS` / `transformer`
- **Answer Claim Preview:** **Transformer.** The foundational sequence-to-sequence neural architecture introduced by Vaswani et al. (2017) relying entirely on stacked self-attention and encoder-decoder cross-attention mechanisms, dispensing with re
- **Before (10 citations, badge `Passage located · Grounded`):**
  - `[1]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_008`, p.2, concept=`transformer`): "Most competitive neural sequence transduction models have an encoder-decoder structure [5, 2, 35]. Here, the encoder maps an input sequence of symbol representa"
  - `[2]` `papers/Dao2022_FlashAttention.pdf` (`chunk_id=upload_cb7badb2_p4_4`, p.4, concept=`matrix_multiplication`): "Standard attention requires O(N^2) HBM accesses because it reads and writes intermediate matrices S and P of size N x N. FlashAttention requires only O(N^2 d^2"
  - `[3]` `papers/Bahdanau2014_Attention.pdf` (`chunk_id=chunk_013`, p.5, concept=`recurrent_neural_network`): "2012 and news-test-2013 to make a development (validation) set, and evaluate the models on the test set (news-test-2014) from WMT ’14, which consists of 3003 se"
  - `[4]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_037`, p.13, concept=`attention_mechanism`): "It is in this spirit that a majority of American governments have passed new laws since 2009 making the registration or voting process more difficult . <EOS> <p"
  - `[5]` `papers/Ho2020_DDPM.pdf` (`chunk_id=chunk_017`, p.5, concept=`neural_network`): "We set T = 1000 for all experiments so that the number of neural network evaluations needed during sampling matches previous work [53, 55]. We set the forward p"
  - `[6]` `papers/Krizhevsky2012_AlexNet.pdf` (`chunk_id=chunk_023`, p.7, concept=`fisher_vector`): "Our results on ILSVRC-2010 are summarized in Table 1. Our network achieves top-1 and top-5 test set error rates of 37.5% and 17.0%5. The best performance achiev"
  - `[7]` `papers/Yao2022_ReAct.pdf` (`chunk_id=chunk_004`, p.1, concept=`autonomous_system`): "A unique feature of human intelligence is the ability to seamlessly combine task-oriented actions with verbal reasoning (or inner speech, Alderson-Day & Fernyho"
  - `[8]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_031`, p.10, concept=`ensemble_learning`): "In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used"
  - `[9]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_029`, p.9, concept=`english_constituency_parsing`): "To evaluate if the Transformer can generalize to other tasks we performed experiments on English constituency parsing. This task presents specific challenges: t"
  - `[10]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_026`, p.8, concept=`translation_quality`): "Table 2 summarizes our results and compares our translation quality and training costs to other model architectures from the literature. We estimate the number"
- **After (3 citations, badge `Provenance verified · Claim support unassessed`, `claim_support_status=not_assessed`):**
  - `[S1]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_007`, `canonical_passage_id=papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_007`, p.2, `provenance=provenance_verified/exact_unique_canonical_chunk`, origin=`/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=2`): "To the best of our knowledge, however, the Transformer is the first transduction model relying entirely on self-attention to compute representations of its input and output without"
  - `[S2]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_008`, `canonical_passage_id=papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_008`, p.2, `provenance=provenance_verified/exact_unique_canonical_chunk`, origin=`/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=2`): "Most competitive neural sequence transduction models have an encoder-decoder structure [5, 2, 35]. Here, the encoder maps an input sequence of symbol representations (x1, ..., xn)"
  - `[S3]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_025`, `canonical_passage_id=papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_025`, p.8, `provenance=provenance_verified/exact_unique_canonical_chunk`, origin=`/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=8`): "On the WMT 2014 English-to-German translation task, the big transformer model (Transformer (big) in Table 2) outperforms the best previously reported models (including ensembles) b"

### Q08: Explain FlashAttention
- **Route / Anchor:** `GRAPH_SYNTHESIS` / `flashattention`
- **Answer Claim Preview:** **FlashAttention.** Optimizes memory bandwidth for high-Bandwidth Memory access, reducing read/write latency. [S1: FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness, PDF p.2](/read?doc=papers%2F
- **Before (6 citations, badge `Passage located · Grounded`):**
  - `[1]` `papers/Dao2022_FlashAttention.pdf` (`chunk_id=upload_cb7badb2_p2_2`, p.2, concept=`flashattention`): "Modern GPUs feature a hierarchical memory system comprising fast, small On-Chip SRAM (around 192 KB per Streaming Multiprocessor) and large, slower High-Bandwid"
  - `[2]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_018`, p.7, concept=`self_attention`): "length n is smaller than the representation dimensionality d, which is most often the case with sentence representations used by state-of-the-art models in mach"
  - `[3]` `papers/Brown2020_GPT3.pdf` (`chunk_id=chunk_021`, p.8, concept=`attention_head`): "Table 2.1 shows the sizes and architectures of our 8 models. Here nparams is the total number of trainable parameters, nlayers is the total number of layers, dm"
  - `[4]` `papers/Dao2022_FlashAttention.pdf` (`chunk_id=upload_cb7badb2_p5_5`, p.5, concept=`long_context_transformer`): "Empirical results demonstrate that FlashAttention trains GPT-2 up to 3x faster than standard PyTorch implementations and scales sequence lengths to 64k tokens w"
  - `[5]` `papers/Kwon2023_vLLM.pdf` (`chunk_id=paged_attention_seed_001`, p.1, concept=`paged_attention`): "Efficient Memory Management for Large Language Model Serving with PagedAttention Woosuk Kwon1,∗Zhuohan Li1,∗Siyuan Zhuang1 Ying Sheng1,2 Lianmin Zheng1 Cody Hao"
  - `[6]` `upload_17869808` (`chunk_id=upload_17869808_p1_0`, p.1, concept=`memory_efficient`): "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Re (Stanford Universit"
- **After (1 citations, badge `Passage located (canonical chunk unmatched) · Claim support unassessed`, `claim_support_status=not_assessed`):**
  - `[S1]` `papers/Dao2022_FlashAttention.pdf` (`chunk_id=upload_cb7badb2_p2_2`, `canonical_passage_id=None`, p.2, `provenance=chunk_unmatched/upload_chunk_unmatched`, origin=`/read?doc=papers%2FDao2022_FlashAttention.pdf&page=2`): "Modern GPUs feature a hierarchical memory system comprising fast, small On-Chip SRAM (around 192 KB per Streaming Multiprocessor) and large, slower High-Bandwidth Memory (HBM, 40 t"

### Q21: How does self-attention relate to the Transformer?
- **Route / Anchor:** `MULTI_CONCEPT` / `self_attention`
- **Answer Claim Preview:** Here is what the available evidence shows about **Self-Attention** and **Transformer**. • **Self-Attention**: Self-Attention is a core component of Transformer decoder architecture that allows the model to attend to all
- **Before (2 citations, badge `Passage located · Grounded`):**
  - `[1]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_013`, p.5, concept=`self_attention`): "The Transformer uses multi-head attention in three different ways: • In "encoder-decoder attention" layers, the queries come from the previous decoder layer, an"
  - `[2]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_031`, p.10, concept=`transformer`): "In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used"
- **After (2 citations, badge `Provenance verified · Claim support unassessed`, `claim_support_status=not_assessed`):**
  - `[S1]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_013`, `canonical_passage_id=papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_013`, p.5, `provenance=provenance_verified/exact_unique_canonical_chunk`, origin=`/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=5`): "The Transformer uses multi-head attention in three different ways: • In "encoder-decoder attention" layers, the queries come from the previous decoder layer, and the memory keys an"
  - `[S2]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_031`, `canonical_passage_id=papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_031`, p.10, `provenance=provenance_verified/exact_unique_canonical_chunk`, origin=`/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=10`): "In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used in encoder-decoder"

### Q23: How does DPR compare to BM25 in open-domain QA?
- **Route / Anchor:** `GRAPH_SYNTHESIS` / `bm25`
- **Answer Claim Preview:** **BM25.** A bidirectional search engine that evaluates text passages using masked language modeling on the BM25 corpus. [S1: papers/Karpukhin2020_DPR.pdf, PDF p.2](/read?doc=papers%2FKarpukhin2020_DPR.pdf&page=2)  [Karpu
- **Before (6 citations, badge `Passage located · Grounded`):**
  - `[1]` `papers/Karpukhin2020_DPR.pdf` (`chunk_id=chunk_007`, p.2, concept=`bm25`): "Our contributions are twofold. First, we demon- strate that with the proper training setup, sim- ply ﬁne-tuning the question and passage encoders on existing qu"
  - `[2]` `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (`chunk_id=chunk_021`, p.7, concept=`big_model`): "We trained our models on one machine with 8 NVIDIA P100 GPUs. For our base models using the hyperparameters described throughout the paper, each training step t"
  - `[3]` `papers/Lewis2020_RAG.pdf` (`chunk_id=chunk_009`, p.3, concept=`retrieval`): "The retrieval component pη(z\|x) is based on DPR [26]. DPR follows a bi-encoder architecture: pη(z\|x) ∝exp   d(z)⊤q(x)  d(z) = BERTd(z), q(x) = BERTq(x) where d"
  - `[4]` `papers/Willard2023_Outlines.pdf` (`chunk_id=chunk_016`, p.14, concept=`partial_match`): "According to case 1. above, parsing can be continued–for the NAME symbol–after previously ending in states 1 or 2. According to case 2., the next string could a"
  - `[5]` `papers/Bai2022_ConstitutionalAI.pdf` (`chunk_id=chunk_031`, p.10, concept=`preference_models`): "We continue to utilize human feedback labels for helpfulness as in prior work, but replace human feedback labels with model feedback labels for harmlessness. Th"
  - `[6]` `papers/Brown2020_GPT3.pdf` (`chunk_id=chunk_028`, p.10, concept=`triviaqa`): "Final results are reported on the test set when publicly available, for each model size and learning setting (zero-, one-, and few-shot). When the test set is p"
- **After (1 citations, badge `Provenance verified · Claim support unassessed`, `claim_support_status=not_assessed`):**
  - `[S1]` `papers/Karpukhin2020_DPR.pdf` (`chunk_id=chunk_007`, `canonical_passage_id=papers/Karpukhin2020_DPR.pdf::chunk_007`, p.2, `provenance=provenance_verified/exact_unique_canonical_chunk`, origin=`/read?doc=papers%2FKarpukhin2020_DPR.pdf&page=2`): "Our contributions are twofold. First, we demon- strate that with the proper training setup, sim- ply ﬁne-tuning the question and passage encoders on existing question-passage pairs"

### Q39: Explain Spanner TrueTime and its prerequisites.
- **Route / Anchor:** `MULTI_CONCEPT` / `None`
- **Answer Claim Preview:** Here is what the available evidence shows about **Spanner TrueTime** and **its prerequisites**.  **Coverage Limitations:** • **Spanner TrueTime** is not indexed in the current catalog. No bridge or relationship has been
- **Before (0 citations, badge `No Verified Graph Match`):**
  - *(0 citations — clean abstention)*
- **After (0 citations, badge `No Verified Graph Match · Clean abstention`, `claim_support_status=not_assessed`):**
  - *(0 citations — clean abstention)*

### DEMO_DEADLOCK: What is deadlock?
- **Route / Anchor:** `GRAPH_SYNTHESIS` / `deadlock`
- **Answer Claim Preview:** **Deadlock.** A concurrent execution state where two or more processes are permanently blocked because each holds a resource and waits for another resource held by another process, satisfying Coffman's four conditions (m
- **Before (2 citations, badge `Source linked — not independently audited`):**
  - `[1]` `textbooks/operating_system_concepts_silberschatz.pdf` (`chunk_id=None`, p.None, concept=`deadlock`): "A concurrent execution state where two or more processes are permanently blocked because each holds a resource and waits for another resource held by another pr"
  - `[2]` `textbooks/ostep_three_easy_pieces.pdf` (`chunk_id=None`, p.None, concept=`mutex_lock`): "A binary mutual exclusion lock providing cooperative synchronization where only the thread that acquired the lock can release it, ensuring that at most one thre"
- **After (1 citations, badge `Metadata only · Provenance and claim support unassessed`, `claim_support_status=not_assessed`):**
  - `[S1]` `textbooks/operating_system_concepts_silberschatz.pdf` (`chunk_id=None`, `canonical_passage_id=None`, p.None, `provenance=metadata_only/unmatched_metadata_only`, origin=`metadata_only`): "A concurrent execution state where two or more processes are permanently blocked because each holds a resource and waits for another resource held by another process, satisfying Co"

### DEMO_DPR_RAG: How does DPR relate to RAG?
- **Route / Anchor:** `MULTI_CONCEPT` / `dpr`
- **Answer Claim Preview:** Here is what the available evidence shows about **DPR** and **RAG**. • **DPR** is indexed, but the selected source passage does not verify its stored summary, so I cannot use that summary as a sourced definition. • **RAG
- **Before (1 citations, badge `Passage located · Grounded`):**
  - `[1]` `papers/Lewis2020_RAG.pdf` (`chunk_id=chunk_011`, p.4, concept=`rag`): "We jointly train the retriever and generator components without any direct supervision on what document should be retrieved. Given a ﬁne-tuning training corpus"
- **After (1 citations, badge `Provenance verified · Claim support unassessed`, `claim_support_status=not_assessed`):**
  - `[S1]` `papers/Lewis2020_RAG.pdf` (`chunk_id=chunk_011`, `canonical_passage_id=papers/Lewis2020_RAG.pdf::chunk_011`, p.4, `provenance=provenance_verified/exact_unique_canonical_chunk`, origin=`/read?doc=papers%2FLewis2020_RAG.pdf&page=4`): "We jointly train the retriever and generator components without any direct supervision on what document should be retrieved. Given a ﬁne-tuning training corpus of input/output pair"

## 3. Dev-15 Per-Query After Evidence (`DEV01`–`DEV15`)

| Query ID | Anchor | Cites | Traceable Origin (`doc_id::chunk_id` / status) | Raw Source Snippet (Rank 1) |
|---|---|---:|---|---|
| `DEV01` | `attention_mechanism` | 3 | `papers/Bahdanau2014_Attention.pdf::chunk_010` (p.4, `provenance_verified`); `papers/Velickovic2017_GAT.pdf::chunk_028` (p.8, `provenance_verified`); `papers/Kwon2023_vLLM.pdf::chunk_018` (p.5, `provenance_verified`) | Published as a conference paper at ICLR 2015 the alignment is not considered to be a latent variable. Instead, the alignment model directly |
| `DEV02` | `gradient_descent` | 3 | `papers/Dettmers2023_QLoRA.pdf::chunk_009` (p.3, `provenance_verified`); `papers/Ho2020_DDPM.pdf::chunk_007` (p.3, `provenance_verified`); `papers/Kipf2016_GCN.pdf::chunk_023` (p.8, `provenance_verified`) | Low-rank Adapters Low-rank Adapter (LoRA) finetuning [28] is a method that reduces memory requirements by using a small set of trainable par |
| `DEV03` | `low_rank_adaptation` | 3 | `papers/Hu2021_LoRA.pdf::chunk_004` (p.2, `provenance_verified`); `papers/Hu2021_LoRA.pdf::chunk_027` (p.9, `provenance_verified`); `papers/Hu2021_LoRA.pdf::chunk_030` (p.10, `provenance_verified`) | often introduce inference latency (Houlsby et al., 2019; Rebufﬁet al., 2017) by extending model depth or reduce the model’s usable sequence |
| `DEV04` | `vector` | 1 | `papers/Edge2024_GraphRAG.pdf::chunk_007` (p.2, `provenance_verified`) | RAG generally refers to any system where a user query is used to retrieve relevant information from external data sources, whereupon this in |
| `DEV05` | `None` | 0 | `none` (clean abstention) | — |
| `DEV06` | `attention_mechanism` | 3 | `papers/Bahdanau2014_Attention.pdf::chunk_010` (p.4, `provenance_verified`); `papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_005` (p.2, `provenance_verified`); `papers/Velickovic2017_GAT.pdf::chunk_026` (p.8, `provenance_verified`) | Published as a conference paper at ICLR 2015 the alignment is not considered to be a latent variable. Instead, the alignment model directly |
| `DEV07` | `rag` | 2 | `papers/Lewis2020_RAG.pdf::chunk_011` (p.4, `provenance_verified`); `papers/Lewis2020_RAG.pdf::chunk_023` (p.6, `provenance_verified`) | We jointly train the retriever and generator components without any direct supervision on what document should be retrieved. Given a ﬁne-tun |
| `DEV08` | `kv_cache` | 3 | `papers/Kwon2023_vLLM.pdf::chunk_018` (p.5, `provenance_verified`); `papers/Kwon2023_vLLM.pdf::chunk_027` (p.7, `provenance_verified`); `papers/Kwon2023_vLLM.pdf::chunk_002` (p.1, `provenance_verified`) | CPU Block Allocator GPU Block Allocator Block tables Worker 0 Model Shard 0 Cache Engine Worker 1 Model Shard 1 Cache Engine Worker N - 1 Mo |
| `DEV09` | `qlora` | 3 | `papers/Dettmers2023_QLoRA.pdf::qlora_seed_002` (p.2, `provenance_verified`); `papers/Dettmers2023_QLoRA.pdf::qlora_seed_003` (p.3, `provenance_verified`); `papers/Dettmers2023_QLoRA.pdf::qlora_seed_001` (p.1, `provenance_verified`) | Table 1: Elo ratings for a competition between models, averaged for 10,000 random initial order- ings. The winner of a match is determined b |
| `DEV10` | `community_detection` | 3 | `papers/Edge2024_GraphRAG.pdf::chunk_019` (p.5, `provenance_verified`); `papers/Edge2024_GraphRAG.pdf::chunk_032` (p.9, `provenance_verified`); `papers/Edge2024_GraphRAG.pdf::chunk_021` (p.6, `provenance_verified`) | Given the graph index created in the previous step, a variety of community detection algorithms may be used to partition the graph into comm |
| `DEV11` | `retrieval` | 2 | `papers/Lewis2020_RAG.pdf::chunk_009` (p.3, `provenance_verified`); `papers/Lewis2020_RAG.pdf::chunk_032` (p.8, `provenance_verified`) | The retrieval component pη(z\|x) is based on DPR [26]. DPR follows a bi-encoder architecture: pη(z\|x) ∝exp   d(z)⊤q(x)  d(z) = BERTd(z), q(x |
| `DEV12` | `nearest_neighbor` | 3 | `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf::chunk_038` (p.7, `provenance_verified`); `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf::chunk_022` (p.4, `provenance_verified`); `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf::chunk_041` (p.8, `provenance_verified`) | The second method enhances anomaly detection by combining dy- namic clustering with ANN analysis [44]. This approach introduces an additiona |
| `DEV13` | `None` | 0 | `none` (clean abstention) | — |
| `DEV14` | `None` | 0 | `none` (clean abstention) | — |
| `DEV15` | `None` | 0 | `none` (clean abstention) | — |

## 4. Disclosed Regressions & Precise Known Limitations

1. **No semantic claim-support model in deterministic engine:** `claim_support_status` is explicitly `"not_assessed"`. Lexical token overlap is used strictly as a deterministic passage-relevance filter and never as proof of claim support.
2. **FlashAttention upload chunk provenance (`Q08`):** `okf_graph.json` stores FlashAttention under upload chunk ID `upload_cb7badb2_p2_2` rather than a canonical `chunk_NNN` corpus ID. Under the strict provenance policy, `Q08` is honestly marked `provenance_status = "chunk_unmatched"` (`upload_chunk_unmatched`) rather than pretending an exact canonical corpus match exists. Re-ingesting `papers/Dao2022_FlashAttention.pdf` into the canonical chunk store is a corpus-ingestion task outside Issue #11.
3. **Upstream router/graph anchor mismatches on some Dev-15 queries:** On `DEV01` ("What is Multi-Head Attention?"), the existing router resolves anchor `attention_mechanism` instead of `multi_head_attention`, so citations come from `attention_mechanism`'s sources (Bahdanau, GAT, vLLM). Similarly, `DEV04` resolves to `vector`, `DEV05` abstains (FAISS not indexed), and `DEV02` (`gradient_descent`) has only secondary paper mentions rather than a foundational textbook passage. Expanding the graph or changing router anchor resolution is outside Issue #11 scope.
4. **Q23 single-anchor recall trade-off:** Removing neighbor expansion eliminated 4/6 irrelevant citations (Vaswani, Outlines, Constitutional AI, GPT-3) on `Q23`, leaving the primary `Karpukhin2020_DPR.pdf::chunk_007` comparison passage. Because `graph.phrase_hits` did not emit `dpr` as a separate multi-char phrase hit (`MIN_PHRASE_LABEL_LEN = 4`), `dpr`'s second passage (`chunk_029`) was not added. This is a conservative precision-over-dilution trade-off.

## 5. Empirical Annotation Task Pointer

Independent human verification of **claim support** (separate from deterministic provenance verification) must be performed by named human reviewers using the blinded pooled worksheets and adjudication protocol managed under Issue #13 (`@eval-manuscript`):
- Worksheet artifact: `research/d5_sigir_evaluation/human_annotation_worksheet.json`
- Reviewer provenance log: `research/d5_sigir_evaluation/reviewer_provenance.json`
- Historical author-attributed D5 baseline (not independent peer review): `research/d5_sigir_evaluation/citation_grounding_audit.json`

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

> The Transformer uses multi-head attention in three different ways: • In "encoder-decoder attention" layers, the queries come from the previous decoder layer, and the memory keys and values come from the output of the encoder. This allows every position in the decoder to attend over all positions in the input sequence. This mimics the typical encoder-decoder attention mechanisms in sequence-to-sequence models such as [38, 2, 9]. • The encoder contains self-attention layers. In a self-attention layer all of the keys, values and queries come from the same place, in this case, the output of the previous layer in the encoder. Each position in the encoder can attend to all positions in the previous layer of the encoder. • Similarly, self-attention layers in the decoder allow each position in the decoder to attend to all positions in the decoder up to and including that position. We need to prevent leftward information flow in the decoder to preserve the auto-regressive property. We implement this inside of scaled dot-product attention by masking out (setting to −∞) all values in the input of the softmax which correspond to illegal connections. See Figure 2.

**My relevance score (0 / 1 / 2):** 0

**Reason (one sentence): Explains how multi-head attention and decoder masking work inside the Transformer, not what sequence-modeling flaws motivated replacing recurrence

**Uncertain? (yes / no):** no

### Passage 2 · CAND-03 (page label 10)
**Section:** N/A

> In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used in encoder-decoder architectures with multi-headed self-attention. For translation tasks, the Transformer can be trained significantly faster than architectures based on recurrent or convolutional layers. On both WMT 2014 English-to-German and WMT 2014 English-to-French translation tasks, we achieve a new state of the art. In the former task our best model outperforms even all previously reported ensembles. We are excited about the future of attention-based models and plan to apply them to other tasks. We plan to extend the Transformer to problems involving input and output modalities other than text and to investigate local, restricted attention mechanisms to efficiently handle large inputs and outputs such as images, audio and video. Making generation less sequential is another research goals of ours. The code we used to train and evaluate our models is available at https://github.com/ tensorflow/tensor2tensor.

**My relevance score (0 / 1 / 2):** 1

**Reason (one sentence): Mentions in the conclusion that the Transformer trains faster than recurrent models and notes a future goal of making generation less sequential, giving only indirect context on recurrence's limits

**Uncertain? (yes / no):** yes

### Passage 3 · CAND-01 (page label 3)
**Section:** N/A

> Consider one’s own thought process when solving a complicated reasoning task such as a multi-step math word problem. It is typical to decompose the problem into intermediate steps and solve each before giving the ﬁnal answer: “After Jane gives 2 ﬂowers to her mom she has 10 . . . then after she gives 3 to her dad she will have 7 . . . so the answer is 7.” The goal of this paper is to endow language models with the ability to generate a similar chain of thought—a coherent series of intermediate reasoning steps that lead to the ﬁnal answer for a problem. We will show that sufﬁciently large 2 language models can generate chains of thought if demonstrations of chain-of-thought reasoning are provided in the exemplars for few-shot prompting. Figure 1 shows an example of a model producing a chain of thought to solve a math word problem that it would have otherwise gotten incorrect. The chain of thought in this case resembles a solution and can interpreted as one, but we still opt to call it a chain of thought to better capture the idea that it mimics a step-by-step thought process for arriving at the answer (and also, solutions/explanations typically come after the ﬁnal answer (Narang et al., 2020; Wiegreffe et al., 2022; Lampinen et al., 2022, inter alia)). Chain-of-thought prompting has several attractive properties as an approach for facilitating reasoning in language models.

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Discusses chain-of-thought prompting for multi-step math word problems in language models and has nothing to do with Transformers or recurrence.

**Uncertain? (yes / no):** no

### Passage 4 · CAND-17 (page label 1)
**Section:** Abstract

> The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train. Our model achieves 28.4 BLEU on the WMT 2014 English- to-German translation task, improving over the existing best results, including ensembles, by over 2 BLEU. On the WMT 2014 English-to-French translation task, our model establishes a new single-model state-of-the-art BLEU score of 41.8 after training for 3.5 days on eight GPUs, a small fraction of the training costs of the best models from the literature. We show that the Transformer generalizes well to other tasks by applying it successfully to English constituency parsing both with large and limited training data.
> 
> ---

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Notes in the abstract that dropping recurrence and convolutions makes the Transformer more parallelizable and faster to train, offering partial evidence without explaining the underlying sequence-modeling bottlenecks.

**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? No
---

## Question 2 — CIKM-PILOT-005

**Question:** What mathematical assumption about weight updates during fine-tuning justifies LoRA's low-rank matrix decomposition?

### Passage 1 · CAND-10 (page label 3)
**Section:** 3.1 Encoder and Decoder Stacks

> Encoder: The encoder is composed of a stack of N = 6 identical layers. Each layer has two sub-layers. The first is a multi-head self-attention mechanism, and the second is a simple, position- wise fully connected feed-forward network. We employ a residual connection [11] around each of the two sub-layers, followed by layer normalization [1]. That is, the output of each sub-layer is LayerNorm(x + Sublayer(x)), where Sublayer(x) is the function implemented by the sub-layer itself. To facilitate these residual connections, all sub-layers in the model, as well as the embedding layers, produce outputs of dimension dmodel = 512. Decoder: The decoder is also composed of a stack of N = 6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack. Similar to the encoder, we employ residual connections around each of the sub-layers, followed by layer normalization. We also modify the self-attention sub-layer in the decoder stack to prevent positions from attending to subsequent positions. This masking, combined with fact that the output embeddings are offset by one position, ensures that the predictions for position i can depend only on the known outputs at positions less than i.

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes the standard Transformer encoder and decoder layer architecture without mentioning LoRA or fine-tuning weight updates.

**Uncertain? (yes / no):no

### Passage 2 · CAND-06 (page label 7)
**Section:** N/A

> LoRA adds trainable pairs of rank decomposition matrices in parallel to existing weight matrices. As mentioned in Section 4.2, we only apply LoRA to Wq and Wv in most experiments for simplicity. The number of trainable parameters is determined by the rank r and the shape of the original weights: |Θ| = 2 × ˆLLoRA × dmodel × r, where ˆLLoRA is the number of weight matrices we apply LoRA to. 6 Model & Method # Trainable E2E NLG Challenge Parameters BLEU NIST MET ROUGE-L CIDEr GPT-2 M (FT)* 354.92M 68.2 8.62 46.2 71.0 2.47 GPT-2 M (AdapterL)* 0.37M 66.3 8.41 45.0 69.8 2.40 GPT-2 M (AdapterL)* 11.09M 68.9 8.71 46.1 71.3 2.47 GPT-2 M (AdapterH) 11.09M 67.3±.6 8.50±.07 46.0±.2 70.7±.2 2.44±.01 GPT-2 M (FTTop2)* 25.19M 68.1 8.59 46.0 70.8 2.41 GPT-2 M (PreLayer)* 0.35M 69.7 8.81 46.1 71.4 2.49 GPT-2 M (LoRA) 0.35M 70.4±.1 8.85±.02 46.8±.2 71.8±.1 2.53±.02 GPT-2 L (FT)* 774.03M 68.5 8.78 46.0 69.9 2.45 GPT-2 L (AdapterL) 0.88M 69.1±.1 8.68±.03 46.3±.0 71.4±.2 2.49±.0 GPT-2 L (AdapterL) 23.00M 68.9±.3 8.70±.04 46.1±.1 71.3±.2 2.45±.02 GPT-2 L (PreLayer)* 0.77M 70.3 8.85 46.2 71.7 2.47 GPT-2 L (LoRA) 0.77M 70.4±.1 8.89±.02 46.8±.2 72.0±.2 2.47±.02 Table 3: GPT-2 medium (M) and large (L) with different adaptation methods on the E2E NLG Challenge. For all metrics, higher is better. LoRA outperforms several baselines with comparable or fewer trainable parameters. Conﬁdence intervals are shown for experiments we ran. * indicates numbers published in prior works. 5.2 ROBERTA BASE/LARGE

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Covers where LoRA inserts rank decomposition matrices, how trainable parameters are counted, and GPT-2 benchmark results rather than the mathematical assumption behind the method.

**Uncertain? (yes / no):no

### Passage 3 · CAND-03 (page label 4)
**Section:** N/A

> A Generalization of Full Fine-tuning. A more general form of ﬁne-tuning allows the training of a subset of the pre-trained parameters. LoRA takes a step further and does not require the accumu- lated gradient update to weight matrices to have full-rank during adaptation. This means that when applying LoRA to all weight matrices and training all biases2, we roughly recover the expressive- ness of full ﬁne-tuning by setting the LoRA rank r to the rank of the pre-trained weight matrices. In other words, as we increase the number of trainable parameters 3, training LoRA roughly converges to training the original model, while adapter-based methods converges to an MLP and preﬁx-based methods to a model that cannot take long input sequences. No Additional Inference Latency. When deployed in production, we can explicitly compute and store W = W0 + BA and perform inference as usual. Note that both W0 and BA are in Rd×k. When we need to switch to another downstream task, we can recover W0 by subtracting BA and then adding a different B′A′, a quick operation with very little memory overhead. Critically, this 2They represent a negligible number of parameters compared to weights. 3An inevitability when adapting to hard tasks. 4 guarantees that we do not introduce any additional latency during inference compared to a ﬁne-tuned model by construction. 4.2 APPLYING LORA TO TRANSFORMER

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): States that LoRA does not require accumulated gradient updates to weight matrices to have full rank during adaptation, providing partial evidence without explicitly framing the intrinsic-rank hypothesis.

**Uncertain? (yes / no):yes

### Passage 4 · CAND-11 (page label 10)
**Section:** N/A

> Table 6 shows that, surprisingly, LoRA already performs competitively with a very small r (more so for {Wq, Wv} than just Wq). This suggests the update matrix ∆W could have a very small “intrinsic rank”.6 To further support this ﬁnding, we check the overlap of the subspaces learned by different choices of r and by different random seeds. We argue that increasing r does not cover a more meaningful subspace, which suggests that a low-rank adaptation matrix is sufﬁcient. 6However, we do not expect a small r to work for every task or dataset. Consider the following thought experiment: if the downstream task were in a different language than the one used for pre-training, retraining the entire model (similar to LoRA with r = dmodel) could certainly outperform LoRA with a small r. 10 Subspace similarity between different r. Given Ar=8 and Ar=64 which are the learned adapta- tion matrices with rank r = 8 and 64 using the same pre-trained model, we perform singular value decomposition and obtain the right-singular unitary matrices UAr=8 and UAr=64.7 We hope to an- swer: how much of the subspace spanned by the top i singular vectors in UAr=8 (for 1 ≤i ≤8) is contained in the subspace spanned by top j singular vectors of UAr=64 (for 1 ≤j ≤64)? We mea- sure this quantity with a normalized subspace similarity based on the Grassmann distance (See Ap- pendix G for a more formal discussion) φ(Ar=8, Ar=64, i, j) = ||U i⊤ Ar=8U j Ar=64||2 F min(i, j) ∈[0, 1] (4) where U i Ar=8 represents the columns of UAr=8 corresponding to the top-i singular vectors.

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly states that the weight update matrix $\Delta W$ may have a very small "intrinsic rank" and backs this up by measuring singular-vector subspace overlap across ranks


**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? Yes

---

## Question 3 — CIKM-PILOT-013

**Question:** How does PagedAttention apply virtual memory paging concepts to eliminate KV-cache fragmentation in LLM serving?

### Passage 1 · CAND-12 (page label 5)
**Section:** vllm

> KV Cache Manager Scheduler CPU Block Allocator GPU Block Allocator Block tables Worker 0 Model Shard 0 Cache Engine Worker 1 Model Shard 1 Cache Engine Worker N - 1 Model Shard N - 1 Cache Engine … Figure 4. vLLM system overview. Although compaction [54] has been proposed as a poten- tial solution to fragmentation, performing compaction in a performance-sensitive LLM serving system is impractical due to the massive KV cache. Even with compaction, the pre-allocated chunk space for each request prevents memory sharing specific to decoding algorithms in existing memory management systems. 4 Method In this work, we develop a new attention algorithm, Page- dAttention, and build an LLM serving engine, vLLM, to tackle the challenges outlined in §3. The architecture of vLLM is shown in Fig. 4. vLLM adopts a centralized scheduler to coordinate the execution of distributed GPU workers. The KV cach

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Explains why memory compaction is impractical for massive KV caches and introduces vLLM's block allocators and block tables, giving useful context before detailing the paging mechanism

**Uncertain? (yes / no):no

### Passage 2 · CAND-10 (page label 8)
**Section:** 5.1 Effect of Pre-training Tasks

> results are still far worse than those of the pre- trained bidirectional models. The BiLSTM hurts performance on the GLUE tasks. We recognize that it would also be possible to train separate LTR and RTL models and represent each token as the concatenation of the two mod- els, as ELMo does. However: (a) this is twice as expensive as a single bidirectional model; (b) this is non-intuitive for tasks like QA, since the RTL model would not be able to condition the answer on the question; (c) this it is strictly less powerful than a deep bidirectional model, since it can use both left and right context at every layer.

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Discusses BERT bidirectional pre-training ablations on GLUE and has no connection to PagedAttention or KV-cache fragmentation.

**Uncertain? (yes / no):no

### Passage 3 · CAND-09 (page label 6)
**Section:** 3 KV cache states for request B’s prompt

> Again, vLLM dynamically assigns new physical blocks to logical blocks as more tokens and their KV cache are gener- ated. As all the blocks are filled from left to right and a new physical block is only allocated when all previous blocks are full, vLLM limits all the memory wastes for a request within one block, so it can effectively utilize all the memory, as shown in Fig. 2. This allows more requests to fit into mem- ory for batching—hence improving the throughput. Once a request finishes its generation, its KV blocks can be freed to store the KV cache of other requests. In Fig. 7, we show an example of vLLM managing the memory for two sequences. The logical blocks of the two sequences are mapped to differ- ent physical blocks within the space reserved by the block engine in GPU workers. The neighboring logical blocks of both sequences do not need to be contiguous in physical GPU memory and the space of physical blocks can be effectively utilized by both sequences. 4.4 Application to Other Decoding Scenarios §4.3 shows how PagedAttention and vLLM handle basic de- coding algorithms, such as greedy decoding and sampling, that take one user prompt as input and generate a single out- put sequence. In many successful LLM applications [18, 34], an LLM service must offer more complex decoding scenarios that exhibit complex accessing patterns and more opportuni- ties for memory sharing. We show the general applicability of vLLM on them in this section.

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly explains how vLLM dynamically maps logical blocks to non-contiguous physical GPU blocks on demand and keeps internal memory waste within a single block per request.

**Uncertain? (yes / no):no

### Passage 4 · CAND-07 (page label 5)
**Section:** 3 KV cache states for request B’s prompt

> During the attention computation, the PagedAttention kernel identifies and fetches different KV blocks separately. We show an example of PagedAttention in Fig. 5: The key and value vectors are spread across three blocks, and the three blocks are not contiguous on the physical memory. At each time, the kernel multiplies the query vector 𝑞𝑖of the query token (“forth”) and the key vectors 𝐾𝑗in a block (e.g., key vectors of “Four score and seven” for block 0) to compute the attention score𝐴𝑖𝑗, and later multiplies𝐴𝑖𝑗with the value vectors 𝑉𝑗in a block to derive the final attention output 𝑜𝑖. In summary, the PagedAttention algorithm allows the KV blocks to be stored in non-contiguous physical memory, which enables more flexible paged memory management in vLLM. 4.2 KV Cache Manager The key idea behind vLLM’s memory manager is analogous to the virtual memory [25] in operating systems. OS parti- tions memory into fixed-sized pages and maps user programs’ logical pages to physical pages. Contiguous logical pages can correspond to non-contiguous physical memory pages, al- lowing user programs to access memory as though it were contiguous. Moreover, physical memory space needs not to be fully reserved in advance, enabling the OS to dynamically allocate physical pages as needed. vLLM uses the ideas be- hind virtual memory to manage the KV cache in an LLM service. Enabled by PagedAttention, we organize the KV cache as fixed-size KV blocks, like pages in virtual memory.

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly answers the question by showing how PagedAttention fetches non-contiguous KV blocks and adapts OS virtual memory pagingfixed-size logical-to-physical block mapping and dynamic allocationto the KV cache.

**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? Yes
---

## Question 4 — CIKM-PILOT-002

**Question:** Why does scaled dot-product attention divide by the square root of the key dimension before applying softmax?

### Passage 1 · CAND-04 (page label 5)
**Section:** N/A

> Instead of performing a single attention function with dmodel-dimensional keys, values and queries, we found it beneficial to linearly project the queries, keys and values h times with different, learned linear projections to dk, dk and dv dimensions, respectively. On each of these projected versions of queries, keys and values we then perform the attention function in parallel, yielding dv-dimensional 4To illustrate why the dot products get large, assume that the components of q and k are independent random variables with mean 0 and variance 1. Then their dot product, q · k = Pdk i=1 qiki, has mean 0 and variance dk. 4 output values. These are concatenated and once again projected, resulting in the final values, as depicted in Figure 2. Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions. With a single attention head, averaging inhibits this. MultiHead(Q, K, V ) = Concat(head1, ..., headh)W O where headi = Attention(QW Q i , KW K i , V W V i ) Where the projections are parameter matrices W Q i ∈Rdmodel×dk, W K i ∈Rdmodel×dk, W V i ∈Rdmodel×dv and W O ∈Rhdv×dmodel. In this work we employ h = 8 parallel attention layers, or heads. For each of these we use dk = dv = dmodel/h = 64. Due to the reduced dimension of each head, the total computational cost is similar to that of single-head attention with full dimensionality.

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Focuses on multi-head projections but includes a footnote proving that dot products of unit-variance vectors have variance $d_k$, which supplies partial mathematical evidence without mentioning softmax gradients. 


**Uncertain? (yes / no):no	

### Passage 2 · CAND-13 (page label 4)
**Section:** 3.2.1 Scaled Dot-Product Attention

> We call our particular attention "Scaled Dot-Product Attention" (Figure 2). The input consists of queries and keys of dimension dk, and values of dimension dv. We compute the dot products of the query with all keys, divide each by √dk, and apply a softmax function to obtain the weights on the values. In practice, we compute the attention function on a set of queries simultaneously, packed together into a matrix Q. The keys and values are also packed together into matrices K and V . We compute the matrix of outputs as: Attention(Q, K, V ) = softmax(QKT √dk )V (1) The two most commonly used attention functions are additive attention [2], and dot-product (multi- plicative) attention. Dot-product attention is identical to our algorithm, except for the scaling factor of 1 √dk . Additive attention computes the compatibility function using a feed-forward network with a single hidden layer. While the two are similar in theoretical complexity, dot-product attention is much faster and more space-efficient in practice, since it can be implemented using highly optimized matrix multiplication code. While for small values of dk the two mechanisms perform similarly, additive attention outperforms dot product attention without scaling for larger values of dk [3]. We suspect that for large values of dk, the dot products grow large in magnitude, pushing the softmax function into regions where it has extremely small gradients 4. To counteract this effect, we scale the dot products by 1 √dk .

**My relevance score (0 / 1 / 2):2

**Reason (one sentence): Directly states that large $d_k$ makes dot products grow large and push softmax into regions with tiny gradients, which dividing by $\sqrt{d_k}$ counteracts. 


**Uncertain? (yes / no):no

### Passage 3 · CAND-09 (page label 3)
**Section:** 3. FlashAttention Algorithm with Tiling and Incremental Softmax

> The core algorithm employs tiling to compute attention in SRAM blocks. Given inputs Q, K, V in HBM, FlashAttention loads blocks of Q, K, and V into on-chip SRAM. To compute softmax over blocks without materializing the full row, it uses an incremental scaling technique known as Online Softmax. As each block of K and V is loaded, FlashAttention updates the partial output vector and rescales previou

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes FlashAttention's SRAM tiling and online softmax rescaling rather than why scaled dot-product attention divides by $\sqrt{d_k}$. 


**Uncertain? (yes / no):no

### Passage 4 · CAND-08 (page label 4)
**Section:** N/A

> An attention function can be described as mapping a query and a set of key-value pairs to an output, where the query, keys, values, and output are all vectors. The output is computed as a weighted sum 3 Scaled Dot-Product Attention Multi-Head Attention Figure 2: (left) Scaled Dot-Product Attention. (right) Multi-Head Attention consists of several attention layers running in parallel. of the values, where the weight assigned to each value is computed by a compatibility function of the query with the corresponding key.

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Gives only the general definition of attention as a weighted sum of values and does not discuss scaling by $\sqrt{d_k}$ or softmax behavior. 


**Uncertain? (yes / no):no

**Does at least one of these four passages provide a direct answer? Yes 
---

## Question 5 — CIKM-PILOT-004

**Question:** How does multi-head self-attention in Vaswani et al. (2017) differ from additive encoder-decoder alignment in Bahdanau et al. (2014)?

### Passage 1 · CAND-17 (page label 5)
**Section:** 3.3 Position-wise Feed-Forward Networks

> In addition to attention sub-layers, each of the layers in our encoder and decoder contains a fully connected feed-forward network, which is applied to each position separately and identically. This consists of two linear transformations with a ReLU activation in between. FFN(x) = max(0, xW1 + b1)W2 + b2 (2) While the linear transformations are the same across different positions, they use different parameters from layer to layer. Another way of describing this is as two convolutions with kernel size 1. The dimensionality of input and output is dmodel = 512, and the inner-layer has dimensionality dff = 2048.

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes the Transformer's position-wise feed-forward sub-layer and says nothing about self-attention or Bahdanau alignment.

**Uncertain? (yes / no):no

### Passage 2 · CAND-08 (page label 12)
**Section:** IEEE Transactions on, 45(11), 2673–2681.

> The update gates zi allow each hidden unit to maintain its previous activation, and the reset gates ri control how much and what information from the previous state should be reset. We compute them by zi = σ (Wze(yi−1) + Uzsi−1 + Czci) , ri = σ (Wre(yi−1) + Ursi−1 + Crci) , where σ (·) is a logistic sigmoid function. At each step of the decoder, we compute the output probability (Eq. (4)) as a multi-layered func- tion (Pascanu et al., 2014). We use a single hidden layer of maxout units (Goodfellow et al., 2013) and normalize the output probabilities (one for each word) with a softmax function (see Eq. (6)). A.1.2 ALIGNMENT MODEL The alignment model should be designed considering that the model needs to be evaluated Tx × Ty times for each sentence pair of lengths Tx and Ty. In order to reduce computation, we use a single- layer multilayer perceptron such that a(si−1, hj) = v⊤ a tanh (Wasi−1 + Uahj) , where Wa ∈Rn×n, Ua ∈Rn×2n and va ∈Rn are the weight matrices. Since Uahj does not depend on i, we can pre-compute it in advance to minimize the computational cost. 8 Here, we show the formula of the decoder. The same formula can be used in the encoder by simply ignoring the context vector ci and the related terms. 12 Published as a conference paper at ICLR 2015 A.2 DETAILED DESCRIPTION OF THE MODEL A.2.1 ENCODER In this section, we describe in detail the architecture of the proposed model (RNNsearch) used in the experiments (see Sec. 4–5). From here on, we omit all bias terms in order to increase readability.

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Provides half of the comparison by detailing Bahdanau et al.'s single-layer MLP additive alignment formula between decoder and encoder states, without mentioning Vaswani et al.'s multi-head self-attention.

**Uncertain? (yes / no):no

### Passage 3 · CAND-07 (page label 10)
**Section:** N/A

> In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used in encoder-decoder architectures with multi-headed self-attention. For translation tasks, the Transformer can be trained significantly faster than architectures based on recurrent or convolutional layers. On both WMT 2014 English-to-German and WMT 2014 English-to-French translation tasks, we achieve a new state of the art. In the former task our best model outperforms even all previously reported ensembles. We are excited about the future of attention-based models and plan to apply them to other tasks. We plan to extend the Transformer to problems involving input and output modalities other than text and to investigate local, restricted attention mechanisms to efficiently handle large inputs and outputs such as images, audio and video. Making generation less sequential is another research goals of ours. The code we used to train and evaluate our models is available at https://github.com/ tensorflow/tensor2tensor.

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Gives high-level context that the Transformer replaces recurrent encoder-decoder layers with multi-headed self-attention, but lacks the structural details needed to contrast it with additive alignment.

**Uncertain? (yes / no):yes

### Passage 4 · CAND-16 (page label 5)
**Section:** 3.2.3 Applications of Attention in our Model

> The Transformer uses multi-head attention in three different ways: • In "encoder-decoder attention" layers, the queries come from the previous decoder layer, and the memory keys and values come from the output of the encoder. This allows every position in the decoder to attend over all positions in the input sequence. This mimics the typical encoder-decoder attention mechanisms in sequence-to-sequence models such as [38, 2, 9]. • The encoder contains self-attention layers. In a self-attention layer all of the keys, values and queries come from the same place, in this case, the output of the previous layer in the encoder. Each position in the encoder can attend to all positions in the previous layer of the encoder. • Similarly, self-attention layers in the decoder allow each position in the decoder to attend to all positions in the decoder up to and including that position. We need to prevent leftward information flow in the decoder to preserve the auto-regressive property. We implement this inside of scaled dot-product attention by masking out (setting to −∞) all values in the input of the softmax which correspond to illegal connections. See Figure 2.

**My relevance score (0 / 1 / 2):1

**Reason (one sentence): Contrasts Transformer encoder and decoder self-attention with encoder-decoder cross-attention (citing Bahdanau et al. as [2]), offering partial comparative evidence while omitting multi-head projection and dot-product versus additive scoring differences.

**Uncertain? (yes / no):yes

**Does at least one of these four passages provide a direct answer? No

---

## Question 6 — CIKM-PILOT-023

**Question:** What exact hyperparameters does DeepSeek-R1 use for GRPO reinforcement learning on math benchmarks?

### Passage 1 · CAND-15 (page label 10)
**Section:** N/A

> On tasks that involve choosing one correct completion from several options (multiple choice), we provide K examples of context plus correct completion, followed by one example of context only, and compare the LM likelihood of each completion. For most tasks we compare the per-token likelihood (to normalize for length), however on a small number of datasets (ARC, OpenBookQA, and RACE) we gain additional beneﬁt as measured on the development set by normalizing by the unconditional probability of each completion, by computing P (completion|context) P (completion|answer context), where answer context is the string "Answer: " or "A: " and is used to prompt that the completion should be an answer but is otherwise generic. On tasks that involve binary classiﬁcation, we give the options more semantically meaningful names (e.g. “True” or “False” rather than 0 or 1) and then treat the task like multiple choice; we also sometimes frame the task similar to what is done by [RSR+19] (see Appendix G) for details. On tasks with free-form completion, we use beam search with the same parameters as [RSR+19]: a beam width of 4 and a length penalty of α = 0.6. We score the model using F1 similarity score, BLEU, or exact match, depending on what is standard for the dataset at hand.

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Describes few-shot evaluation and beam search parameters from the GPT-3 paper rather than DeepSeek-R1 or GRPO.

**Uncertain? (yes / no):yes

### Passage 2 · CAND-18 (page label 2)
**Section:** N/A

> Table 1: Elo ratings for a competition between models, averaged for 10,000 random initial order- ings. The winner of a match is determined by GPT-4 which declares which response is better for a given prompt of the the Vicuna benchmark. 95% confidence intervals are shown (±). After GPT- 4, Guanaco 33B and 65B win the most matches, while Guanaco 13B scores better than Bard. Model Size Elo GPT-4 - 1348 ± 1 Guanaco 65B 41 GB 1022 ± 1 Guanaco 33B 21 GB 992 ± 1 Vicuna 13B 26 GB 974 ± 1 ChatGPT - 966 ± 1 Guanaco 13B 10 GB 916 ± 1 Bard - 902 ± 1 Guanaco 7B 6 GB 879 ± 1 that are tuned by backpropagating gradients through the quantized weights. QLORA reduces the average memory requirements of finetuning a 65B parameter model from >780GB of GPU memory to <48GB without degrading the runtime or predictive performance compared to a 16- bit fully finetuned baseline. This marks a significant shift in accessibility of LLM finetuning: now the largest publicly available models to date finetunable on a single GPU. Using QLORA, we train the Gua- naco family of models, with the second best model reaching 97.8% of the performance level of ChatGPT on the Vicuna [10] benchmark, while being trainable in less than 12 hours on a single consumer GPU; using a single professional GPU over 24 hours we achieve 99.3% with our largest model, essentially closing the gap to ChatGPT on the Vicuna bench- mark. When deployed, our smallest Guanaco model (7B parameters) requires just 5 GB of memory and outperforms a 26 GB Alpaca model by more than 20 percentage points on the Vicuna benchmark (Table 6).

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Reports Vicuna Elo ratings and GPU memory savings for QLoRA and Guanaco models, which is unrelated to DeepSeek-R1 or GRPO.

**Uncertain? (yes / no):no

### Passage 3 · CAND-13 (page label 9)
**Section:** N/A

> where πRL φ is the learned RL policy, πSFT is the supervised trained model, and Dpretrain is the pretraining distribution. The KL reward coefﬁcient, β, and the pretraining loss coefﬁcient, γ, control the strength of the KL penalty and pretraining gradients respectively. For "PPO" models, γ is set to 0. Unless otherwise speciﬁed, in this paper InstructGPT refers to the PPO-ptx models. Baselines. We compare the performance of our PPO models to our SFT models and GPT-3. We also compare to GPT-3 when it is provided a few-shot preﬁx to ‘prompt’ it into an instruction-following mode (GPT-3-prompted). This preﬁx is prepended to the user-speciﬁed instruction.6 We additionally compare InstructGPT to ﬁne-tuning 175B GPT-3 on the FLAN (Wei et al., 2021) and T0 (Sanh et al., 2021) datasets, which both consist of a variety of NLP tasks, combined with natural language instructions for each task (the datasets differ in the NLP datasets included, and the style of instructions used). We ﬁne-tune them on approximately 1 million examples respectively and choose the checkpoint which obtains the highest reward model score on the validation set. See Appendix C for more training details.

**My relevance score (0 / 1 / 2):0

**Reason (one sentence): Covers PPO-ptx KL and pretraining loss coefficients from the InstructGPT paper rather than DeepSeek-R1's GRPO hyperparameters.

**Uncertain? (yes / no):no

### Passage 4 · CAND-03 (page label 1)
**Section:** Abstract

> Making language models bigger does not inherently make them better at following a user’s intent. For example, large language models can generate outputs that are untruthful, toxic, or simply not helpful to the user. In other words, these models are not aligned with their users. In this paper, we show an avenue for aligning language models with user intent on a wide range of tasks by ﬁne-tuning with human feedback. Starting with a set of labeler-written prompts and prompts submitted through the OpenAI API, we collect a dataset of labeler demonstrations of the desired model behavior, which we use to ﬁne-tune GPT-3 using supervised learning. We then collect a dataset of rankings of model outputs, which we use to further ﬁne-tune this supervised model using reinforcement learning from human feedback. We call the resulting models InstructGPT. In human evaluations on our prompt distribution, outputs from the 1.3B parameter InstructGPT model are preferred to outputs from the 175B GPT-3, despite having 100x fewer parameters. Moreover, InstructGPT models show improvements in truthfulness and reductions in toxic output generation while having minimal performance regressions on public NLP datasets. Even though InstructGPT still makes simple mistakes, our results show that ﬁne-tuning with human feedback is a promising direction for aligning language models with human intent.

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

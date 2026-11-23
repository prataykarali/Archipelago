# Archipelago — Five-Minute SIGIR Demonstration Walkthrough

**Target URL:** `https://archipelago-blond.vercel.app/chat`
**Duration:** 5 minutes (timed)
**Prerequisite:** Valid student credentials for Supabase authentication

---

## Setup (30 seconds)

1. Open `https://archipelago-blond.vercel.app/chat` in Chrome or Firefox.
2. Click **Sign In** and authenticate with student credentials.
3. Confirm the chat interface loads with the Archipelago Research
   Workspace layout: message input at bottom, graph inspector panel on
   the right, evidence drawer accessible from the toolbar.

> If login fails, verify Supabase credentials and check browser console
> for auth errors. The logout URL is `?logout=1`.

---

## Scenario 1: Transformer Concept Reasoning (2 minutes)

### Turn 1 — Concept Resolution (40 seconds)

**Type:** `What is a Transformer?`

**Point out:**
- The answer references Vaswani et al. 2017 "Attention Is All You Need"
- The **grounding badge** shows a verified graph match (green indicator)
- The **graph inspector** highlights the `transformer` concept node
- **Evidence panel** shows the supporting passage from Vaswani 2017

**Key claim:** The system resolves "Transformer" to a canonical concept
node and grounds the answer in a verified source passage, not a generic
LLM completion.

### Turn 2 — Relationship Traversal (40 seconds)

**Type:** `What is self-attention and how does it relate to Transformers?`

**Point out:**
- The graph inspector now shows the `self_attention` connected to `transformer`
  with a **RELATED / REQUIRES** relationship
- The specific architectural role (self-attention as a foundational component
  of the Transformer) is synthesized in the grounded text response and supported
  by citations
- Citation links to Vaswani 2017 §3.2 (Scaled Dot-Product Attention)

**Key claim:** Relationship traversal connects related concepts without asserting
fabricated structural edge labels.

### Turn 3 — Prerequisite Chain (40 seconds)

**Type:** `What mathematical concepts are prerequisites for self-attention?`

**Point out:**
- The graph shows `self_attention → matrix_multiplication` and
  `self_attention → softmax` with **REQUIRES** edges
- These are **pedagogical prerequisites**, connecting attention mechanisms
  to underlying mathematical foundations
- The human review record classifies them as `pedagogical_consensus`
- The evidence passage explains why linear algebra is foundational

**Key claim:** The system captures prerequisite learning paths (`REQUIRES`),
a distinction not captured by flat lexical retrieval.

---

## Scenario 2: DPR and RAG (1.5 minutes)

### Turn 4 — RAG Architecture (45 seconds)

**Type:** `How does Retrieval-Augmented Generation work?`

**Point out:**
- Concept resolved to `rag` with citation to Lewis et al. 2020
- Graph shows `rag` connected to `dpr` (`REQUIRES`) and `transformer` (`RELATED`)
- The evidence panel displays the supporting passage from the RAG paper
- The grounding badge confirms verified graph match

**Key claim:** Multi-hop concept relationships — RAG connects to dense retrieval
and transformer sequence-to-sequence foundations.

### Turn 5 — Contrastive Evaluation (45 seconds)

**Type:** `How does DPR compare to BM25 for passage retrieval?`

**Point out:**
- The response synthesizes the contrast between dense bi-encoder retrieval and sparse BM25
- Citations to Karpukhin et al. 2020 (DPR paper) and Lewis et al. 2020 (RAG paper)
- The evidence passage explains DPR's learned dense representations
  versus BM25's lexical matching
- Controlled evaluation on the held-out set (D5.1-v2, algorithmic qrels, not human-verified):
  BM25 (MRR=0.75, nDCG@5=0.6415), Snowflake-Arctic neural dense (MRR=0.75, nDCG@5=0.6524),
  Feature-Hashed Vector (MRR=0.28), Graph-Assisted (MRR=0.4865 — heuristic decay scores, not learned).
  Source: `research/d5_sigir_evaluation/d5_1_evaluation_results_v2.json`.

**Key claim:** The system grounds comparative IR methodology in dual original
literature citations rather than unverified contrastive graph edges.

---

## Scenario 3: Honest Unsupported-Topic Handling (1 minute)

### Turn 6 — Abstention (60 seconds)

**Type:** `Explain how Spanner TrueTime works and what are its prerequisites`

**Point out:**
- The grounding badge shows **"No Verified Graph Match"** (amber/gray)
- The system does NOT fabricate a prerequisite path or citation
- No graph edges are displayed — the inspector shows an empty subgraph
- The response may provide general knowledge but clearly disclaims
  verified graph grounding
- The trace intent is `GUARDRAIL_INTERCEPT` or `GENERAL_EXPLANATION`

**Key claim:** Perfect abstention precision (1.0) — the system never
fabricates knowledge graph structure for unsupported topics. This is a
critical scientific integrity property.

---

## Wrap-Up (30 seconds)

Summarize the three contributions demonstrated:

1. **Structured concept resolution** — Archipelago resolver: 68.4% concept-resolution
   accuracy on supported queries (26/38 hits), vs BM25 at 42.1% and Snowflake neural at
   36.8%. Source: D5.1-v2, Experiment A.
2. **Knowledge graph traversal** — Graph surfaces `RELATED`, `REQUIRES`, `UNLOCKS` edges.
   `USES`, `CONTRASTS_WITH`, and `APPLIES_TO` are absent from the runtime schema; 13/18
   relational queries have predicates absent from the graph (D5.1-v2 relationship audit).
3. **Honest abstention** for unsupported topics — 12 out-of-corpus queries return zero
   citations and zero fabricated graph edges (D5.3-A verified).

Note that this is a **Demonstrations Track** submission — the system is live and deployed.
Passage qrels are algorithmically generated (not human-verified); citation grounding has
29% strict precision across 24 audited citations (7/24 fully supported, 9/24 irrelevant or
spurious). An independent annotation pass has not yet been completed.

---

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| Login page loops | Append `?logout=1` to URL, then sign in again |
| Graph inspector empty | Click the graph icon in the toolbar; it may be collapsed |
| Evidence panel not showing | Click the evidence/citation link in the answer |
| Slow first query | Cold start; subsequent queries use cached graph (median 15 ms) |
| "No Verified Graph Match" on supported topic | Alias coverage gap; documented as a known limitation |

---

## Evaluation References

| Artifact | Path |
|----------|------|
| Full evaluation report | `research/d5_sigir_evaluation/D5_EVALUATION_REPORT.md` |
| Results data | `research/d5_sigir_evaluation/d5_1_evaluation_results_v2.json` |
| Graph slice | `research/d5_sigir_evaluation/d5_graph_slice.json` |
| Human reviews | `research/d5_sigir_evaluation/human_review_records.json` |
| Benchmark script | `scripts/benchmarks/d5_retrieval_benchmark.py` |
| Demo scenarios (detailed) | `docs/sigir/DEMO_SCENARIOS.md` |

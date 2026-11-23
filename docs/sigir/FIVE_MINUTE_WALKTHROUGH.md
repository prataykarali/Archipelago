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

### Turn 3 — Prerequisite Neighborhood Inspection (40 seconds)

**Type:** `What mathematical concepts are prerequisites for self-attention?`

**Point out (verified live runtime behavior):**
- Note that this compound phrasing currently resolves to `attention_mechanism` with an empty prerequisite list (`prereqs=[]`), whereas `transformer` (Turn 1) and `self_attention` (Turn 2) expose `matrix_multiplication` and `linear_algebra` in their prerequisite neighborhoods.
- Use this transparently to show both what the live graph surfaces and where compound query resolution / relation extraction still fail (0.0 exact triple F1 in D5.1-v2).

---

## Scenario 2: DPR and RAG (1.5 minutes)

### Turn 4 — RAG Architecture (45 seconds)

**Type:** `How does Retrieval-Augmented Generation work?`

**Point out:**
- Concept resolves to `rag` with rank-1 citation to `papers/Lewis2020_RAG.pdf` (Page 4)
- Graph neighborhood shows `rag` related to `retrieval_augmented_generation`, `language_model`, `gpt_2`, and unlocking `advanced_rag`
- Be transparent about neighborhood citation dilution (peripheral papers can appear at lower ranks; 37.5% spurious rate in the 24-citation author audit)

### Turn 5 — Contrastive Evaluation (45 seconds)

**Type:** `How does DPR compare to BM25 for passage retrieval?`

**Point out:**
- Concept resolves to `retrieval`, whose neighborhood includes `dpr`, `dense_passage_retriever`, and `bm25`, with citations to `Lewis2020_RAG.pdf` (Pages 3, 7) and `Devlin2018_BERT.pdf` (Page 7)
- Controlled evaluation on the held-out set (D5.1-v2, **algorithmic candidate qrels, NOT human-verified**):
  BM25 (MRR=0.7500, nDCG@5=0.6415), Snowflake-Arctic neural dense (MRR=0.7500, nDCG@5=0.6524),
  Archipelago Graph-Assisted (MRR=0.4865, nDCG@5=0.2253 — heuristic decay scores, not learned),
  Feature-Hashed Vector (MRR=0.2806, nDCG@5=0.1764).
  Source: `research/d5_sigir_evaluation/d5_1_evaluation_results_v2.json`.

**Key claim:** The system surfaces related retrieval concepts in the graph neighborhood while disclosing that flat BM25 and neural dense rankers outperform graph-assisted citation retrieval on passage-level ranking.

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

**Key claim:** 12/12 (100%) anchor-abstention accuracy on the 12 held-out out-of-domain
benchmark queries (`Q39`–`Q50`, returning `anchor_concept=None`, `render_graph=False`,
and 0 corpus passage citations; 11/12 return 0 total citations while `Q45` surfaces 1
Pearson catalog book metadata entry).

---

## Wrap-Up (30 seconds)

Summarize the three contributions demonstrated:

1. **Structured concept resolution** — Archipelago resolver: 68.4% concept-resolution
   accuracy on supported queries (26/38 hits), vs BM25 at 42.1% and Snowflake neural at
   36.8%. Source: D5.1-v2, Experiment A.
2. **Knowledge graph traversal** — Graph surfaces `RELATED`, `REQUIRES`, `UNLOCKS` edges.
   `USES`, `CONTRASTS_WITH`, and `APPLIES_TO` are absent from the runtime schema; 13/18
   relational queries have predicates absent from the graph (D5.1-v2 relationship audit).
3. **Honest abstention** for unsupported topics — 12/12 out-of-corpus queries return
   `anchor_concept=None`, `render_graph=False`, and zero indexed paper citations (11/12
   return 0 total citations; `Q45` surfaces 1 Pearson catalog book metadata entry).

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

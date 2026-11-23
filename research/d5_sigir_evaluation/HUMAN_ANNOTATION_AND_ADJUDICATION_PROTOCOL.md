# Archipelago D5 — Human Relevance Annotation & Adjudication Protocol

**Target Venue:** ACM SIGIR 2027 Demonstrations Track  
**Benchmark Artifact Directory:** `research/d5_sigir_evaluation/`  
**Status:** `PENDING_HUMAN_ANNOTATION` (0 human relevance judgments completed)  
**Blinding Model:** **System-Blinded (Single-Blinded) Pooled Top-5 Assessment**

> [!IMPORTANT]
> **Terminology Discipline:** This protocol is **system-blinded (single-blinded)**
> pooled IR relevance assessment, **NOT** a clinical "double-blind" study. Annotators
> are blinded to which retrieval system(s) surfaced each candidate, the retrieval rank,
> the retrieval score, and each other's grades. The study coordinator holds the sealed
> pool key (`worksheets/pool_key_SEALED.json`) strictly outside annotator packets.
> Do not describe this protocol as "double-blind" in manuscripts or reports.

---

## 1. Purpose & Scientific Gap Being Closed

All current passage-level relevance labels in `passage_qrels.json` (445 positive labels
across 37 of 50 held-out queries) are **`ALGORITHMIC_RULE_BASED_CANDIDATE`** labels
generated via keyword density and document substring matching (`human_reviewed: false`).
Consequently, current Experiment B passage-retrieval metrics are provisional and cannot
be reported as human-validated retrieval benchmarks.

This protocol defines the exact procedure for collecting independent human relevance and
claim-support judgments over the frozen held-out query set (`queries_heldout_50.json`,
SHA-256 `9e39430942b4f00d34911848cbe61a96532c29ffaee76f0d82ce69496f71103a`) and the
775-passage corpus (`okf_graph.json`, SHA-256
`9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`).

---

## 2. Pooled Top-5 Construction & Blinding Guarantees

Generated deterministically by `research/d5_sigir_evaluation/build_blinded_pool.py`
from the four frozen TREC run files in `research/d5_sigir_evaluation/ranked_runs/`:

| System | Run File | Top-5 Depth | Pool Coverage |
|---|---|---:|---:|
| BM25Okapi (`k1=1.5, b=0.75`) | `bm25.run` | 5 | 100% |
| Snowflake-Arctic-Embed-M (Neural Dense) | `snowflake_arctic_neural.run` | 5 | 100% |
| Feature-Hashed Vector (BLAKE2b, 384-d) | `feature_hashed_vector.run` | 5 | 100% |
| Archipelago Graph-Assisted (Heuristic) | `archipelago_graph_assisted.run` | 5 | 100% |

- **Total pooled items:** **731** unique `(query_id, passage_id)` pairs across all **50** held-out queries.
- **Candidate ID blinding:** Each `(query_id, passage_id)` is assigned a deterministic
  hash ID (`CAND-<12-hex>`) derived from `sha256(salt || query_id || passage_id)`.
- **Order randomization:** Within each query, candidates are sorted by `blinded_candidate_id`
  rather than retrieval rank or system order, preventing position bias.
- **Sealed key separation:** `worksheets/pool_key_SEALED.json` maps `item_id` and
  `blinded_candidate_id` back to contributing systems and ranks. **This file must never
  be distributed to annotators.**

---

## 3. Grading Rubric

For every item in `worksheets/reviewer_A_worksheet.csv` or `worksheets/reviewer_B_worksheet.csv`,
each human judge assigns two independent fields plus metadata:

### 3.1 Passage Relevance Grade (`relevance_grade` $\in \{0, 1, 2\}$)

| Grade | Label | Decision Rule |
|---:|---|---|
| **0** | **Irrelevant** | Passage does not address the query topic, is about an unrelated method/domain, or is an out-of-domain query (`Q39`–`Q50`) for which no corpus passage is relevant. |
| **1** | **Topical / Marginal** | Passage mentions the target concept or related mechanism in passing, provides peripheral context, or answers only a minor sub-part of the query. |
| **2** | **Directly Relevant** | Passage directly defines, explains, derives, or empirically answers the query with sufficient technical specificity to ground a response. |

### 3.2 Claim Support Grade (`claim_supported`)

| Value | Decision Rule |
|---|---|
| `FULLY_SUPPORTED` | Verbatim passage text directly and completely supports an authoritative answer to the query. |
| `PARTIALLY_SUPPORTED` | Passage supports part of the query (e.g., mentions one side of a comparison or one component of a mechanism) but omits key elements. |
| `UNSUPPORTED` | Passage contradicts or fails to substantiate the queried claim despite topical similarity. |
| `IRRELEVANT` | Passage is off-topic / spurious with respect to the query. |

### 3.3 Mandatory Annotator Metadata Columns

- `reviewer_id`: Named human identifier (e.g., `human_annotator_01`, mapped to a named
  researcher in the post-study provenance ledger; never an LLM or coding agent).
- `review_date`: ISO-8601 date (`YYYY-MM-DD`).
- `confidence`: `HIGH`, `MEDIUM`, or `LOW`.
- `notes`: Brief justification required whenever `confidence == LOW` or when grading edge cases.

> [!CAUTION]
> **Hard Prohibition:** Coding agents, LLMs, and heuristic scripts MUST NOT populate,
> prefill, or attribute any human grade column. Automated tests in
> `tests/unit/test_d5_eval_integrity.py` enforce that all 731 items remain `null`/empty
> until named human annotators return completed worksheets.

---

## 4. Reviewer Assignment & Independent Overlap Plan

1. **Annotator Recruitment & Qualification:**
   - Recruit **at least two (2) independent human annotators** (Reviewer A and Reviewer B)
     with graduate-level CS/ML/IR literacy who are **not** the primary system author
     (`Pratay Karali`).
   - Recruit **one (1) named human adjudicator** (Adjudicator C) to resolve disagreements.
2. **Calibration Phase (Non-Evaluative):**
   - Both annotators jointly practice on 5 queries from `queries_dev_15.json` (never from
     `queries_heldout_50.json`) to align on borderline `1` vs `2` distinctions.
3. **Independent Judging Phase:**
   - **Full-overlap design (recommended, $N=731$ items):** Both Reviewer A
     (`worksheets/reviewer_A_worksheet.csv`) and Reviewer B
     (`worksheets/reviewer_B_worksheet.csv`) independently judge all 731 pooled items.
   - **Minimum-overlap fallback (if annotator budget is constrained):** At least **20%**
     of queries (10 stratified queries: 4 core, 4 relational, 2 abstention; $\ge 145$ items)
     must be independently dual-coded by both Reviewer A and Reviewer B before single-coding
     the remaining queries in balanced 50/50 partitions.
   - Reviewers must not communicate about held-out items until both CSVs are locked and
     submitted with SHA-256 checksums.

---

## 5. Inter-Annotator Agreement (IAA) & Adjudication Procedure

Once both completed CSVs are submitted:

1. **Compute Agreement Before Adjudication:**
   - **Ordinal relevance (`relevance_grade` $\in \{0,1,2\}$):** Report exact percent agreement,
     unweighted Cohen's $\kappa$, **quadratic-weighted Cohen's $\kappa_w$**, and
     Krippendorff's $\alpha_{\text{ordinal}}$.
   - **Binary relevance ($\text{grade} \ge 1$ and $\text{grade} == 2$):** Report Cohen's $\kappa$.
   - **Claim support (4-class nominal):** Report unweighted Cohen's $\kappa$ and confusion matrix.
   - **Target reliability thresholds:** Quadratic-weighted $\kappa_w \ge 0.60$ (substantial)
     and Krippendorff's $\alpha \ge 0.67$ (tentative/acceptable); $\ge 0.80$ preferred.
     If $\kappa_w < 0.60$, halt metric reporting, revise rubric ambiguity on dev examples, and
     re-annotate before unlocking results.
2. **Adjudication (`worksheets/adjudication_worksheet.csv`):**
   - Every item where `reviewer_A_grade != reviewer_B_grade` (or claim-support differs) is
     copied into `adjudication_worksheet.csv` (still system-blinded!).
   - Adjudicator C reviews the query, verbatim passage text, and both reviewers' anonymized
     notes, then records `adjudicated_relevance_grade`, `adjudicated_claim_supported`,
     `adjudicator_id`, `adjudication_date`, and `adjudication_rationale`.
   - Final human qrels are frozen as `passage_qrels_human_v1.json` with SHA-256 checksum,
     separate from the legacy `passage_qrels.json` algorithmic qrels.
3. **Unblinding & Re-Evaluation:**
   - Only after `passage_qrels_human_v1.json` is SHA-256 locked, unblind via
     `worksheets/pool_key_SEALED.json` and recompute Experiment B metrics (MRR, nDCG@5,
     Recall@5, Precision@5) with paired bootstrap / randomization significance tests
     ($p < 0.05$, Bonferroni-corrected across baseline comparisons).

---

## 6. Explicit Provenance Ledger (Who Did What)

| Artifact / Activity | Performed By | Role / Independence | Status |
|---|---|---|---|
| 45 Graph Edges Audit (`human_review_records.json`, `reviewer_provenance.json`) | Pratay Karali | Primary Author (NOT independent) | Completed (40 verified, 5 quarantined) |
| 24-Citation Grounding Audit (`citation_grounding_audit.json`) | Pratay Karali | Primary Author (NOT independent) | Completed (7/24 fully supported, 9/24 spurious) |
| 445 Algorithmic Passage QRels (`passage_qrels.json`) | Keyword/doc-substring script | Algorithmic heuristic (NOT human) | Frozen & explicitly labeled `ALGORITHMIC_RULE_BASED_CANDIDATE` |
| System-Blinded Top-5 Pool & Worksheets (`build_blinded_pool.py`, 731 items) | Automated pooling script (Agent C) | Mechanical pooling only (0 grades filled) | Ready for human assignment; all grade fields `null`/empty |
| Independent Human Passage Relevance Judging (`reviewer_A/B_worksheet.csv`) | **PENDING (Named Humans TBD)** | Independent human annotators | **NOT STARTED (blocks Scientific GO)** |
| Disagreement Adjudication (`adjudication_worksheet.csv`) | **PENDING (Named Human TBD)** | Independent human adjudicator | **NOT STARTED** |

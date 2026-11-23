# ARCHIPELAGO — D7.1 Demonstration & Cross-System Reliability Gate Report

**Date:** 2026-11-23  
**Audit Version:** D7.1  
**Branch:** `redesign_research_workspace`  
**D5 Eval Source:** `research/d5_sigir_evaluation/d5_1_evaluation_results_v2.json`  
**Citation Audit Source:** `research/d5_sigir_evaluation/citation_grounding_audit.json`

---

## 1. Corrections Applied in D7.1

| Issue | Description | Status |
|-------|-------------|--------|
| ISS-01 | Probe runner: unexpected 401/403 is now FAIL, not auto-BLOCKED_BY_AUTH | FIXED |
| ISS-02 | Stale MRR 0.68 (2.6× BM25) claim removed from walkthrough | FIXED |
| ISS-03 | Stale 1.0 relationship accuracy with USES/CONTRASTS_WITH removed | FIXED |
| ISS-04 | "Independently reproducible" claim removed | FIXED |
| ISS-05 | Old `d5_evaluation_results.json` reference updated to `d5_1_evaluation_results_v2.json` | FIXED |
| ISS-06 | DEMO_SCENARIOS.md checklist `USES` edge claim fixed | FIXED |
| ISS-07 | Citation grounding: 9/24 spurious citations disclosed | DISCLOSED |
| ISS-08 | Authenticated browser flow BLOCKED (no test credentials available) | BLOCKED |
| ISS-09 | Stale Scenario 2 MRR values (0.5476/0.5750) updated to D5.1-v2 | FIXED |

---

## 2. Probe Evidence (D7.1 — Regenerated from Actual Runner)

**23 probes executed:** 14 PASS, 9 BLOCKED_BY_AUTH (gate confirmed), 0 FAIL, 0 UNVERIFIED.

**BLOCKED_BY_AUTH is NOT a functional PASS.** Nine guarded endpoints correctly reject
anonymous callers. The end-to-end authenticated workflows (chat, PDF reader, research
persistence, workbook export) cannot be verified by automated runner without valid
credentials.

Public/external endpoints verified as PASS:
- `/api/readiness`: system live, 610 concepts, 40 Pearson books
- `/chat` page redirect: live
- OpenAlex, Crossref, arXiv scholarly APIs: live with graceful degradation
- DOI resolution chain: live (302 → ACL Anthology)
- `/api/library/data` and `/api/library/koha`: snapshot with explicit `stale: true`
- Koha OPAC biblionumber 1868, 1910, search `q=algorithms`: live institutional
- Pearson eLibrary viewer origin: reachable
- Security: `/.env` and `/cache/*.sqlite3` blocked (404)

---

## 3. Accurate Scientific Metrics (from D5.1-v2)

### Concept Resolution (Experiment A, 38 supported queries)

| System | Accuracy | Hits |
|--------|----------|------|
| **Archipelago Resolver** | **68.4%** | **26/38** |
| BM25 Lexical | 42.1% | 16/38 |
| Snowflake Arctic Neural | 36.8% | 14/38 |
| Feature-Hashed Vector | 7.9% | 3/38 |

### Passage Retrieval (Experiment B, algorithmic qrels — not human-verified)

| System | MRR | nDCG@5 | R@5 |
|--------|-----|--------|-----|
| BM25 | 0.750 | 0.6415 | 0.3707 |
| Snowflake Arctic Neural | 0.750 | 0.6524 | 0.3324 |
| Graph-Assisted (heuristic) | 0.4865 | 0.2253 | 0.0597 |
| Feature-Hashed Vector | 0.2806 | 0.1764 | 0.1093 |

> [!IMPORTANT]
> Qrel provenance: `ALGORITHMIC_RULE_BASED_CANDIDATE`. No human relevance judgments
> have been completed. Passage retrieval metrics are provisional and cannot be presented
> as human-validated retrieval benchmarks.

### Relationship Prediction (D5.1-v2)

| Metric | Value |
|--------|-------|
| Precision over all surfaced triples | 0.0 |
| Recall over assessable queries | 0.0 |
| F1 | 0.0 |
| Runtime predicates | RELATED, REQUIRES, UNLOCKS |
| Absent predicates (USES, CONTRASTS_WITH, APPLIES_TO) | 13/18 relational queries affected |

> [!CAUTION]
> Do NOT claim typed relationship accuracy in the SIGIR submission. The runtime schema
> does not support USES or CONTRASTS_WITH. What is demonstrable: graph traversal from
> anchor concept via RELATED/REQUIRES/UNLOCKS, synthesized into grounded prose.

### Citation Grounding (5 queries, 24 citations, single annotator)

| Outcome | Count | Rate |
|---------|-------|------|
| Fully supported | 7 | 29.2% |
| Partially supported | 6 | 25.0% |
| Irrelevant or spurious | 9 | 37.5% |
| Unassessable | 1 | 4.2% |
| **Strict precision** | — | **0.29** |

---

## 4. Demonstration Script Accuracy (Corrected)

| Scenario | Query | Verdict | Evidence |
|----------|-------|---------|---------|
| S1 Turn 1 | `What is a Transformer?` | Demonstrable (anchors to `transformer`) | Concept resolver 68.4% acc on supported queries |
| S1 Turn 2 | `Self-attention and Transformers?` | Demonstrable (RELATED edge displayed) | RELATED/REQUIRES/UNLOCKS in runtime schema |
| S2 Turn 1 | `What is RAG?` | Demonstrable | Lewis 2020 citation |
| S2 Turn 2 | `DPR vs BM25?` | Demonstrable as grounded prose | No CONTRASTS_WITH edge; synthesis in text |
| S3 Turn 1 | `Spanner TrueTime?` | **Verified** (D5.3-A) | 0 citations, 0 graph edges, clean abstention |

**NOT demonstrable at the booth:** typed `USES` or `CONTRASTS_WITH` graph edges.
**NOT demonstrable at the booth:** claimed relationship-direction accuracy metric.

---

## 5. Remaining Defect Register

| ID | Issue | Severity | Status |
|----|-------|----------|--------|
| DEF-01 | Authenticated chat/PDF/workbook browser flow unverified | P1 | BLOCKED (no credentials) |
| DEF-02 | Citation grounding: 37.5% irrelevant/spurious | P1 | DISCLOSED — not tuned against held-out |
| DEF-03 | Passage qrels are algorithmic, not human-verified | P1 | DISCLOSED — labeled in all reports |
| DEF-04 | No independent annotation pass completed | P1 | DISCLOSED — single author annotator |
| DEF-05 | USES/CONTRASTS_WITH absent from runtime schema | P2 | DISCLOSED — demo scripts corrected |
| DEF-06 | Koha holdings are dated snapshot (2026-11-19) | P2 | DISCLOSED — `stale: true` in API |

---

## 6. Gate Verdicts

### 1. Local Engineering Integrity: **GO**
51/51 regression tests pass. Probe runner now correctly distinguishes BLOCKED_BY_AUTH
from PASS. Stale scientific claims removed from demonstration documents.

### 2. Hosted SIGIR Demo Readiness: **CONDITIONAL GO**
Public endpoints, abstention behavior, Koha OPAC, scholarly APIs, and Pearson
handoff are verified PASS. The demonstration is scientifically accurate for
Scenarios 1, 2, and 3 with corrected claim language. Auth-required workflows
(chat, PDF reader) are live per the auth-gate probes but require manual pre-demo
verification with valid credentials.

> [!WARNING]
> Do NOT claim MRR 0.68, 2.6× BM25, 1.0 relationship accuracy, or independent
> reproducibility at the SIGIR booth. Use the corrected D5.1-v2 metrics above.

### 3. Scientific Evaluation Readiness: **HOLD**
Passage qrels are algorithmic (not human-verified). Citation grounding has 29%
strict precision. Relationship prediction has 0.0 precision/recall/F1 on
relational queries. No independent annotation pass has been completed.

### 4. Campus Pilot Readiness: **HOLD**
Awaiting: live Koha ILS synchronization bridge, campus SSO/LDAP integration,
and local PDF cache deployment.

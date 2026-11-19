# S5-v3 Module E — Human Annotation Cost & Effort Forecast

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-benchmark-expansion`  
**Status:** PRE-ANNOTATION FORECAST — ARITHMETIC VERIFIED VIA PYTHON  
**Empirical Calibration Anchor:** Frozen S5-v2.1 pilot (`10` active queries: `7` answerable + `3` provisional negative controls; `6` frozen systems; depth `k = 10` union + `10` seed-only pairs = **`254` unique pairs**, i.e., `25.4` pairs/query; S5-C2 observed disagreement rate `51 / 254 = 20.08%`; S5-C2 negative-control search candidates `8 + 8 + 6 = 22` across `3` NC queries = `7.33` candidates/NC query).

> [!IMPORTANT]
> **Cost & Independence Rule:** Every hour below assumes **independent human annotators** operating under strict blinding (zero AI relevance suggestions, zero model-generated grades, zero prior-reviewer hints, mandatory verbatim supporting quotation for grades `1` and `2`). AI-assisted labeling is **never** counted as an independent human annotator (`faggioli2023perspectives`; S5-C2 governance rule).

---

## 1. Explicit Parameter & Calibration Assumptions

| Parameter | Central Estimate | Sensitivity Range | Calibration Basis |
|---|---:|---:|---|
| **Pooled systems (`S`)** | `8` systems (controls + v3 variants) | `6–10` systems | v2.1 had `6` systems (`24.4` retrieved + `1.0` seed = `25.4` pairs/query at `k = 10`). |
| **Unique pairs/query at `k = 5`** | **`18` pairs/query** | `15–22` pairs/query | `8 × 5 = 40` raw slots; ~40%–45% unique-to-slot ratio across diverse lexical/dense/hybrid/graph rankers + ~1–2 seed-only passages. |
| **Unique pairs/query at `k = 10`** | **`32` pairs/query** | `26–38` pairs/query | `8 × 10 = 80` raw slots; ~38%–40% unique-to-slot ratio calibrated from v2.1 (`24.4 / 60 = 40.7%`) + ~1–2 seed-only passages. |
| **Single-annotator grading pace** | **`90 sec/pair`** (`40` pairs/hr) | `60` (fast) – `120` (math/proof) sec/pair | Reading technical ML/math/NLP passage, assigning `0/1/2`, extracting exact verbatim quote for grades `1/2`, logging confidence & notes. |
| **Independent annotators per pair** | **`2`** (dual blind) | Fixed (`2`) | Required for inter-human reliability (`κ`, quadratic weighted `κ_w`; `cohen1968weighted`). |
| **Disagreement rate** | **`20.0%`** | `15%–25%` | Directly calibrated from S5-C2 observed disagreement rate (`51 / 254 = 20.08%`). |
| **Adjudication pace (3rd human)** | **`2.5 min/disagreement`** (`24`/hr) | `2.0–3.5` min/disagreement | Reviewing passage, query, and both blinded quotes/rationales to issue final grade. |
| **Negative-control (NC) verification** | **`0.50 hr / NC query`** (`30` min) | `0.33–0.75` hr / NC query | Independent human audit of ~10 top lexical/dense corpus candidates (`~2 min/candidate` + corpus-absence rationale logging; v2.1 averaged `7.33` candidates/NC query). |
| **Pre-freeze query verification (QV)** | **`0.10 hr / query`** (`6` min) | `0.08–0.15` hr / query | Human verification of candidate query premise, exact information need, page provenance, and single-passage shortcut check before freezing the benchmark. |
| **Illustrative hourly labor rate** | `$25/hr` (grad RA) – `$50/hr` (domain specialist) | Institutional / regional | Reported strictly as an illustrative budget range; person-hours are the primary invariant metric. |

---

## 2. Calibration Sanity Check on Frozen S5-v2.1 (`Q = 10`, `254` Pairs)

Applying the exact central-estimate formulas to the frozen S5-v2.1 pilot (`Q = 10`, `NC = 3`, `254` pairs):
- Single-annotator grading: `254 × 90 s / 3600 = 6.35 hr`
- Dual independent grading: `2 × 6.35 = 12.70 hr`
- Disagreement adjudication (`round(254 × 0.20) = 51` disagreements — exact match to S5-C2!): `51 × 2.5 / 60 = 2.12 hr`
- Negative-control verification (`3 × 0.50`): `1.50 hr`
- Pre-freeze query verification (`10 × 0.10`): `1.00 hr`
- **Total v2.1 equivalent effort:** **`17.32 person-hours`** (`$433–$866`).

---

## 3. Sensitivity Table: `40 / 48 / 60` Queries × Pool Depth `k = 5` vs. `k = 10`

All totals below are computed with exact arithmetic (`Total = Dual Grading + Adjudication + NC Verification + Query Verification`). Negative controls are scaled proportionally (~15%–17% of queries: `6` for `Q=40`, `8` for `Q=48`, `10` for `Q=60`).

| Queries (`Q`) | NC Queries | Pool Depth (`k`) | Est. Pairs / Query | Total Pairs | 1× Annotator (hr) | 2× Dual Annotators (hr) | Est. Disagreements (20%) | Adjudication (hr) | NC Verification (hr) | Query Verification (hr) | **Total Person-Hours** | Illustrative Cost (`$25–$50/hr`) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **40** | 6 | `k = 5` | 18 | 720 | 18.00 | 36.00 | 144 | 6.00 | 3.00 | 4.00 | **49.00 hr** | `$1,225 – $2,450` |
| **40** | 6 | `k = 10` | 32 | 1,280 | 32.00 | 64.00 | 256 | 10.67 | 3.00 | 4.00 | **81.67 hr** | `$2,042 – $4,083` |
| **48** *(target)* | 8 | `k = 5` | 18 | 864 | 21.60 | 43.20 | 173 | 7.21 | 4.00 | 4.80 | **59.21 hr** | `$1,480 – $2,960` |
| **48** *(target)* | 8 | `k = 10` | 32 | 1,536 | 38.40 | 76.80 | 307 | 12.79 | 4.00 | 4.80 | **98.39 hr** | `$2,460 – $4,920` |
| **60** | 10 | `k = 5` | 18 | 1,080 | 27.00 | 54.00 | 216 | 9.00 | 5.00 | 6.00 | **74.00 hr** | `$1,850 – $3,700` |
| **60** | 10 | `k = 10` | 32 | 1,920 | 48.00 | 96.00 | 384 | 16.00 | 5.00 | 6.00 | **123.00 hr** | `$3,075 – $6,150` |

### Key Tradeoff (`k = 5` vs. `k = 10` at Target `Q = 48`)
- Moving from `k = 10` (`1,536` pairs, `98.39 hr`) to `k = 5` (`864` pairs, `59.21 hr`) saves **`39.18 person-hours` (`39.8%` reduction)**.
- **Methodological consequence:** Complete pool coverage (`100%` judged, zero unjudged passages) is guaranteed **only up to the pooled cutoff `k`**. Therefore:
  - If budgeted for `k = 5`, primary metrics MUST be restricted to `@5` (`nDCG@5`, `Recall@5`, `Precision@5`, `MRR@5`), with `@10` either omitted or reported strictly with explicit unjudged-passage counts and `bpref` (`buckley2004retrieval`), never silent zero-imputation.
  - If `nDCG@10` / `Recall@10` are required as primary metrics (matching v2.1), **`k = 10` pooling (`~98.39 hr` at `Q = 48`)** is required.

---

## 4. Pacing Sensitivity for Target Configuration (`Q = 48`, `k = 10`, `1,536` Pairs)

Because Corpus v3 includes dense mathematical derivations (`mml-book.pdf`), technical NLP/decoding proofs (`arXiv:2307.09702v2`), and robotics control passages (`metatron-paper.pdf`), grading time per pair can vary substantially:

| Pacing Scenario | Sec / Pair | Pairs / Hr | 1× Annotator (hr) | 2× Dual Annotators (hr) | Adjudication (hr) | NC + Query Verify (hr) | **Total Person-Hours** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Fast** (experienced CS/ML reader) | `60 s` | 60 | 25.60 | 51.20 | 12.79 | 8.80 | **72.79 hr** |
| **Central** (standard technical grading + verbatim quote) | `90 s` | 40 | 38.40 | 76.80 | 12.79 | 8.80 | **98.39 hr** |
| **Careful** (math/derivation-heavy passages) | `120 s` | 30 | 51.20 | 102.40 | 12.79 | 8.80 | **123.99 hr** |

---

## 5. Phased Execution Option (Dev-First Budget Control)

To minimize wasted annotation effort before validating the query set and retrieval pipeline:
1. **Stage 1 — Pre-Freeze Query & NC Verification (`~8.80 hr` at `Q = 48`):** Human verification of all proposed queries, passage-necessity tags, and negative controls *before* pooling.
2. **Stage 2 — Dev Split Pooling & Dual Annotation:** Annotate the `dev` split first to measure empirical inter-annotator agreement (`κ`, `κ_w`), empirical pairs/query, and empirical grading pace; freeze all v3 retrieval hyperparameters strictly on `dev`.
3. **Stage 3 — Locked Test Split Pooling & Dual Annotation:** Freeze all system configs (SHA-256 locked), run test pooling once, and execute dual independent human annotation + adjudication on `test`.

---

## 6. Synced S5-v3 Exact Split & System Breakdown

Synced directly from `@corpus-v3` (`858` passages / `818` usable across `4` OA docs), `@benchmark-v3` (**`48` proposed queries**: `16` `dev` [`13` positive + `3` negative controls] and `32` `test` [`27` positive + `5` negative controls]), and `@retrieval-v3` (**`6` S5-v3 variants**, yielding `8–9` total pooled systems once `dense_snowflake_arctic_768d`, `hybrid_rrf_e2e`, and optional `cross-encoder/ms-marco-MiniLM-L-6-v2` are cached and added):

| Split | Queries (`Q`) | Positives | NC Queries | Pool Depth (`k`) | Est. Pairs | 2× Dual Annotators (hr) | Est. Disagreements (20%) | Adjudication (hr) | NC Verify (hr) | Query Verify (hr) | **Split Total (hr)** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`dev`** | `16` | `13` | `3` | `k = 5` | `288` | `14.40` | `58` | `2.42` | `1.50` | `1.60` | **`19.92 hr`** |
| **`test`** | `32` | `27` | `5` | `k = 5` | `576` | `28.80` | `115` | `4.79` | `2.50` | `3.20` | **`39.29 hr`** |
| **Combined (`k = 5`)** | **`48`** | **`40`** | **`8`** | **`k = 5`** | **`864`** | **`43.20`** | **`173`** | **`7.21`** | **`4.00`** | **`4.80`** | **`59.21 hr`** |
| **`dev`** | `16` | `13` | `3` | `k = 10` | `512` | `25.60` | `102` | `4.25` | `1.50` | `1.60` | **`32.95 hr`** |
| **`test`** | `32` | `27` | `5` | `k = 10` | `1,024` | `51.20` | `205` | `8.54` | `2.50` | `3.20` | **`65.44 hr`** |
| **Combined (`k = 10`)** | **`48`** | **`40`** | **`8`** | **`k = 10`** | **`1,536`** | **`76.80`** | **`307`** | **`12.79`** | **`4.00`** | **`4.80`** | **`98.39 hr`** |

*Arithmetic check:* `19.92 + 39.29 = 59.21 hr` (`k = 5`); `32.95 + 65.44 = 98.39 hr` (`k = 10`), matching §3 exactly.

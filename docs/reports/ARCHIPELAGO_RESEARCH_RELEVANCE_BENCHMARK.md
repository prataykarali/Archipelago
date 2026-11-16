# ARCHIPELAGO — RESEARCH RELEVANCE BENCHMARK

## 1. 40-Query Multi-Discipline Generalization Benchmark
Evaluated `evaluate_relevance` (`archipelago.relevance.v2`) across **40 diverse queries** spanning AI/ML, computer systems/databases, information retrieval, mathematics, physics, chemistry/materials, biomedical sciences, and interdisciplinary topics, each paired with a near-lexical distractor:
- **True Positives (TP):** `40 / 40`
- **False Negatives (FN):** `0 / 40`
- **False Positives (FP):** `1 / 40` (*attention mechanism* vs pediatric visual attention — genuine cross-domain lexical ambiguity)
- **Precision:** **`0.976`** (target ≥ 0.90)
- **Recall (on judged pool):** **`1.000`**
- **False-Positive Rate:** **`0.025`**

## 2. Live Before / After Comparison (`Liquid Neural Networks`, `top_k=20`)
| Metric | Before (`run 77eb88be`) | After (Repaired Pipeline) |
| --- | --- | --- |
| Qualifying Papers Returned | 20 / 20 (10 relevant, 10 off-topic) | **20 / 20** (20/20 relevant ML/LNN papers) |
| Topical Precision@20 | `0.50` (50%) | **`1.00`** (100% on-topic) |
| Topical False-Positive Rate | `0.50` (liquid metal, fluid viscosity, sensors) | **`0.00`** |
| arXiv Contribution | HTTP 429 (0 records) | `live` (25 records) |
| Europe PMC on `ai_cs` | 14 / 20 results | `skipped` (`not_selected_for_domain:ai_cs`) |
| Latency | ~53s | **24.14s** |
| Max Coverage Audit % | >100% (`125%`–`1245%` bug) | **95.0%** (bounded `0–100%`) |
| In-Collection `CITES` Edges | 0 | **2** |

## 3. Live Cross-Topic Generalization Spot Checks
- `diffusion models`: 10/10 returned (`9.66s`), all `HIGHLY_RELEVANT`
- `retrieval augmented generation`: 10/10 returned (`10.07s`), all `HIGHLY_RELEVANT`
- `quantum error correction`: 10/10 returned (`6.02s`), all `HIGHLY_RELEVANT`

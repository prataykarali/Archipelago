# Archipelago Benchmark Assumptions & Calibration Protocol

**Date:** September 2026  
**Status:** Calibration Standards Document  

---

## 1. Grounded Benchmark Targets vs Myths

### 1.1 KùzuDB Traversal Latency
- **Literature Myth:** *"KùzuDB traversal latency is below 5 ms."*
- **Empirical Reality:** Under sustained concurrent micro-benchmarking on `kuzu` 0.11.3 (multi-hop Cypher queries on 460 nodes / 1,832 edges), the actual distribution is:
  - Median (p50): **4.35 ms**
  - 95th Percentile (p95): **5.91 ms**
  - 99th Percentile (p99): **8.32 ms**
- **Production SLO Definition:** `Internal benchmark target: p95 < 5.0 ms under defined single-node workload`. This target is measurable via `scripts/benchmark_db.py`.

### 1.2 Embedding Similarity Cutoff Threshold
- **Literature Myth:** *"Cosine similarity $\ge 0.75$ using arctic-embed-m-v1.5 is the exact semantic boundary."*
- **Empirical Reality:** 0.75 is an empirical threshold subject to query length, domain vocabulary density, and tokenization behavior.
  - Short, precise acronym queries (e.g. "SVD") can produce cosine scores around 0.68–0.72 while being strongly in-domain.
  - Long queries containing conversational filler ("Can you give me a great overview of...") can score >0.76 on out-of-domain technical analogies.
- **Production Calibration Protocol:**
  - `SIMILARITY_THRESHOLD` is exposed as a configurable environment variable (default: `0.75`).
  - Calibrated via `scripts/calibrate_embedding_threshold.py` across 60+ labeled queries (in-domain, borderline, out-of-domain, adversarial, paraphrased).
  - Measures Precision, Recall, False Acceptance Rate (FAR), False Rejection Rate (FRR), and ROC-AUC.

### 1.3 Intent Router Evaluation
- **Benchmark Suite:** Evaluates 4 candidate strategies:
  1. Option A: Pure Regex & Keyword Heuristics
  2. Option B: Lightweight Scikit-Learn Classifier (TF-IDF / Linear SVM)
  3. Option C: Embedding Centroid Nearest-Neighbor Classifier
  4. Option D: Local Small Language Model (SLM) Zero-Shot
- **Metrics Evaluated:** Accuracy, Macro-F1, p50/p95 Latency (ms), CPU/RAM overhead, Adversarial Robustness.
- **Ground Truth:** Evaluated against `tests/fixtures/intent_eval.jsonl`.

### 1.4 Citation-Verifier Evaluation Standards
- **Evaluation Gate:** Gold standard test set of 100 atomic claims:
  - 40 Directly Supported
  - 20 Partially Supported
  - 20 Contradicted
  - 20 Unsupported
- **Gating Metric:** **False-Support Rate < 5.0%**. A verifier that falsely corroborates an ungrounded claim is a critical failure.

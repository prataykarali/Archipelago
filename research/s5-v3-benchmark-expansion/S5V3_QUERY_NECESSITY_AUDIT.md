# S5-v3 Module C — Query Necessity, Shortcut-Falsification & Premise Audit

**Date:** 2026-11-19  
**Manifest Audited:** [s5v3_query_benchmark_proposed.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/manifests/s5v3_query_benchmark_proposed.json)  
**Audit Status:** `AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION` (programmatic consistency checks passed with `0` errors; independent human verification remains mandatory before evaluation).

---

## 1. Necessity Audit Summary

| Query Class | Count | `multi_document_truly_necessary` | `shortcut_found` | Premise Audit Flags |
|---|---:|---:|---:|---:|
| `single_passage_fact_concept` | 12 | 0 | 12 (expected) | 0 |
| `technical_terminology_paraphrase` | 8 | 0 | 8 (expected) | 0 |
| `same_doc_multi_passage` | 10 | 0 | **0** | 0 |
| `cross_doc_multi_passage` | 10 | **10** | **0** | 0 |
| `negative_control` | 8 | 0 | **0** | 0 |
| **Total** | **48** | **10** | **20** | **0** |

Every multi-passage (`10` same-doc + `10` cross-doc) query was audited to verify that **no single passage** in Corpus v3 contains the complete answer (`shortcut_found: false`), and every `cross_doc_multi_passage` query spans **>= 2 distinct `source_doc_id`s** in `minimum_required_evidence_set`.

---

## 2. Cross-Document Multi-Passage Necessity Audit (10 Queries)

No query was forced into cross-document status. Each of the 10 cross-document queries pairs distinct, complementary technical content verified across two separate open-access sources:

| `query_id` | Split | Required `source_doc_id` Pair | Required Passage IDs & Pages | Why No Single Passage Suffices |
|---|---|---|---|---|
| `Q-S5V3-08` | `dev` | `local_oa_001` + `local_oa_003` | `..._001_p0001_c0018` (p.1), `..._003_p0304_c0532` (p.304) | D2L assumes fixed $\sigma$ to motivate squared loss; MML differentiates w.r.t. $\sigma^2$ to derive $\sigma^2_{\text{ML}}$. |
| `Q-S5V3-09` | `dev` | `local_oa_003` + `local_oa_002` | `..._003_p0191_c0320` (p.191), `..._002_p0004_c0005` (p.4) | MML defines marginal/conditional probability factorization; Willard & Louf applies boolean logit masking for discrete conditional LLM distributions. |
| `Q-S5V3-10` | `dev` | `local_oa_004` + `local_oa_003` | `..._004_p0011_c0038` (p.11), `..._003_p0309_c0543` (p.309) | METATRON deploys only the prior path (dropping the privileged posterior); MML uses the full posterior distribution for Bayesian prediction. |
| `Q-S5V3-32` | `test` | `local_oa_001` + `local_oa_003` | `..._001_p0001_c0005` (p.1), `..._003_p0308_c0541` (p.308) | D2L introduces unregularized squared loss; MML derives MAP / regularized least squares $\|\mathbf{y} - \boldsymbol{\Phi}\theta\|^2 + \lambda\|\theta\|_2^2$. |
| `Q-S5V3-33` | `test` | `local_oa_001` + `local_oa_003` | `..._001_p0001_c0009` (p.1), `..._003_p0237_c0407` (p.237) | D2L motivates minibatch SGD without momentum; MML derives the momentum update $\Delta x_i$ combining current and previous gradients. |
| `Q-S5V3-34` | `test` | `local_oa_001` + `local_oa_003` | `..._001_p0001_c0019` (p.1), `..._003_p0167_c0277` (p.167) | D2L frames linear regression as a single-layer neural network; MML generalizes to multi-layer backpropagation via the chain rule. |
| `Q-S5V3-35` | `test` | `local_oa_003` + `local_oa_004` | `..._003_p0077_c0118` (p.77), `..._004_p0003_c0009` (p.3) | MML defines the Euclidean $\ell_2$ norm; METATRON projects latent samples onto the unit sphere $z_t = \tilde{z}_t / \|\tilde{z}_t\|_2$. |
| `Q-S5V3-36` | `test` | `local_oa_002` + `local_oa_004` | `..._002_p0002_c0003` (p.2), `..._004_p0004_c0013` (p.4) | Willard & Louf enforces Python syntax via CFG/LALR(1) token masking; METATRON refines Python skill code via closed-loop simulation feedback. |
| `Q-S5V3-37` | `test` | `local_oa_001` + `local_oa_003` | `..._001_p0001_c0004` (p.1), `..._003_p0302_c0528` (p.302) | D2L presents raw-feature affine prediction $\hat{\mathbf{y}} = \mathbf{X}\mathbf{w} + b$; MML generalizes to nonlinear basis features $\phi^\top(x)\theta$. |
| `Q-S5V3-38` | `test` | `local_oa_003` + `local_oa_002` | `..._003_p0263_c0450` (p.263), `..._002_p0003_c0004` (p.3) | MML contrasts ERM point estimates vs probabilistic models; Willard & Louf formalizes an LLM as returning next-token logits $\alpha \in \mathbb{R}^N$. |

---

## 3. Same-Document Multi-Passage Necessity Audit (10 Queries)

| `query_id` | Split | `source_doc_id` | Required Passage IDs & Pages | Shortcut Falsification Rationale |
|---|---|---|---|---|
| `Q-S5V3-05` | `dev` | `local_oa_003` | `p0191_c0321` (p.191), `p0192_c0322` (p.192) | Prior role defined on p.191; marginal likelihood/evidence integral defined on p.192. |
| `Q-S5V3-06` | `dev` | `local_oa_003` | `p0111_c0180` (p.111), `p0112_c0182` (p.112) | Characteristic polynomial det/trace coefficients on p.111; Theorem 4.8 eigenvalue root equivalence on p.112. |
| `Q-S5V3-07` | `dev` | `local_oa_002` | `p0007_c0009` (p.7), `p0008_c0010` (p.8) | Algorithm 3 sub-sequence matching on p.7; Algorithm 4 state-to-vocabulary map construction on p.8. |
| `Q-S5V3-25` | `test` | `local_oa_001` | `p0001_c0011` (p.1), `p0001_c0013` (p.1) | Minibatch sampling/gradient averaging in c0011; global minimum vs deep network loss surfaces in c0013. |
| `Q-S5V3-26` | `test` | `local_oa_002` | `p0004_c0006` (p.4), `p0015_c0019` (p.15) | $O(N)$ naive partial-matching bottleneck on p.4; LALR(1) REDUCE sub-stack configurations on p.15. |
| `Q-S5V3-27` | `test` | `local_oa_003` | `p0328_c0579` (p.328), `p0340_c0602` (p.340) | Constrained variance Lagrangian on p.328; low-rank reconstruction error equivalence on p.340. |
| `Q-S5V3-28` | `test` | `local_oa_003` | `p0356_c0636` (p.356), `p0367_c0655` (p.367) | GMM convex-combination expressiveness on p.356; Dempster et al. EM parameter learning on p.367. |
| `Q-S5V3-29` | `test` | `local_oa_003` | `p0389_c0697` (p.389), `p0394_c0707` (p.394) | Primal-to-dual Lagrange multiplier transformation on p.389/391; nonlinear kernel substitution on p.394. |
| `Q-S5V3-30` | `test` | `local_oa_003` | `p0241_c0414` (p.241), `p0251_c0429` (p.251) | Min-max weak duality inequality on p.241; Legendre-Fenchel conjugate duality connection on p.251. |
| `Q-S5V3-31` | `test` | `local_oa_004` | `p0010_c0032` (p.10), `p0005_c0017` (p.5) | Three-stage separation in Appendix I (p.10); four-expert distillation and frozen runtime execution on p.5. |

---

## 4. Negative-Control Absence Audit (8 Queries)

All 8 negative controls (`3 dev`, `5 test`) were scanned programmatically across all `858` passages of `s5v3_corpus_passages.jsonl`:

| `query_id` | Split | Domain / Status | Target Topic | Corpus v3 Exact-Term Hits |
|---|---|---|---|---:|
| `Q-S5V3-14` | `dev` | Distributed Systems (`DEFERRED`) | Raft consensus term numbers & leader heartbeats | 0 (whole-word) |
| `Q-S5V3-15` | `dev` | Systems / Storage (Absent) | NVMe PCIe Gen5 Samsung 990 Pro / Linux `io_uring` | 0 |
| `Q-S5V3-16` | `dev` | Databases (`DEFERRED`) | PostgreSQL MVCC transaction IDs & snapshot isolation | 0 |
| `Q-S5V3-44` | `test` | Computer Networks (`DEFERRED`) | TCP BBR bottleneck bandwidth & round-trip propagation | 0 (whole-word) |
| `Q-S5V3-45` | `test` | ML Systems (Absent) | FlashAttention-2 GPU SRAM/HBM block tiling | 0 |
| `Q-S5V3-46` | `test` | Robotics (Absent) | Boston Dynamics electric Atlas knee peak torque | 0 |
| `Q-S5V3-47` | `test` | Operating Systems (`DEFERRED`) | Linux CFS red-black tree virtual runtime scheduling | 0 |
| `Q-S5V3-48` | `test` | LLM Serving (Absent) | vLLM PagedAttention Mixtral-8x7B on NVIDIA B200 | 0 |

---

## 5. Human-Verification Protocol Requirements (Next Gate)

Before any subset of these 48 proposed queries is promoted from `AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION` to an evaluated benchmark:

1. **Answerability Verification:** Independent human assessors must inspect the cited Corpus v3 passages and confirm `answer_exists_in_eligible_corpus` (upgrading from `CANDIDATE_UNVERIFIED_REQUIRES_HUMAN_AUDIT`).
2. **Shortcut Falsification Check:** For all 20 multi-passage queries (`10` same-doc, `10` cross-doc), human reviewers must verify that no single passage retrieved by baseline systems suffices to answer the exact information need.
3. **Negative-Control Verification:** Independent human verifiers must inspect top-ranked candidate passages retrieved by all competing systems on the 8 negative controls to confirm true unanswerability (following the S5-C3 negative-control protocol).

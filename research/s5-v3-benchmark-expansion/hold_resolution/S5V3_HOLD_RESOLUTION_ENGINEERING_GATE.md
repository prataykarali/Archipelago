# S5-v3 hold resolution engineering gate

**Date:** 2026-11-19  
**Base:** `7f3a01ab81bfdd47972d514a82cc59d35ac195cd`  
**Decision:** **HOLD** for research execution; engineering and query-audit handoff is ready.

## 1. Recovery and independence

Search covered the canonical repository, Desktop, Downloads, Documents, Codex worktrees, local Trash, and mounted `/media` and `/mnt` trees. This is a local search, not proof that no external backup exists. The expected identities come from `reports/s5v3_module_a_inventory.json` and the frozen S5 records.

| Artifact | Result | Evidence |
|---|---|---|
| Original v2.1 `okf_graph.db` | **MISSING** | The only name match was a 16,384-byte empty Kùzu database in the `archipelago-library-release` worktree; SHA-256 `03781cdcc1184786b660a78d973dd2dece9204ec94b41fa87254a7042902fd4c`, unequal to recorded corpus hashes `fc0d0c7e...` and `6435bf44...`. It has no `Chunk` table. |
| v2.1 dense cache `s5a_dense_embeddings_713.npy` | **MISSING** | No matching file in searched locations; the new v3 model weights below are not this historical cache. |
| Original Reviewer A `reviewer_a_s5b2_1_workbook.md` | **MISSING** | No matching file; recorded SHA-256 `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` cannot be verified without bytes. |

No replacement was synthesized. **V3 can run independently** on its own SHA-locked passage JSONL and corpus-scoped graph adapter. It cannot claim byte-identical v2.1 reproduction, original Reviewer A comparison, or parity with the missing historical dense cache. The existing `okf_graph.json` contains concepts and edges, not the missing original passage collection.

Preservation check: the frozen S5-D0 manifest names 10 tracked files with explicit expected digests and 9 additional tracked files recorded as unchanged without expected digests. The 10 digest-bearing files still match; Git reports no working-tree changes in the other 9. This supports preservation, but does not turn the 9 files into hash-verified artifacts.

## 2. Corpus audit and scope decision

All four local source bytes match the recorded SHA-256 digests. The private corpus JSONL matches `dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4`.

| Document | SHA-256 prefix | Total | Eligible (`is_usable`) | Flagged and eligible | Flagged and excluded | Rights status |
|---|---|---:|---:|---:|---:|---|
| D2L Ch. 3, `local_oa_001` | `39990e29` | 27 | 26 | 1 | 1 | CC BY-SA 4.0; attribution/share-alike |
| Willard & Louf, `local_oa_002` | `8888aa20` | 24 | 23 | 16 | 1 | arXiv perpetual nonexclusive; local research, no blanket republication claim |
| MML book, `local_oa_003` | `3f87b70c` | 757 | 719 | 67 | 38 | Free-to-read PDF; local research, redistribution unverified |
| METATRON, `local_oa_004` | `de2411a2` | 50 | 50 | 14 | 0 | Preprint; local research, redistribution unverified |
| **Total** | | **858** | **818** | **98** | **40** | |

The 138 flagged passages comprise **98 eligible + 40 excluded**. The 818 eligible comprise **720 unflagged + 98 flagged**. All three exact-duplicate records are among the 40 excluded; one near-duplicate pair remains an audit concern. Eligibility is exactly `is_usable=true` in the SHA-locked private JSONL; a quality flag alone is not an exclusion rule. Moderate math extraction noise and sentence truncation remain in the 98 flagged eligible passages and need human readability review for any cited evidence. Eleven proposed queries cite at least one flagged passage.

The four-document scope is defensible only as a **narrow ML/math/NLP/robotics feasibility study**, with no OS, database, network, or distributed-systems generalization. It is unbalanced: MML contributes 719/818 eligible passages (87.9%) and 23/48 proposed questions. A broader CS claim needs a corpus expansion **before query approval and pooling**, plus balanced per-document sampling or stratified reporting.

**Smallest proposed broader scope:** retain these four sources and add one version-pinned, rights-verified source per missing domain, for eight sources total. Candidate primary sources and rights evidence:

| Domain | Candidate | License/provenance evidence | Boundary |
|---|---|---|---|
| Operating Systems | [MIT PDOS xv6 RISC-V book](https://github.com/mit-pdos/xv6-riscv-book) | [Book LICENSE](https://github.com/mit-pdos/xv6-riscv-book/blob/xv6-riscv/LICENSE) grants use, copy, modification, and distribution with notice. | Covers OS mechanisms through xv6, not all OS research. |
| Databases | [PostgreSQL versioned manual](https://www.postgresql.org/docs/17/) | [Official PostgreSQL license](https://www.postgresql.org/about/licence/) explicitly covers documentation; pin version and a bounded section set. | Vendor-specific DBMS concepts; avoid a general database-theory claim. |
| Networks | [Computer Networks: A Systems Approach source](https://github.com/SystemsApproach/book) | [Publisher/author repository README](https://github.com/SystemsApproach/book/blob/master/README.rst) states CC BY 4.0 and required attribution. | Pin a commit because the open book changes. |
| Distributed Systems | [Cambridge distributed-systems lecture notes](https://github.com/ept/dist-sys) | Author repository states CC BY-SA; verify exact license file/version and notice before any ingest. | Course notes, not a substitute for a broad research corpus. |

These are **candidates, not ingested sources**. Their exact source revision, downloaded-byte hash, extraction quality, passage count, and query coverage remain unverified. OSTEP is free to read but its redistribution license was not established here, so it is not the default ingest candidate.

## 3. Model readiness

The essential neural dependency for the planned v3 dense and hybrid controls is [Snowflake/snowflake-arctic-embed-m-v1.5](https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v1.5), Apache 2.0. It was downloaded only from the official model repository at exact revision `e58a8f756156a1293d763f17e3aae643474e9b8a`; the local 417 MiB snapshot and every file SHA-256 are recorded in `s5v3_essential_model_pin.json`. The principal `model.safetensors` SHA-256 is `463d27a3e88a748997316367c419bbdab4d809300a5f24b9b19ba9b2dc08ffdd`.

Hardware observed: 15 GiB RAM (6.7 GiB available), RTX 2050 with 4 GiB VRAM (3,758 MiB free), and 17 GiB free disk. A **CPU-only**, offline local-load smoke test encoded two generic, non-benchmark sentences into finite, unit-normalized `(2, 768)` embeddings. No proposed test question or provisional label was used. A full-corpus dense cache and controlled GPU throughput test remain future pre-pooling work. BM25 and v3 graph code require no model weights. [MiniLM-L6 cross-encoder](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) is Apache 2.0, about 90 MiB, and hardware-feasible but **optional and not downloaded**. [BGE reranker base](https://huggingface.co/BAAI/bge-reranker-base) is MIT licensed, about 1.1 GiB, and feasible only with careful memory settings; [BGE reranker v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) is Apache 2.0, about 2.3 GiB, and high risk on 4 GiB VRAM. Neither BGE model was downloaded. Any optional reranker must be declared before pool construction if it will enter the evaluation.

## 4. Human query audit and feasibility

The private blinded investigator workbook is at `data/annotation_local/s5v3/query_audit/s5v3_query_audit_workbook.xlsx`, with matching JSON, CSV, and evidence-excerpt Markdown in that Git-ignored directory. It has 48 unique AI-proposed queries in shuffled order, exact questions, evidence document/passage IDs, proposed category, claimed necessity, shortcut rationale, provenance concerns, and blank decision/correction cells. The workbook omits dev/test split, graph-anchor regime, and relevance grades. The metadata-only public template and schema are in this directory. **Zero queries are human-validated.** Eight proposed negative controls have no cited positive evidence and require independent corpus-absence checks.

Benchmark concerns: only 27 proposed answerable test questions; 10 same-document and 10 cross-document necessity claims remain unverified; 20 proposed single-passage/paraphrase questions explicitly have a shortcut; 11 questions cite flagged evidence; the corpus and query distribution are concentrated in MML. Human review must check exact source text, premise, passage readability, whether one passage suffices, category, and negative-control answer absence. Rejected or revised questions need a fresh manifest and split audit before any freeze.

For 48 approved queries, the current **forecast**, not measured labor, is ~8.8 person-hours for query/negative-control verification, then ~59.21 person-hours total for depth-5 dual annotation or ~98.39 for depth-10, including verification and adjudication. These estimates change if the corpus or queries change. Two independent human graders, a separate disagreement adjudicator, source-rights/provenance review, and investigator sign-off are still missing. No relevance grades, full pools, D1 run, or effectiveness claims were produced.

## 5. Gate

**HOLD** on S5-v3 research execution. The v3 engineering substrate and blinded query-audit handoff are usable independently of the missing v2.1 database, but corpus scope and human query validity remain unresolved. The next human decision is to choose the narrow four-document claim or authorize the eight-source minimum expansion, then review all 48 queries against that fixed scope. Only after source provenance, query approval, model/system list, and independent annotation protocol are fixed should full pooling or relevance annotation begin.

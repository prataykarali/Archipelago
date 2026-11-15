# Archipelago — Final Integration, Security Hardening & UX Acceptance Report

**Repository:** `prataykarali/Archipelago`  
**Branch:** `fix/s6-security-chat-ux`  
**Starting Commit:** `c22c4d0cae44f641c3ef86e3fe42a694c1e25c5f`  
**Updated Branch Head:** includes `d3698b4` (`host_research/app.py` CSP fix) and local `route_logic.py` book/paper matching refinements

---

## 1. Deployed Applications, SHAs & Deployment IDs

| Application | Team / Project | Production URL | Deployment ID | Deployment URL | Git Commit |
| --- | --- | --- | --- | --- | --- |
| **Main Academic Inference** (`host_inference/`) | `archipelago-6383/archipelago` | `https://archipelago-blond.vercel.app` | `frdxPZNNvi1jXR547ZpShmd66LR6` | `https://archipelago-qboeqpr66-archipelago-6383.vercel.app` | `b396a04` |
| **Librarian & Research** (`host_research/`) | `shinaura/archipelago-librarian` | `https://archipelago-librarian.vercel.app` | `dpl_BbyKC3wUc3zTHvqXD8rkABGXrhdc` | `https://archipelago-librarian-r9u8x6wax-shinaura.vercel.app` | `d3698b4` |

---

## 2. Real-Browser Screenshots (Desktop `1440x960` & Mobile `390x844`)

Captured via Playwright + Chromium against live production deployments with authenticated Supabase sessions:
- **Librarian Dashboard (Desktop):** `prod_screenshots/prod_librarian_desktop_1440x960.png`
- **Librarian Dashboard (Mobile):** `prod_screenshots/prod_librarian_mobile_390x844.png`
- **Knowledge Graph (Desktop):** `prod_screenshots/prod_graph_desktop_1440x960.png`
- **Knowledge Graph (Mobile):** `prod_screenshots/prod_graph_mobile_390x844.png`
- **Student Chat — Hessian KaTeX (Desktop):** `prod_screenshots/prod_chat_q4_hessian.png`
- **Student Chat — Neural Network Diagnostic (Desktop):** `prod_screenshots/prod_chat_q7_quiz_nn.png`
- **Student Chat — Hessian Quiz Honest Refusal (Desktop):** `prod_screenshots/prod_chat_q8_quiz_hessian.png`

---

## 3. Live Student Chat Verification (`https://archipelago-blond.vercel.app/chat`)

Tested in Playwright with an authenticated student account (`s6-demo-student@example.com`):

| Query | Status | Answer & Citations | Graph / Quiz / KaTeX | Assessment |
| --- | --- | --- | --- | --- |
| `What is AGI?` | **PASS** | `GENERAL_EXPLANATION` (1,332 chars); accurate foundational explanation, no fabricated citations. | No irrelevant graph or quiz. | Functional |
| `What are the e-resources?` | **PASS** | Lists 40 Pearson eBooks (`https://ebooks.elibrary.in.pearson.com/`), 51 HF Cloud Reader titles, 109 Koha holdings & 1,212 journal issues (`https://uemk-opac.l2c2.co.in/`). Explicitly notes external IEEE/ACM/Springer/Scopus access is unverified. | `hide_graph: true` | Functional |
| `Show me available neural-network books.` | **DEGRADED (Live) / FIXED (Local)** | Live deployment (`b396a04`) missed adjective-before-noun regex and returned `"I cannot provide a list of available neural network books..."` with paper links (`Ho2020_DDPM.pdf`, `Krizhevsky2012_AlexNet.pdf`). Local `route_logic.py` update now matches **Neural Networks and Learning Machines** (Haykin) via `LIBRARY_LOOKUP`. | No graph | Degraded in live `b396a04` (main deployment frozen per constraint) |
| `Explain the Hessian matrix.` | **PASS** | Accurate mathematical definition from general foundational knowledge; no fabricated local textbook citations. | **2 KaTeX `.katex` elements** rendered (`H`, `f: R^n -> R`); zero CSP errors. | Functional |
| `Explain backpropagation and show its concept graph.` | **DEGRADED** | In Playwright sequential run, timed/aborted (`AbortError: BodyStreamBuffer was aborted` when previous stream/rate-limit overlapped). Locally returns `MULTI_CONCEPT` (`Error Backpropagation Algorithm` + pseudo-concept `"show its concept graph"`). | Graph rendering in live multi-turn sequence not cleanly verified. | Degraded |
| `Show papers about KV caching.` | **PASS (minor dup in live)** | Returned `Kwon2023 vLLM` with working `/open/Kwon2023_vLLM.pdf?page=1` link; live `b396a04` listed both `Kwon2023_vLLM.pdf` and `books/papers/Kwon2023_vLLM.pdf` (deduplicated by basename in local `route_logic.py`). | `hide_graph: true` | Functional |
| `Quiz me on neural networks.` | **PASS** | Returned diagnostic checkpoint for `Neural Network` with `Yes, Start Diagnostic` trigger and `Bahdanau2014_Attention.pdf#page=10`. | Diagnostic UI ready | Functional |
| `Quiz me on the Hessian matrix.` | **PASS** | Honestly refused: `"library has not indexed a concept node for it yet, so I cannot ground a lesson or roadmap in retrieved text."` No fuzzy fallback to `2d_discrete_convolution`. | No unrelated quiz | Functional |
| `Give me a verified source page about virtual memory.` | **DEGRADED** | Returned accurate definition of virtual memory from `okf_graph.json`, but **0 source page links** (`links: []`) because synthetic `textbooks/*.pdf` references are quarantined and no replacement reader PDF page is linked for `virtual_memory`. | No page link | Intentionally quarantined / degraded |

**Console / Streaming Notes:** Zero CSP violations on `archipelago-blond.vercel.app`. One `404` resource warning and one `AbortError: BodyStreamBuffer was aborted` occurred during rapid sequential Playwright submits; `/api/chat` also enforces per-user rate limiting (`429` after 10 rapid requests).

---

## 4. Librarian Dashboard & Graph UX Verification (`https://archipelago-librarian.vercel.app`)

Tested in Playwright (`1440x960` desktop and `390x844` mobile) with `librarian@librarian.iem.archipelago.invalid`:

- **RBAC:** `GET /api/librarian/catalog` returned `200` for `librarian` and `401` for `student` (`s6-demo-student@example.com`).
- **CSP Fix Verified:** Real-browser testing caught a hostname typo (`spllaastefjwclllfndp` -> `spllaastejfwclllfndp`) in `host_research/app.py` `connect-src`. Fixed in `d3698b4` and redeployed (`dpl_BbyKC3wUc3zTHvqXD8rkABGXrhdc`); authenticated `/librarian` and `/academic/graph` now load with zero CSP errors.
- **`/librarian` Dashboard:**
  - Zero horizontal overflow on desktop and mobile (`scrollWidth <= innerWidth`).
  - `#traffic-body` stays hidden (`traffic_hidden: true`) when live gate/QR telemetry is not connected.
  - Progressive disclosure drawer (`secondary-drawer`) collapses Circulation, Orders, Fine notes, Research Discovery, and Official OPAC links cleanly.
  - **KPI Limitation:** The 4 overview KPI cards (`#metric-pearson`, `#metric-hf`, `#metric-koha`, `#metric-reviews`) render `—` because live `/api/analytics/summary` currently returns only `physical_footfall` / `occupancy` fields rather than catalog counts.
- **`/academic/graph`:**
  - `.graph-toolbar` sits cleanly above `#graph` (`toolbar_no_overlap: true`) on both desktop and mobile.
  - `#advanced-filters` is collapsed by default (`adv_collapsed_default: true`), and `#clear-filters` restores `"Showing 12 nodes · 24 edges"` (desktop) / `"Showing 6 nodes · 8 edges"` (mobile).
  - **Domain Filter Limitation:** `#domain-filter` renders only `"All domains"` (`domain_options: 1`) on live `/api/graph/hubs` because hub node payloads do not currently include a `domain` property (verified working with 4 domains when `domain` is present in node payloads).

---

## 5. Semantic-Routing Generalization Results (Task 3)

Live `/api/chat` hit `429` rate limits after `U1`; therefore unseen paraphrases were evaluated locally against `host_inference/engine/Engine`:

| ID | Unseen Query | Route | Outcome |
| --- | --- | --- | --- |
| `U1_KV_PARAPHRASE` | `How do GPUs share KV memory across concurrent LLM requests?` | `GENERAL_EXPLANATION` | Recognizes GPU/KV/LLM terms; does not surface `Kwon2023_vLLM.pdf` without `"papers"` cue. |
| `U2_PAGING_COMPARE` | `Compare virtual memory paging in operating systems with PagedAttention.` | `CROSS_DOMAIN` | **PASS** — comparative matrix `Virtual Memory × PagedAttention`. |
| `U3_JACOBIAN` | `Explain the Jacobian matrix and its mathematical definition.` | `GENERAL_EXPLANATION` | **PASS** — routes to general academic explanation. |
| `U4_READ_ONLINE` | `Where can students read engineering textbooks online?` | `GENERAL_EXPLANATION` | **GAP** — missed `_INSTITUTIONAL_ERESOURCE_RE` (expected `LIBRARY_LOOKUP`). |
| `U5_SILBERSCHATZ` | `Do you hold Silberschatz Operating System Concepts?` | `GENERAL_EXPLANATION` | **GAP** — `"Do you hold ..."` missed `_CATALOG_AVAILABILITY_RE` (expected `CATALOG_SHELF_ROUTING`). |
| `U6_LORA_PAPERS` | `Find scholarly articles on LoRA fine-tuning.` | `RESEARCH_TOPIC` | **PASS** — matched `Dettmers2023_QLoRA.pdf` and `Hu2021_LoRA.pdf`. |
| `U7_BLOOM_FILTER` | `What is a Bloom filter?` | `GUARDRAIL_INTERCEPT` | **GAP** — out-of-vocabulary for `ACADEMIC_DOMAIN_RE` and unindexed in `okf_graph.json`. |
| `U8_GRADIENT_DESCENT` | `Explain stochastic gradient descent.` | `GRAPH_SYNTHESIS` | **PASS** — matched `Stochastic Gradient Descent` node. |

**Assessment:** Routing relies on regex intent/domain gates (`ACADEMIC_DOMAIN_RE`, `_BOOK_ABOUT_RE`, `_INSTITUTIONAL_ERESOURCE_RE`) paired with graph phrase/embedding lookup. While indexed concepts and comparative queries generalize well, unindexed academic topics outside `ACADEMIC_DOMAIN_RE` (e.g., `Bloom filter`) and unseen library phrasings (`"Do you hold ..."`, `"read textbooks online"`) still fall through.

---

## 6. Outstanding Security Verification Summary (Task 4)

- **Code-Level Fixes Verified Live:** Both `host_research` CSP (`dpl_BbyKC3wUc3zTHvqXD8rkABGXrhdc`) and `host_inference` CSP + KaTeX sanitization (`frdxPZNNvi1jXR547ZpShmd66LR6`) are active in production.
- **Supabase Read-Only Audit (`spllaastejfwclllfndp`):**
  - All **15** `public` tables have `rowsecurity = true`.
  - **3** tables (`credential_import_audits`, `credential_import_permissions`, `profiles`) have explicit `SELECT` policies; **26** tables across `public` (12) and `research_intelligence` (14) have RLS enabled with zero permissive policies (backend `service_role` only).
  - **Advisor Warning:** `auth_leaked_password_protection` (HaveIBeenPwned check) is disabled in Supabase Auth settings (left unchanged per read-only constraint).
- **Dependencies & Vercel Settings:** `requirements.txt` files checked; `pip_audit` is not installed in the local Python environment so automated CVE scanning of transitive wheels remains unverified.

---

## 7. Remaining Limitations

1. **Main App Freeze:** The `Q3_NN_BOOKS` regex fix and paper deduplication in `host_inference/engine/route_logic.py` are committed locally on `fix/s6-security-chat-ux` but not redeployed to `archipelago-6383` (`Do not modify the main application's deployment`).
2. **Virtual Memory Source Page:** Quarantining synthetic `textbooks/*.pdf` links leaves `virtual_memory` without a verified reader page until an authorized OS textbook PDF is indexed.
3. **Librarian Overview KPIs & Graph Domains:** `/api/analytics/summary` does not yet emit catalog counts and `/api/graph/hubs` does not yet emit `domain` fields, so overview KPIs show `—` and the domain dropdown shows `All domains` only.
4. **Rate Limiting & Rapid Multi-Turn Streaming:** Rapid consecutive queries on `/api/chat` trigger `429` rate limits and `AbortError` if a new query is submitted before the prior stream completes.

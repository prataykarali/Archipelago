# D14 Tooling Evaluation & Five-Repository Integration Plan

**Owner:** `d14-tooling-scout`  
**Phase:** D14.0 (Read-Only Evaluation & Proposal — No Repo Root Configs or Production Code Modified)  
**Date:** 2026-11-28  
**Target Integration Branch (Post-Approval):** `sigir/d14-recovery` (based off `sigir/d12-recovery` `fe8887c8`)  
**Protected Boundaries Respected:** Zero edits to production code, UEM institutional production (`archipelago-blond.vercel.app`), or `/home/pratay-karali/Desktop/sigit_manu*`.

---

## 1. Executive Summary & Verdicts

All five repositories were inspected via shallow read-only clones in an isolated scratch directory (no install scripts executed, no global packages installed).

| # | Repository | License | Verdict | Primary Archipelago D14 Role |
|---|---|---|---|---|
| 1 | **Ponytail 5** (`DietrichGebert/ponytail`) | **MIT** | `ADOPT_AS_SKILL` | Enforce concise diffs, reuse-first ladder, grep-all-callers bugfixes, and mandatory tests for risky logic alongside `AGENTS.md` |
| 2 | **unslop** (`heydamir/unslop`) | **CC BY 4.0** (attribution required) | `ADOPT_AS_SKILL` (Polish Mode) | Strip AI-slop chrome from `/chat` 3D UI & Inspector (`d14-ux-followups`, D14.6) while preserving restored Archipelago identity & UI mirror invariant |
| 3 | **Elephant-Goldfish Model (EGM)** (`google/elephant-goldfish-model`) | **Apache-2.0** | `ADOPT_WORKFLOW_PATTERN` | Operationalize zero-context Goldfish spec/diff review via `d14-independent-verifier` before `d14-integrator` merges |
| 4 | **Agent Reach** (`Panniantong/Agent-Reach`) | **MIT** | `DEFER` (for D14.1 ingestion) | Not recommended for D14.1 OER corpus ingestion (use canonical open APIs instead); optional `public-web`/`github`-only CLI fallback if ever needed |
| 5 | **Claude Code Setup** (`anthropics/claude-plugins-official/plugins/claude-code-setup`) | **Apache-2.0** | `ADOPT_WORKFLOW_PATTERN` | Periodic read-only automation audit (executed below for Archipelago; surfaces top 1–2 automations/category and trims 72-skill GSD clutter) |

---

## 2. Detailed Repository Evaluations

### 2.1 Ponytail 5 (`https://github.com/DietrichGebert/ponytail`)

- **Verdict:** `ADOPT_AS_SKILL` (adopt `SKILL.md` + `ponytail-review/SKILL.md` as project-local Antigravity skills; skip Claude-Code-only `band` UI and Node lifecycle hooks).
- **License:** MIT (`Copyright (c) 2026 DietrichGebert`). Permissive; safe for adaptation with license header preserved.
- **Architecture & Dependencies:**
  - Core prompt lives in `skills/ponytail/SKILL.md` (52 lines) and compact ruleset in `.agents/rules/ponytail.md` (30 lines).
  - Companion skills: `ponytail-review` (reads diff + all callers, ranks `Must fix / Should fix / Nice to have`, requires concrete failure cases), `ponytail-audit` (whole-repo triage), `ponytail-debt` (harvests `shortcut:` comments).
  - Optional Node hooks (`hooks/ponytail-activate.js`, `hooks/claude-codex-hooks.json`) and Claude Code status band (`hooks/band/`) are host-specific and unnecessary in Antigravity.
- **Security Posture:** Clean. Inspected `hooks/` and `skills/`; no telemetry, no remote network calls, no binaries. Adopting only the pure-Markdown skills carries zero runtime attack surface.
- **Mapping to Archipelago D14 (`AGENTS.md` Complement):**
  - `AGENTS.md` enforces `<=500` lines/file, downward-only imports, no magic numbers, and `scripts/quality_gate.py`.
  - Ponytail fills the behavioral gap *before* code is written:
    1. **6-rung reuse ladder** ("already in codebase -> stdlib -> installed dep -> minimum code") stops D14 workers from adding speculative abstractions or duplicate helpers.
    2. **Bugfix caller-grep rule** ("grep every caller before editing, fix root cause once") directly prevents the D13 regressions where one route was patched while sibling callers or `ui/chat/` mirrors drifted.
    3. **Risky-logic test invariant** ("every new branch, loop, parser, security check, or bug fix leaves at least one small test") reinforces Skill 2 without boilerplate coverage padding.
    4. **Explicit non-negotiables**: Ponytail explicitly forbids cutting trust-boundary validation, data-loss error handling, security, or accessibility—matching `AGENTS.md` Skill 1 & Skill 4.
    5. **`/ponytail-review` format** gives `d14-integrator` a crisp, concrete pre-merge check (`What this is / Problem / Fix / If we skip it`).
- **Draft Proposal:** [`docs/reports/d14/tooling_proposals/archipelago-ponytail-SKILL.md`](tooling_proposals/archipelago-ponytail-SKILL.md)

---

### 2.2 unslop (`https://github.com/heydamir/unslop`)

- **Verdict:** `ADOPT_AS_SKILL` — specifically in **Light Slop / Polish Mode** for D14.6 (`d14-ux-followups`).
- **License:** **CC BY 4.0** (Damir Sokolovsky, `@heydamir`, `https://github.com/heydamir/unslop`). **Mandatory requirement:** retain attribution to Damir Sokolovsky (`@heydamir`) and link back to the repo in any copied or adapted skill file.
- **Architecture & Dependencies:**
  - Pure Markdown skill (`skills/unslop/SKILL.md`, 236 lines) + reference rubrics (`references/signs.md`, `tokens.md`, `visuals.md`, `effects.md`, `rtl.md`).
  - Optional Node scripts (`scripts/snapshot.mjs`, `scripts/story.mjs`) require `playwright` + `ffmpeg` only if snapshotting live URLs or rendering promo videos. Neither is required for auditing local Archipelago UI files.
- **Security Posture:** Clean. Pure Markdown instructions; local Playwright script only runs if explicitly invoked. Disable its optional paid image-generation MCP prompts—academic app dashboards should not generate decorative hero images.
- **Concrete Audit Findings on Archipelago `/chat` UI (`host_inference/ui/index.html`):**
  A read-only scan of `host_inference/ui/index.html` immediately surfaced textbook `unslop` tells that D14.6 (`d14-ux-followups`) can fix **without** redesigning or losing Archipelago's restored identity:
  1. **Blurred multi-hue background blobs (L124–126):** `bg-accentPurple`, `bg-accentPink`, `bg-accentCyan` with `blur-[120px] animate-blob` — classic AI-slop filler + continuous GPU/CPU animation overhead.
  2. **Hue gradients + neon glows + `transition-all` on chrome (L222, L555, L638, L655):** `from-accentPink/25 to-accentPurple/25`, `hover:shadow-[0_0_24px_rgba(236,72,153,0.35)]`, `from-accentPurple to-indigo-600`, and `transition-all` (instead of explicit `transition-colors` / `transition-[transform,opacity]`).
  3. **Sub-legible glowing pills (L278):** `text-[9px] font-extrabold uppercase bg-accentPurple/25 ... shadow-[0_0_10px_rgba(139,92,246,0.2)]` — violates `unslop`'s 11px minimum text floor, weight `400–600` ceiling, and quiet-meta rule.
  4. **Brand & Mirror Guardrails (Critical for D14.6):**
     - Run strictly in **Polish Mode** on `sigir/d14-recovery` (`fe8887c` base, NOT `main`).
     - **Keep Archipelago's "One Bright Moment":** the interactive 3D Knowledge Graph / Concept Map & Chromatic Canvas—make the surrounding chrome (sidebar, buttons, Inspector headers, citations) quiet so the graph and cited evidence stand out.
     - **Enforce `D14_INTEGRATION_CONTRACT.md` UI Mirror Invariant:** every edit to `host_inference/ui/<file>` MUST be mirrored identically to `ui/chat/<file>`.
- **Draft Proposal:** [`docs/reports/d14/tooling_proposals/archipelago-unslop-polish-SKILL.md`](tooling_proposals/archipelago-unslop-polish-SKILL.md)

---

### 2.3 Elephant-Goldfish Model / EGM (`https://github.com/google/elephant-goldfish-model`)

- **Verdict:** `ADOPT_WORKFLOW_PATTERN` (immediate operationalization in D14 swarm via `d14-independent-verifier`; optional full plugin install via `agy plugin install https://github.com/google/elephant-goldfish-model`).
- **License:** **Apache-2.0** (Google). Permissive; safe for workflow adaptation and direct plugin install.
- **Architecture & Dependencies:**
  - Zero external runtime dependencies; pure Markdown skills (`egm-brainstorm`, `egm-draft`, `egm-review`, `egm-review-loop`, `egm-resolve`, `egm-drift-report`, `egm-lite`, `egm-bootstrap`), 10 reviewer persona prompts in `agents/` (`comprehension.md`, `design_critic.md`, `structural.md`, `style.md`, `implementation_readiness.md`, `codebase_details.md`, `zoom_out.md`, `inventive_catalyst.md`, `synthesizer.md`, `bootstrap_orchestrator.md`), and document standards in `resources/document_standards/`.
  - **Antigravity Compatibility (verified in `docs/harnesses.md`):** Supported natively in Antigravity CLI (`agy plugin install https://github.com/google/elephant-goldfish-model`), Antigravity App, and Antigravity for IDEs (requires fresh-context subagents; not supported in standalone Antigravity IDE without `invoke_subagent`).
- **Security Posture:** Strong. Explicitly enforces workspace-boundary path checks (resolves symlinks, skips/asks before reading files outside working directory or remote URLs) and enforces strict non-sycophantic adversarial review language.
- **Mapping to Archipelago D14 Swarm (`d14-independent-verifier`):**
  - **Elephant role:** High-context D14 specialist workers (`d14-corpus`, `d14-retrieval`, `d14-synthesis`, `d14-ux-followups`, `d14-streaming-auth`) who hold full debugging history and write specs/patches.
  - **Goldfish role:** `d14-independent-verifier` (spawned fresh via `swarm{action:"add"}` **without** `fork`, so it has zero prior conversation bias).
  - **Condensed 3-Stage D14 Goldfish Gate (before `d14-integrator` merges any specialist branch):**
    1. **Stage A — Comprehension (Zero Extra Context):** Read only the specialist's PR summary/spec + diff. Paraphrase what it claims to fix and flag any unstated assumption or missing edge case.
    2. **Stage B — Critic & Caller Verification:** Cross-check the diff against `D14_CONSOLIDATED_DEFECT_REGISTER.csv`, `D14_INTEGRATION_CONTRACT.md` (file ownership + UI mirror), and all callers in the codebase.
    3. **Stage C — Implementation & Scientific Readiness:** Verify regression tests fail before fix / pass after fix, `open_access` / `pearson_books: 0` isolation holds, and benchmark isolation (`D14_BENCHMARK_ISOLATION_CONTRACT.md`) is unbroken.
- **Draft Proposal:** [`docs/reports/d14/tooling_proposals/archipelago-egm-goldfish-WORKFLOW.md`](tooling_proposals/archipelago-egm-goldfish-WORKFLOW.md)

---

### 2.4 Agent Reach (`https://github.com/Panniantong/Agent-Reach`)

- **Verdict:** `DEFER` for D14.1 corpus discovery & ingestion. (If ever used for ad-hoc manual link reading, restrict strictly to `USE_AS_CLI_TOOL` with `--backend public-web` or `github` only, never logged-in browser/cookie channels.)
- **License:** **MIT** (`Neo Reid` / `Agent Eyes`, v1.6.1).
- **Architecture & Dependencies:**
  - Python `>=3.10` CLI (`requests`, `loguru`, `pyyaml`, `yt-dlp==2026.8.19`) providing 15 channels (`web`, `github`, `youtube`, `reddit`, `twitter`, `bilibili`, `xiaohongshu`, `linkedin`, `facebook`, `instagram`, `v2ex`, `xueqiu`, `boss`, `xiaoyuzhou`).
  - `web` channel uses `https://mcp.exa.ai/mcp` (Exa MCP search) and `https://r.jina.ai/<url>` (Jina Reader) as free public-web fallbacks.
  - Optional authenticated channels rely on **CloakBrowser** (anti-detect headless Chromium) and **OpenCLI Chrome extension**, which copies active site login sessions/cookies from the user's Chrome browser into a dedicated browser profile.
- **Security, Legal & ToS Assessment for D14.1:**
  - **Positive controls observed:** `agent_reach/utils/url.py` implements solid SSRF protection (`normalize_public_http_url` blocks `localhost`, RFC1918/non-global IPs, and cloud metadata hosts); `SKILL_en.md` enforces read-only red lines and stops on `RATE_LIMITED` / `PLATFORM_BLOCKED` without CAPTCHA bypass.
  - **Material risks for Archipelago D14.1:**
    1. **Cookie/session reuse risk:** OpenCLI cookie copying from a developer's primary Chrome browser is unsafe on a machine that accesses UEM institutional accounts, Supabase, or Vercel.
    2. **Third-party transit & brittle rate limits:** Routing corpus discovery through `r.jina.ai` and unauthenticated `mcp.exa.ai` introduces opaque rate limits, non-reproducible HTML-to-Markdown transforms, and external third-party transit.
    3. **Copyright & OER provenance mismatch:** D14.1 needs **verifiably open-licensed academic textbooks and OER** (CC-BY, CC-BY-SA, CC0, MIT/Apache docs, arXiv open licenses) with deterministic URLs, SHA-256 checksums, and machine-readable license metadata for SIGIR 2027 reproducibility. Social platforms (Reddit, X, Xiaohongshu, LinkedIn) are neither peer-reviewed textbooks nor legally clean OER sources, and scraping them violates platform ToS.
- **Recommended Alternative for D14.1:** Use direct, official, zero-fee academic/OER APIs and repositories:
  - **OpenStax** (`openstax.org` — CC BY 4.0 textbooks), **DOAB** (`directory.doabooks.org/rest`), **OpenAlex** (`api.openalex.org`), **arXiv API** (`export.arxiv.org/api/query`), **MIT OCW** (`ocw.mit.edu` — CC BY-NC-SA 4.0, check NC compatibility), **Open Textbook Library** (`open.umn.edu/opentextbooks`), and **GitHub REST API / `gh`** (checking `license.spdx_id` before download).

---

### 2.5 Claude Code Setup (`anthropics/claude-plugins-official/plugins/claude-code-setup`)

- **Verdict:** `ADOPT_WORKFLOW_PATTERN` (execute its read-only codebase audit methodology periodically; no need to keep installed as an always-on plugin).
- **License:** **Apache-2.0** (Anthropic).
- **Security Posture:** Strictly read-only (`tools: Read, Glob, Grep, Bash`); recommends at most 1–2 high-value automations per category and never edits files itself.

---

## 3. Executed `claude-code-setup` Audit for Archipelago

Applying `claude-automation-recommender`'s exact Phase 1–3 methodology against this repository:

### Codebase Profile
- **Runtime & Backend:** Python 3.12 (`pyproject.toml`), Flask + Gunicorn, Pydantic v2, `psycopg[binary]` (Supabase/PostgreSQL), Kuzu graph DB, Ollama (`qwen3.5:0.8b`), multi-service Vercel (`host_inference/app.py`, `host_research/app.py`).
- **Frontend:** Vanilla HTML/CSS/JS + Tailwind utility classes + Three.js 3D canvas (`host_inference/ui/` mirrored to `ui/chat/`).
- **Quality & CI:** `.github/workflows/ci.yml` (`ruff`, `mypy --strict`, `scripts/quality_gate.py`, `pytest` unit/integration, `bandit`, `pip-audit`, graph-integrity).
- **Current Agent Configs:** `AGENTS.md` at repo root; **0** project-local `.agents/skills/` or hooks; **1** global plugin (`supabase`); **72** global `gsd-*` skills in `~/.gemini/config/skills/`.

### Top 1–2 Automations per Category

#### A. MCP Servers
1. **Playwright MCP** (`@playwright/mcp` / Chrome DevTools plugin)
   - **Why:** D14.6 (`d14-ux-followups`) and D14.7 (`d14-streaming-auth`) need real browser verification for `/chat` loading, sign-out/sign-in latency, SSE streaming stop/completion states, and `unslop` visual regression checks.
2. **Supabase MCP (Already Installed — Needs Staging Pinning)**
   - **Why:** `~/.gemini/config/plugins/supabase` is already installed. Use it *strictly* for read/verification against Research Staging (`edokbtmhztkhndmxetpy`) and enforce a guardrail against UEM Production (`spllaastejfwclllfndp`).

#### B. Skills (Project-Local `.agents/skills/`)
1. **`archipelago-ponytail`** (Concise diffs + caller grep + mandatory risky-logic test + `/ponytail-review`)
   - **Why:** Operationalizes `AGENTS.md` before code is written and cuts diff/token bloat across all 8 D14 specialist workers.
2. **`archipelago-unslop-polish`** (Light-slop UI craft pass with Archipelago 3D brand preservation + mirror invariant)
   - **Why:** Targets the exact AI-slop defects found in `host_inference/ui/index.html` while protecting `ui/chat/` mirror parity and accessibility.

#### C. Hooks (Pre/Post Tool Safety & Hygiene)
1. **PreToolUse Protected-Path & UEM-Deploy Guard**
   - **Why:** Hard-blocks any accidental write/edit to `/home/pratay-karali/Desktop/sigit_manu*`, `.env*`, or any `.vercel/project.json` containing UEM's `prj_yVvxBExHYiLa67oqnABK2vW9FfCS`, and blocks overwriting frozen baseline files in `docs/reports/d14/D14_BASELINE_MANIFEST.json`.
2. **PostToolUse Scoped `ruff` + UI Mirror Sync Check**
   - **Why:** Automatically runs `ruff check` on edited `.py` files under `archipelago/`, `okf/`, `host_inference/`, and warns immediately if a file in `host_inference/ui/` is edited without mirroring to `ui/chat/`.

#### D. Subagents / Swarm Personas
1. **`d14-goldfish-verifier` (EGM Pattern)**
   - **Why:** Fresh zero-context subagent (never `fork`ed) that reviews every specialist's spec + diff against `D14_CONSOLIDATED_DEFECT_REGISTER.csv` and `D14_INTEGRATION_CONTRACT.md` before merge.
2. **`d14-security-boundary-auditor`**
   - **Why:** Verifies `ARCHIPELAGO_TOKEN` 401/200 auth boundaries, prompt-injection delimiters, and `ARCHIPELAGO_ACCESS_PROFILE=open_access` (`pearson_books: 0`) isolation on every PR touching auth, retrieval, or corpus loaders.

#### E. Slash Commands (Workflow Shortcuts)
1. **`/d14-gate`** — Runs `ruff check`, `python scripts/quality_gate.py`, scoped `pytest tests/unit/`, and `diff -qr host_inference/ui ui/chat` in one command before handoff to `d14-integrator`.
2. **`/d14-goldfish-review <target>`** — Triggers the 3-stage zero-context EGM review on a D14 spec or specialist branch diff.

#### F. Clutter to Trim (High-ROI Context Win)
- **72 global `gsd-*` skills in `~/.gemini/config/skills/`:** Every Antigravity turn currently injects all 72 `gsd-*` skill descriptions into the system prompt, consuming thousands of tokens per turn across every swarm worker.
  - **Action:** Run the built-in `gsd-surface` skill (e.g., disable unused GSD clusters or apply a minimal profile) while running the D14 swarm so only active skills are surfaced.
- **Legacy root backup/duplicate files (defer to post-D14 cleanup, do not touch in D14.0):** e.g., `host_inference/ui/index.html.stripped_backup_20260729`, duplicate `archipelago_review.md` / `ARCHIPELAGO_REVIEW.md` on `main` (verify status on `sigir/d14-recovery`).

---

## 4. Exact Activation Steps (Once Approved by `@coordinator` / User)

> **Do not run these until `@coordinator` approves transition to `sigir/d14-recovery`.**

1. **Activate `archipelago-ponytail` & `archipelago-unslop-polish` as project-local Antigravity skills** (on `sigir/d14-recovery`):
   ```bash
   mkdir -p .agents/skills/archipelago-ponytail .agents/skills/archipelago-unslop-polish
   cp docs/reports/d14/tooling_proposals/archipelago-ponytail-SKILL.md \
      .agents/skills/archipelago-ponytail/SKILL.md
   cp docs/reports/d14/tooling_proposals/archipelago-unslop-polish-SKILL.md \
      .agents/skills/archipelago-unslop-polish/SKILL.md
   ```
2. **Activate EGM Goldfish Review:**
   - **Swarm-native (zero install, works immediately):** Include [`docs/reports/d14/tooling_proposals/archipelago-egm-goldfish-WORKFLOW.md`](tooling_proposals/archipelago-egm-goldfish-WORKFLOW.md) in `d14-independent-verifier`'s brief when spawning it fresh (`swarm{action:"add"}` without `fork`).
   - **Optional full EGM plugin install (Antigravity CLI/App):**
     ```bash
     agy plugin install https://github.com/google/elephant-goldfish-model
     ```
3. **Trim GSD Skill Clutter (Immediate Token Savings):**
   - Invoke `gsd-surface` in a main session to disable unused `gsd-*` clusters (reducing 72 surfaced skills down to <=10).
4. **Do NOT install `Agent-Reach` for D14.1.** Use canonical open-license APIs (OpenStax, DOAB, OpenAlex, arXiv, GitHub REST/SPDX) in `d14-corpus`.

---

## 5. Companion Deliverables in `docs/reports/d14/tooling_proposals/`

1. [`archipelago-ponytail-SKILL.md`](tooling_proposals/archipelago-ponytail-SKILL.md) — Archipelago-adapted Ponytail 5 skill & review rubric (MIT attribution preserved).
2. [`archipelago-unslop-polish-SKILL.md`](tooling_proposals/archipelago-unslop-polish-SKILL.md) — Archipelago D14.6 Polish-Mode UI audit skill (CC BY 4.0 attribution to Damir Sokolovsky / `@heydamir` preserved).
3. [`archipelago-egm-goldfish-WORKFLOW.md`](tooling_proposals/archipelago-egm-goldfish-WORKFLOW.md) — Operationalized 3-stage Goldfish verification protocol for `d14-independent-verifier` (Apache-2.0 attribution preserved).

---
name: archipelago-egm-goldfish
description: >
  Zero-context Goldfish verification workflow for Archipelago D14 specs and specialist
  branches, adapted from Google's Elephant-Goldfish Model (Apache-2.0,
  google/elephant-goldfish-model). Operationalizes independent adversarial review via
  d14-independent-verifier before d14-integrator merges into sigir/d14-recovery.
license: Apache-2.0
metadata:
  adapted_from: https://github.com/google/elephant-goldfish-model
  author_upstream: Google (Elephant-Goldfish Model contributors)
---

# Archipelago D14 Goldfish Review Protocol (EGM Pattern)

Adapted from Google's **Elephant-Goldfish Model** ([github.com/google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model)), licensed under **Apache-2.0**.

## Core Isolation Invariant

- **Elephant (Specialist Worker):** Holds full debugging history, drafts the spec/patch on `d14/<slug>`, and hands off only the artifact path + git diff.
- **Goldfish (`d14-independent-verifier`):** MUST be spawned fresh via `swarm{action:"add"}` **without** `fork`. A review performed in the Elephant's own context is **not** a Goldfish review.
- **Tone:** Direct, plain-English, adversarial scrutiny. Never use sycophantic praise (`"great"`, `"brilliant"`, `"perfect"`, `"spot-on"`). Every finding must cite a concrete file, line, or failing input.

## 3-Stage D14 Goldfish Gate

### Stage A — Comprehension Check (Zero Extra Context)
- **Inputs:** ONLY the specialist's spec/summary and `git diff sigir/d14-recovery..d14/<slug>`. Do NOT read prior board chatter first.
- **Output:**
  1. Two-sentence paraphrase of what the change claims to fix and how.
  2. List of unstated assumptions, ambiguous edge cases, or claims not backed by the diff.

### Stage B — Critic & Contract Audit
- **Inputs:** Add `docs/reports/d14/D14_CONSOLIDATED_DEFECT_REGISTER.csv`, `docs/reports/d14/D14_INTEGRATION_CONTRACT.md`, and live callers in the repo.
- **Checks:**
  1. **Ownership & Mirror:** Every modified file is inside the specialist's ownership slice; any `host_inference/ui/` edit is mirrored identically to `ui/chat/`.
  2. **Caller & Root-Cause Integrity:** All callers of modified functions were checked; no symptom-only patch leaving shared logic broken.
  3. **Defect Closure:** Each claimed `defect_id` has a verifiable mechanism fixing its root cause.

### Stage C — Implementation & Scientific Readiness
- **Inputs:** Add `docs/reports/d14/D14_BENCHMARK_ISOLATION_CONTRACT.md` and run read-only verification commands (`ruff`, `scripts/quality_gate.py`, scoped `pytest`).
- **Checks:**
  1. New non-trivial logic / bug fixes include targeted regression tests.
  2. No contamination of the 50 held-out SIGIR benchmark questions, historical results, or protected manuscript directories (`/home/pratay-karali/Desktop/sigit_manu*`).
  3. `ARCHIPELAGO_ACCESS_PROFILE=open_access` (`pearson_books: 0`) and `ARCHIPELAGO_TOKEN` auth boundaries remain intact.
  4. Zero references or deploy links pointing to UEM production (`prj_yVvxBExHYiLa67oqnABK2vW9FfCS` / `spllaastejfwclllfndp`).

## Output Format (Artifact-First)

Write findings to `docs/reports/d14/reviews/<slug>_goldfish_review.md` classified as:
- **🔴 Blocker** (must fix before `d14-integrator` merges)
- **🟡 Major** (missing regression test, edge-case gap, or contract drift)
- **🟢 Nit** (minor clarity/cleanup)

Post only the verdict (`APPROVE` / `CHANGES_REQUESTED`), blocker count, and report path to the specialist and `@d14-integrator`.

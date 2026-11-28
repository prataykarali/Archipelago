---
name: archipelago-ponytail
description: >
  Concise, reuse-first engineering and diff review discipline for Archipelago D14,
  adapted from Ponytail 5 (MIT, DietrichGebert/ponytail) to complement AGENTS.md.
  Use when implementing fixes, refactoring, or reviewing specialist branches before
  merging into sigir/d14-recovery.
license: MIT
metadata:
  adapted_from: https://github.com/DietrichGebert/ponytail
  author_upstream: DietrichGebert
---

# Archipelago Ponytail (Concise Engineering & Pre-Merge Review)

Adapted from Ponytail 5 (MIT License, DietrichGebert) for Archipelago AI Labs (`AGENTS.md`).

## Core Rule

Solve the complete task with the smallest, clearest diff. Never cut trust-boundary validation, error handling that prevents data loss, security (`ARCHIPELAGO_TOKEN`, prompt-injection sanitization), `open_access` isolation (`pearson_books: 0`), accessibility, or `host_inference/ui/` <-> `ui/chat/` mirror parity.

## Before Editing

1. Read the target code and every caller it touches (`grep` all callers before changing a signature or fixing a bug).
2. Confirm your file is inside your `D14_INTEGRATION_CONTRACT.md` ownership slice.
3. Check the 6-rung ladder — stop at the first rung that fully works:
   1. **Does it need to exist?** Skip unrequested options, flags, or abstractions.
   2. **Already in Archipelago?** Reuse existing helpers in `archipelago/`, `okf/`, or `host_inference/`.
   3. **Python 3.12 stdlib / native Web API?** Prefer stdlib/native over custom wrappers.
   4. **Already in `requirements.txt`?** Never add a dependency for <100 lines.
   5. **One clear line?** Prefer direct, readable code over clever indirection.
   6. **Minimum complete code** that stays `<=500` lines/file (prefer `<=300`), uses named constants (no magic numbers), and passes `ruff` + `scripts/quality_gate.py`.

## Mandatory Test & Debt Invariants

- Every new branch, loop, parser, retrieval/ranking heuristic, security check, or D13 bug fix **must** ship with at least one targeted regression test in `tests/unit/` or `tests/integration/`.
- Mark any intentional bounded shortcut as: `# shortcut: <limit>, <when to upgrade>`.
- End every handoff message with 1–2 lines: **Not checked:** `<what was skipped>` and **Risk:** `<any residual risk>`.

## Pre-Merge Review Mode (`/ponytail-review` Equivalent)

When reviewing a D14 specialist branch before `d14-integrator` merges it:
1. Read the diff **and** its callers, tests, and UI mirror (if applicable).
2. Rank findings strictly as **Must fix** (bug, security, data loss, contract breach), **Should fix** (missing regression test, duplication, dead code), or **Nice to have**.
3. Every finding requires a concrete failing case and four short lines: **What this is**, **Problem**, **Fix**, **If we skip it**.
4. End with `Verdict: Ship.` or `Verdict: fix <N> first.` plus `Not checked: <line>`.

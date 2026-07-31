# Skill 1 — Engineer (50 Laws)

**Owners:** Lead Engineer, Frontend Engineer  
**Enforced by:** CI Engineer Gate + architecture checks in `scripts/quality_gate.py`  
**Sources:** Karpathy (reader > writer, understand over abstraction), Rauch (edge-first, a11y-as-correctness), swyx + Chase (LLM eng), Willison (prompt injection).

---

## A. Correctness (Laws 1–10)

| # | Law | Practice |
|---|-----|----------|
| 1 | **Correctness before cleverness** | Prefer the boring solution that is right. |
| 2 | **Fail loud, fail early** | Invalid state raises; never continue silently. |
| 3 | **Validate at boundaries** | Sanitize and type-check every external input (HTTP, LLM, file, env). |
| 4 | **Types are contracts** | Public functions have full type hints; `mypy --strict` is non-optional. |
| 5 | **One source of truth** | Config, schema, and constants live in one place; no duplicate magic. |
| 6 | **Idempotent where possible** | Retries must not double-write or corrupt graph state. |
| 7 | **Explicit errors** | Raise domain exceptions with messages a caller can act on. |
| 8 | **No half-initialized services** | Readiness (`/api/readiness`) is false until deps are actually ready. |
| 9 | **Deterministic defaults** | Same input + same env → same routing decision (LLM synthesis may vary). |
| 10 | **Test the bug, then fix** | Regression test lands with the fix, never after. |

---

## B. Clarity (Laws 11–20)

| # | Law | Practice |
|---|-----|----------|
| 11 | **Optimise for the reader, not the writer** (Karpathy) | Names must carry meaning without a glossary. |
| 12 | **One idea per function** | If the docstring needs “and”, split the function. |
| 13 | **Names beat comments** | Comment *why*, never *what* the code already says. |
| 14 | **Delete dead code** | No commented-out blocks; git remembers. |
| 15 | **Short files, many files** | ≤ 500 lines hard; prefer ≤ 300; breadth over bulk. |
| 16 | **One feature per package** | `inference/`, `okf/graph/`, `okf/eval/` — not mixed blobs. |
| 17 | **Public API is small** | Export only what callers need; hide helpers. |
| 18 | **Docstrings are skim-first** | One-line summary; Args/Returns/Raises only when non-obvious. |
| 19 | **No clever one-liners** | Nested comprehensions that need a pause get a loop. |
| 20 | **Understand over abstraction** (Karpathy nanoGPT) | If you cannot explain it in one sentence, it is too abstract. |

---

## C. Architecture (Laws 21–30)

| # | Law | Practice |
|---|-----|----------|
| 21 | **Import downward only** | `apps → inference / okf`. Never reverse. |
| 22 | **Root shims are legacy only** | New code imports from feature packages. |
| 23 | **No circular imports** | Fix with package splits or local imports at call sites sparingly. |
| 24 | **State is explicit** | Session/graph/model state lives in named modules (`state.py`), not globals sprinkled everywhere. |
| 25 | **Side effects at the edge** | Pure core; I/O in routes, workers, scripts. |
| 26 | **Schema before code** | Graph/catalog schema changes are reviewed like code. |
| 27 | **Feature flags over forks** | Behaviour toggles via env/config, not copy-pasted branches. |
| 28 | **Contracts over convenience** | JSON response shapes are versioned by tests. |
| 29 | **Split before you hit 500** | Refactor proactively; do not wait for the gate. |
| 30 | **No magic numbers** | Literals other than `0`, `1`, `-1` are named constants. |

---

## D. AI / LLM Engineering (Laws 31–40)

| # | Law | Practice |
|---|-----|----------|
| 31 | **Prompts are code** (swyx + Chase) | Version-controlled, reviewed, tested; no ad-hoc production strings. |
| 32 | **Prompt injection law** (Willison) | Untrusted user text is never interpolated raw into system/instruction layers. |
| 33 | **Delimit, sanitise, escape** | User content goes in clearly marked, filtered sections. |
| 34 | **Evals are not optional** (swyx) | No LLM path merges without an eval or deterministic fixture suite. |
| 35 | **Ground before generate** | Retrieval / graph facts first; synthesis second. |
| 36 | **Cite or refuse** | Library answers need citations or an honest “not in corpus” path. |
| 37 | **Check LLM output** | Parse, validate schema, strip injection; never trust raw model text. |
| 38 | **Separate routing from prose** | Intent/scope gates are code; chat wording is synthesis. |
| 39 | **Log enough to debug, not enough to leak** | No secrets or full PII in logs. |
| 40 | **Model is a dependency** | Pin model name/version in config; document behaviour change. |

---

## E. Frontend & Deployment (Laws 41–45)

| # | Law | Practice |
|---|-----|----------|
| 41 | **Edge-first** (Rauch) | Minimise round-trips; cache; assume slow network. |
| 42 | **Accessibility-as-correctness** (Rauch) | If a screen reader cannot use it, it is a bug. |
| 43 | **Progressive enhancement** | Core chat/query works without fragile JS-only traps. |
| 44 | **Bind loopback by default** | `127.0.0.1`; `0.0.0.0` only with `ARCHIPELAGO_TOKEN`. |
| 45 | **Three services, one ops script** | Inference 5051, graph 5050, chat 5052 via `scripts/ops/serve.sh`. |

---

## F. Python & Performance (Laws 46–50)

| # | Law | Practice |
|---|-----|----------|
| 46 | **`from __future__ import annotations`** | On every new module. |
| 47 | **pytest markers** | `unit` / `integration` / `e2e` — use them. |
| 48 | **ruff + mypy are the floor** | Format, lint, types before human review. |
| 49 | **Measure before optimising** | No premature caches or micro-opts without a profile or slow path. |
| 50 | **Cheap path first** | Library queries prefer structured graph/catalog hits before heavy LLM synthesis. |

---

## Local checklist (Engineer Gate)

```bash
ruff check .
ruff format --check .
mypy --strict archipelago/ okf/
python scripts/quality_gate.py
```

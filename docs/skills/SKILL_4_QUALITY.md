# Skill 4 — Quality (5-Pass Review + Banned Patterns)

**Owner:** Release Engineer (pairs with Lead in Week 4)  
**Enforced by:** `scripts/quality_gate.py` + branch protection (human approval)  
**Sources:** Karpathy/Willison gate — nothing ships until all five passes clear.

---

## Core stance

Quality is a gate, not a vibe. Automated passes 1–4 must be green.
Pass 5 requires a human from a **different role** than the author pair.

---

## The 5-Pass Review

| Pass | Name | What runs | Automated? |
|------|------|-----------|------------|
| 1 | **Lint** | `ruff check` + `ruff format --check` | Yes |
| 2 | **Types** | `mypy --strict` on `archipelago/`, `okf/` | Yes |
| 3 | **Banned patterns** | `scripts/quality_gate.py` pattern scan | Yes |
| 4 | **Architecture** | File size, import direction, feature boundaries | Yes |
| 5 | **Human review** | Approval from a different role | Manual |

**Ship rule:** Passes 1–5 all clear, or it does not merge.

---

## Banned Patterns (Auto-Fail)

| Pattern | Example | Why banned |
|---------|---------|------------|
| Bare / silent swallow | `except: pass` | Hides failures |
| Broad silent swallow | `except Exception: pass` | Same — use `logging.exception` |
| Magic numbers | `if x > 42:` (not `0`/`1`/`-1`) | Unmaintainable |
| Hardcoded credentials | `password = "admin"` | Security risk |
| Unchecked LLM output | raw `ollama.chat(...)` used as truth | Hallucination / injection |
| Prompt injection sinks | `f"User: {user_input}\nAssistant:"` | Injection vector |
| `eval(` | `eval(user_input)` | Code execution |
| `exec(` | `exec(user_input)` | Code execution |
| `shell=True` | `subprocess.run(cmd, shell=True)` | Shell injection |
| `pickle.load` | `pickle.load(f)` | Deserialization attack |
| `os.system` | `os.system(cmd)` | Shell injection |
| Unsafe YAML | `yaml.load(data)` without SafeLoader | Deserialization attack |
| TLS bypass | `verify=False` | MITM risk |

Checked by:

```bash
python scripts/quality_gate.py
```

Scope: all `.py` under product packages (excludes pure `tests/` and tooling
paths as configured in the script).

---

## Architecture rules (Pass 4)

1. **File size** ≤ 500 lines (prefer ≤ 300; more files/folders over bulk).  
2. **Import direction** `apps → inference / okf` only.  
3. **One feature per package** — split rather than swell.  
4. **No new root production logic** — feature packages only; root shims for compat.  
5. **Named constants** for every non-trivial literal.

---

## Human review (Pass 5)

| Rule | Detail |
|------|--------|
| Who | At least one approver **not** on the authoring pair that day |
| What they check | Intent, security, eval coverage, UX/a11y if UI, deploy risk |
| Blockers | Missing tests for LLM paths, unexplained new deps, secret leakage |
| Record | GitHub approval + note in `docs/reports/HANDOFF.md` if non-obvious |

---

## Quality laws (operating rules)

| # | Rule |
|---|------|
| Q1 | Run the quality gate **before every push**. |
| Q2 | Never disable a gate to “unblock” without Release + Lead written approval. |
| Q3 | Fix forward on `main` only via PR; no force-push to `main`. |
| Q4 | CD is sequential on `main`; concurrent PRs are fine until merge. |
| Q5 | Banned-pattern exceptions require a documented allowlist entry, not a comment. |
| Q6 | File-size failures are fixed by splitting packages, not by raising the limit. |
| Q7 | Human approval from the same person who wrote the code does not count. |
| Q8 | Security findings (bandit/secrets) are merge blockers, not TODOs. |
| Q9 | Prompt/eval changes require Skill 2 distribution notes when behaviour shifts. |
| Q10 | Release owns the red button: if staging smoke fails, production does not move. |

---

## Local checklist (Quality Gate)

```bash
python scripts/quality_gate.py
ruff check .
ruff format --check .
mypy --strict archipelago/ okf/
./scripts/ops/pilot_readiness.sh SKIP_LIVE=1
```

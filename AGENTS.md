# Archipelago AI Labs — Engineering Standards

## Company Structure

**5 employees, 2 working at a time.** Pair programming with rotating partners.
Every change ships through a shared CI/CD pipeline that enforces all four
skill sets below.

| # | Role | Primary Skill | Responsibilities |
|---|------|--------------|-----------------|
| 1 | Lead Engineer | Skill 1 — Engineer (50 laws) | Backend architecture, Python, AI/LLM engineering, deployment |
| 2 | Frontend Engineer | Skill 1 — Engineer + UI/UX | Chat UI, graph UI, edge-first, accessibility-as-correctness |
| 3 | QA Engineer | Skill 2 — Tester (20 laws) | Unit tests, integration tests, security, prompt-injection suites |
| 4 | ML Engineer | Skill 3 — Resourceful (20 laws) | LLM prompts, evals, fine-tuning, model optimization |
| 5 | Release Engineer | Skill 4 — Quality (5-pass review) | Quality gates, banned patterns, deployment, code review |

### Pairing Rotation

```
Week 1: Lead Engineer + Frontend Engineer
Week 2: Lead Engineer + QA Engineer
Week 3: Lead Engineer + ML Engineer
Week 4: Lead Engineer + Release Engineer
```

Daily handoff: each pair writes a `HANDOFF.md` entry in `docs/reports/`
summarising what was built, what was deferred, and what the next pair
should know.

**Full roster, pair rules, efficiency doctrine:**
[`docs/company/EMPLOYEES.md`](docs/company/EMPLOYEES.md)

---

## Efficiency Doctrine (breadth over bulk)

- **Files ≤ 500 lines** (prefer ≤ 300). Split before you hit the limit.
- **More folders/files, not larger files.** One concern per module.
- **One feature per package:** `archipelago/inference/`, `okf/graph/`,
  `okf/cleanup_parts/`, `okf/eval/`.
- **Features import downward only:** `apps → inference / okf`. Never reverse.
- **Root shims only for backwards compat.** New code imports from feature packages.
- **No magic numbers.** Every literal that isn't `0`, `1`, or `-1` is a named constant.

---

## Skill 1 — Engineer (50 laws)

**Full text:** [`docs/skills/SKILL_1_ENGINEER.md`](docs/skills/SKILL_1_ENGINEER.md)

### Core Principles (summary)

1. **Optimise for the reader, not the writer** (Karpathy). Every function,
   class, and module should be self-documenting. If the reader has to look
   up a name, the name failed.
2. **Understand over abstraction** (Karpathy nanoGPT). Prefer explicit,
   readable code over clever indirection. If you can't explain it in one
   sentence, it's too abstract.
3. **Edge-first** (Rauch). Design for the edge: minimise round-trips,
   cache aggressively, assume the network is slow.
4. **Accessibility-as-correctness** (Rauch). If a screen reader can't use
   it, it's a bug, not a feature request.
5. **Prompts are code** (swyx + Chase). Every prompt is version-controlled,
   reviewed, and tested. No inline prompts in production logic.
6. **Prompt injection law** (Willison). Untrusted input is never passed
   verbatim into an LLM prompt. Always delimit, sanitise, and escape.
7. **Evals are not optional** (swyx). Every LLM integration has an eval
   suite. No eval = no merge.

### Architecture Rules

- **Files ≤ 500 lines.** Split before you hit 500.
- **One feature per package.** `archipelago/inference/`, `okf/graph/`,
  `okf/cleanup_parts/`, `okf/eval/`.
- **Features import downward only.** `apps → inference / okf`. Never reverse.
- **Root shims only for backwards compat.** New code imports from feature
  packages.
- **No magic numbers.** Every literal that isn't `0`, `1`, or `-1` is a
  named constant.

### Python Rules

- Type hints on every public function.
- `from __future__ import annotations` at the top of every new file.
- Docstrings: one-line summary + Args/Returns/Raises as needed.
- `pytest` for all tests. Markers: `unit`, `integration`, `e2e`.
- `ruff` for lint + format. `mypy --strict` for type checking.

### Deployment Rules

- Three Flask services: inference (5051), graph (5050), chat (5052).
- Bind to `127.0.0.1` by default. `0.0.0.0` only with `ARCHIPELAGO_TOKEN` set.
- `scripts/ops/serve.sh start|stop|status|restart` manages all three.
- Health check: `GET /api/readiness` must return `{"ready": true}`.

---

## Skill 2 — Tester (20 laws)

**Full text:** [`docs/skills/SKILL_2_TESTER.md`](docs/skills/SKILL_2_TESTER.md)

### Core Principles (summary)

1. **Eval discipline** (swyx). Unit tests and LLM pipeline evals follow the
   same discipline: define expected behaviour, write the test, then code.
2. **Adversarial instinct** (Willison). Think like an attacker. What input
   breaks this? What if the user sends HTML? What if they send a prompt
   injection?
3. **LLM evals are probability checks, not pass/fail.** Report distributions:
   mean, std, min, max, p5, p95. A 90% pass rate with 0.3 std is better
   than a 100% pass rate with a single adversarial failure.
4. **Fuzz with hypothesis.** Property-based tests for parsers, sanitizers,
   and graph queries.
5. **Auth boundary tests.** Every endpoint that accepts `ARCHIPELAGO_TOKEN`
   must have a test that verifies 401 without it and 200 with it.

### Test Layers

| Layer | Path | Marker | Runs in CI |
|-------|------|--------|------------|
| Unit | `tests/unit/` | `unit` | Always |
| Integration | `tests/integration/` | `integration` | Always |
| E2E (live) | `tests/e2e/` | `e2e` | `RUN_LIVE_E2E=1` |

### Security Tests

- `bandit` — static analysis for common Python security issues.
- `detect-secrets` — scan for hardcoded credentials, API keys, tokens.
- Prompt injection test suite — adversarial queries that attempt to override
  system behaviour. Must be rejected or safely handled.
- Auth boundary tests — verify token enforcement on all mutating endpoints.

---

## Skill 3 — Resourceful (20 laws)

**Full text:** [`docs/skills/SKILL_3_RESOURCEFUL.md`](docs/skills/SKILL_3_RESOURCEFUL.md)

### Core Principles (summary)

1. **Prototype in a notebook, fine-tune last** (Howard). Get it working end-to-end
   before optimising. The first working version is the baseline.
2. **Search before you write** (Willison). Check existing code, existing
   libraries, existing solutions before adding a new dependency.
3. **Smaller model + better prompt heuristic.** A 0.8B model with a well-crafted
   prompt beats a 7B model with a vague one. Prefer `qwen3.5:0.8b`.
4. **Constraints produce creativity.** Limited context? Limited compute?
   Good. Constraints force you to find the elegant solution.
5. **Open-source instinct.** Prefer open-source tools. If you need a
   commercial service, justify it.

### Resource Guidelines

- **Model**: `qwen3.5:0.8b` via Ollama. `ARCHIPELAGO_LOAD_AURA=1` for
  embedding model (optional, larger).
- **Dependencies**: only add what you can't build in <100 lines.
- **Corpus**: stream from canonical public sources. Never commit copyrighted
  PDFs to the repo.

---

## Skill 4 — Quality (5-pass review + banned patterns)

**Full text:** [`docs/skills/SKILL_4_QUALITY.md`](docs/skills/SKILL_4_QUALITY.md)

### The 5-Pass Review

Before any code ships, it must pass all five passes. The CI pipeline
automates passes 1–4; pass 5 is human approval from a different role.

| Pass | Name | What | Automated? |
|------|------|------|------------|
| 1 | **Lint** | `ruff check` + `ruff format --check` | Yes |
| 2 | **Types** | `mypy --strict` | Yes |
| 3 | **Banned patterns** | `scripts/quality_gate.py` | Yes |
| 4 | **Architecture** | Dependency rules, file size, feature boundaries | Yes |
| 5 | **Human review** | At least one approval from a different role | Manual |

### Banned Patterns (Auto-Fail)

The following patterns cause immediate CI failure. They are checked by
`scripts/quality_gate.py`.

| Pattern | Example | Rationale |
|---------|---------|-----------|
| `except: pass` | `except: pass` | Silently swallows errors |
| `except Exception: pass` | `except Exception: pass` | Same — use `logging.exception` |
| Magic numbers | `if x > 42:` (not `0`, `1`, `-1`) | Unmaintainable |
| Hardcoded credentials | `password = "admin"` | Security risk |
| Unchecked LLM output | `result = ollama.chat(...)` without validation | Injection / hallucination |
| Prompt injection sinks | `f"User: {user_input}\nAssistant:"` | Prompt injection vector |
| `eval(` | `eval(user_input)` | Code execution |
| `exec(` | `exec(user_input)` | Code execution |
| `shell=True` | `subprocess.run(cmd, shell=True)` | Shell injection |
| `pickle.load` | `pickle.load(f)` | Deserialization attack |
| `os.system` | `os.system(cmd)` | Shell injection |
| `yaml.load` (unsafe) | `yaml.load(data)` | Deserialization attack |
| `verify=False` | `requests.get(url, verify=False)` | TLS bypass |

### Quality Gate Script

```bash
# Run locally before pushing:
python scripts/quality_gate.py
```

Checks:
1. Banned patterns in all `.py` files (excluding `tests/` and `scripts/`).
2. File size ≤ 500 lines.
3. No `except: pass` or `except Exception: pass`.
4. No hardcoded credentials (regex-based).
5. Architecture dependency rules.
6. Magic number detection (configurable exceptions).

---

## CI/CD Pipeline

**Full documentation:** [`docs/CI_CD.md`](docs/CI_CD.md)

### CI (Continuous Integration)

Runs on every PR and push to any branch.

```
┌─────────────────────────────────────────────────────┐
│                    CI Pipeline                       │
├─────────────────────────────────────────────────────┤
│ 1. Engineer Gate (Skill 1)                          │
│    ├── ruff check (lint)                           │
│    ├── ruff format --check                         │
│    ├── mypy --strict (type check)                  │
│    └── architecture check (deps, file size)        │
│                                                     │
│ 2. Tester Gate (Skill 2)                            │
│    ├── pytest tests/unit/ -m unit                  │
│    ├── pytest tests/integration/ -m integration    │
│    ├── bandit (security scan)                      │
│    ├── detect-secrets (credential scan)            │
│    └── prompt injection tests                       │
│                                                     │
│ 3. Quality Gate (Skill 4)                           │
│    ├── scripts/quality_gate.py                     │
│    └── 5-pass review (automated passes 1-4)        │
│                                                     │
│ 4. Report                                           │
│    └── GitHub Checks summary                        │
└─────────────────────────────────────────────────────┘
```

### CD (Continuous Deployment)

Runs on merge to `main`.

```
┌─────────────────────────────────────────────────────┐
│                    CD Pipeline                       │
├─────────────────────────────────────────────────────┤
│ 1. Build                                            │
│    ├── Install dependencies                         │
│    ├── Run migrations (Kuzu schema)                 │
│    └── Build artifacts                              │
│                                                     │
│ 2. Deploy to Staging                                │
│    ├── Start services (serve.sh start)              │
│    └── Wait for readiness                           │
│                                                     │
│ 3. Staging Tests                                    │
│    ├── pytest tests/integration/                   │
│    ├── pytest tests/e2e/ (RUN_LIVE_E2E=1)          │
│    ├── Gold eval (structural audit)                │
│    └── Smoke test (7-query demo gate)              │
│                                                     │
│ 4. Deploy to Production                             │
│    ├── Blue-green deploy                            │
│    └── Health check                                 │
│                                                     │
│ 5. Notify                                           │
│    └── Slack / email on success or failure          │
└─────────────────────────────────────────────────────┘
```

### Concurrent PR Workflow (2 employees at a time)

The CI pipeline is designed to support two concurrent PRs:

1. Each PR gets its own CI run (parallel jobs).
2. Quality gates are per-PR — no PR can merge without passing.
3. CD runs only on `main` — merges are sequential, preventing conflicts.
4. Staging deploys are isolated per PR via ephemeral environments.

---

## Definition map (source of truth)

| Topic | Path |
|-------|------|
| Company + pairing | [`docs/company/EMPLOYEES.md`](docs/company/EMPLOYEES.md) |
| Skill 1 — 50 laws | [`docs/skills/SKILL_1_ENGINEER.md`](docs/skills/SKILL_1_ENGINEER.md) |
| Skill 2 — 20 laws | [`docs/skills/SKILL_2_TESTER.md`](docs/skills/SKILL_2_TESTER.md) |
| Skill 3 — 20 laws | [`docs/skills/SKILL_3_RESOURCEFUL.md`](docs/skills/SKILL_3_RESOURCEFUL.md) |
| Skill 4 — quality | [`docs/skills/SKILL_4_QUALITY.md`](docs/skills/SKILL_4_QUALITY.md) |
| Skills index | [`docs/skills/README.md`](docs/skills/README.md) |
| CI/CD detail | [`docs/CI_CD.md`](docs/CI_CD.md) |

---

## Quick Reference

```bash
# Local development
source .venv/bin/activate
pip install -r requirements.txt
ruff check .
mypy --strict archipelago/
pytest tests/unit/ -m unit

# Quality gate (run before every commit)
python scripts/quality_gate.py

# Full CI simulation
./scripts/ops/pilot_readiness.sh SKIP_LIVE=1

# Start services
./scripts/ops/serve.sh start
```

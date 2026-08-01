# Archipelago CI/CD Pipeline

## Overview

The Archipelago CI/CD pipeline enforces the four engineering skill sets across
a 5-employee, 2-at-a-time pair-programming model. Every change ships through
shared gates that prevent regressions in correctness, security, quality,
and architecture.

**Definitions (source of truth):**

| Doc | Purpose |
|-----|---------|
| [company/EMPLOYEES.md](company/EMPLOYEES.md) | Roster, pairing, efficiency doctrine |
| [skills/SKILL_1_ENGINEER.md](skills/SKILL_1_ENGINEER.md) | 50 Engineer laws |
| [skills/SKILL_2_TESTER.md](skills/SKILL_2_TESTER.md) | 20 Tester laws |
| [skills/SKILL_3_RESOURCEFUL.md](skills/SKILL_3_RESOURCEFUL.md) | 20 Resourceful laws |
| [skills/SKILL_4_QUALITY.md](skills/SKILL_4_QUALITY.md) | 5-pass + banned patterns |

## Company Structure

| # | Role | Skill | Pairings (rotating) |
|---|------|-------|---------------------|
| 1 | Lead Engineer | Skill 1 (50 laws) | Weeks 1-4 (every week) |
| 2 | Frontend Engineer | Skill 1 + UI/UX | Week 1 |
| 3 | QA Engineer | Skill 2 (20 laws) | Week 2 |
| 4 | ML Engineer | Skill 3 (20 laws) | Week 3 |
| 5 | Release Engineer | Skill 4 (5-pass) | Week 4 |

Only 2 employees work at a time. The pipeline is designed to support two
concurrent PRs without blocking. Idle roles review or plan; they do not
push to the active pair's branch.

## CI Pipeline (Continuous Integration)

Triggers on every PR and push to any branch.

### Jobs

```
┌─────────────────────────────────────────────────────┐
│                    CI Pipeline                       │
├─────────────────────────────────────────────────────┤
│ 1. Engineer Gate (Skill 1)                          │
│    ├── ruff check (lint)                           │
│    ├── ruff format --check                         │
│    ├── mypy --strict (type check)                  │
│    └── quality_gate.py (architecture, file size)   │
│                                                     │
│ 2. Tester Gate (Skill 2)                            │
│    ├── pytest tests/unit/ -m unit                  │
│    ├── pytest tests/integration/ -m integration    │
│    ├── bandit (security scan)                      │
│    ├── detect-secrets (credential scan)            │
│    ├── prompt injection tests                      │
│    ├── auth boundary tests                         │
│    └── fuzz tests (hypothesis)                     │
│                                                     │
│ 3. Quality Gate (Skill 4)                           │
│    ├── quality_gate.py (Passes 1-4)                │
│    └── Pass 5: human review (manual approval)       │
│                                                     │
│ 4. Concurrent PR Check                               │
│    └── Merge conflict detection                    │
│                                                     │
│ 5. Report                                            │
│    └── GitHub Checks summary                       │
└─────────────────────────────────────────────────────┘
```

### Concurrent PR Workflow

1. Each PR gets its own CI run (parallel jobs).
2. Quality gates are per-PR — no PR can merge without passing.
3. CD runs only on `main` — merges are sequential, preventing conflicts.
4. Staging deploys are isolated per PR via ephemeral environments.

## CD Pipeline (Continuous Deployment)

Triggers on merge to `main`.

### Jobs

```
┌─────────────────────────────────────────────────────┐
│                    CD Pipeline                       │
├─────────────────────────────────────────────────────┤
│ 1. Build                                            │
│    ├── Install dependencies                         │
│    ├── Kuzu schema validation (dry-run)             │
│    ├── Entrypoint verification                     │
│    └── Upload artifacts                            │
│                                                     │
│ 2. Deploy to Staging                                │
│    ├── Start services (serve.sh start)             │
│    └── Wait for readiness                          │
│                                                     │
│ 3. Staging Tests                                    │
│    ├── Integration tests                           │
│    ├── E2E tests (RUN_LIVE_E2E=1)                  │
│    ├── Gold eval (structural audit)                │
│    ├── Smoke test (7-query demo gate)              │
│    └── Stop staging services                       │
│                                                     │
│ 4. Deploy to Production                             │
│    ├── Blue-green deploy (serve.sh restart)        │
│    └── Health check                                │
│                                                     │
│ 5. Notify                                           │
│    └── Success/failure report                      │
└─────────────────────────────────────────────────────┘
```

## Services

| Service | Port | Entry Point | Description |
|---------|------|-------------|-------------|
| Inference | 5051 | `python -m archipelago.apps.inference_app` | Chat API, RAG, graph queries |
| Graph | 5050 | `graph_server.py` | Graph API + graph UI |
| Chat | 5052 | `chat_server.py` | Chat UI (proxies to inference) |

All services bind to `127.0.0.1` by default. Set `ARCHIPELAGO_BIND=0.0.0.0`
and `ARCHIPELAGO_TOKEN=<secret>` to expose on LAN.

## Test Layers

| Layer | Path | Marker | Runs in CI | Runs in CD |
|-------|------|--------|------------|------------|
| Unit | `tests/unit/` | `unit` | Always | — |
| Integration | `tests/integration/` | `integration` | Always | Staging |
| E2E (live) | `tests/e2e/` | `e2e` | Never (opt-in) | Staging (opt-in) |

## Quality Gates

### Pass 1: Lint
- `ruff check .`
- `ruff format --check .`

### Pass 2: Types
- `mypy --strict archipelago/ okf/`

### Pass 3: Banned Patterns
Enforced by `scripts/quality_gate.py`:
- `except: pass` / `except Exception: pass`
- Magic numbers (not 0, 1, -1)
- Hardcoded credentials (password, api_key, token)
- Unchecked LLM output (direct `ollama.chat()` without validation)
- Prompt injection sinks (f-strings with `user_input`)
- `eval()`, `exec()`, `shell=True`, `pickle.load`, `os.system`, `yaml.load`, `verify=False`

### Pass 4: Architecture
- File size ≤ 500 lines
- Features import downward only (`apps → inference / okf`)
- No `except: pass`

### Pass 5: Human Review
- At least one approval from a different role
- Manual gate in GitHub branch protection

## Local Development

```bash
# Quick reference
source .venv/bin/activate
pip install -r requirements.txt

# Run quality gate (all automated passes)
python scripts/quality_gate.py

# Run tests
pytest tests/unit/ -m unit -q
pytest tests/integration/ -m integration -q

# Start services
./scripts/ops/serve.sh start

# Full CI simulation (offline)
./scripts/ops/pilot_readiness.sh SKIP_LIVE=1

# Full CD simulation (services up)
RUN_LIVE_E2E=1 ./scripts/ops/pilot_readiness.sh
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHIPELAGO_BIND` | `127.0.0.1` | Network bind address |
| `ARCHIPELAGO_TOKEN` | (empty) | API token for auth (required for `0.0.0.0` bind) |
| `ARCHIPELAGO_RATE_LIMIT_DISABLED` | `0` | Disable rate limiting (tests) |
| `ARCHIPELAGO_LOAD_AURA` | `0` | Load Aura embedding model |
| `ARCHIPELAGO_AUTO_OLLAMA` | `1` | Auto-warm Ollama on startup |
| `RUN_LIVE_E2E` | `0` | Run E2E tests (requires live services) |

### Secrets (GitHub)

| Secret | Used In | Description |
|--------|---------|-------------|
| `STAGING_ARCHIPELAGO_TOKEN` | CD staging | Token for staging deployment |
| `PROD_ARCHIPELAGO_BIND` | CD production | Bind address for production |
| `PROD_ARCHIPELAGO_TOKEN` | CD production | Token for production deployment |

## Daily Workflow

1. **Morning check**: `bash scripts/daily_check.sh`
2. **Start work**: `./scripts/ops/serve.sh start`
3. **Before commit**: `python scripts/quality_gate.py`
4. **Before push**: `pytest tests/unit/ -m unit -q`
5. **Daily handoff**: Write `docs/reports/HANDOFF.md`

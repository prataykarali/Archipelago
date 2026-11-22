# 12. CI/CD Specification (GitHub Actions)

This document outlines the Continuous Integration and Continuous Deployment (CI/CD) strategy for the Archipelago project, utilizing GitHub Actions.

## 1. Current State
- **GitHub Actions workflow directory:** `Archipelago/.github/workflows/`
- **Existing CI status:** Reported as "repaired" in Phase 5 of the clean architecture deployment.
- **Quality gate scripts:** `scripts/quality_gate.py` (10KB) and `scripts/quality_gate_checks.py` (10KB)
- **Test runner:** `pytest` with specific markers (`unit`, `integration`, `e2e`)
- **Linting:** Ruff (configured in `pyproject.toml`)
- **Type checking:** Mypy strict mode (configured in `pyproject.toml`)
- **Security:** Bandit (configured in `pyproject.toml`)

## 2. Proposed CI Pipeline

```yaml
# Trigger: push to main, pull requests
jobs:
  lint:
    - Ruff lint + format check
    - Mypy type check
    - Bandit security scan
  
  unit-tests:
    - pytest tests/unit/ -m unit
    - Coverage report (target: >80%)
  
  integration-tests:
    - pytest tests/integration/ -m integration
    - Requires: KùzuDB fixture, env vars
    - Known failures: 13 pre-existing (must fix)
  
  quality-gate:
    - scripts/quality_gate.py
    - 5,151-node baseline check (graph integrity)
    - Source link validation (40 Pearson + 21 HF)
    - No file >500 lines (AGENTS.md rule)
  
  build:
    - Docker build (python:3.12-slim)
    - Image size check
    - Healthcheck validation
  
  deploy-staging:
    - Deploy to staging AntDeploy
    - Run E2E smoke tests against staging
    - Validate /health and /api/readiness
  
  deploy-production:
    - Manual approval gate
    - Deploy to archipelago.antideploy
    - Post-deploy E2E validation
```

## 3. Quality Gate Checks
Defined primarily in `scripts/quality_gate.py`:
- Graph node count >= baseline (currently ~460, target 5,151 nodes)
- No dangling edges (edges referencing missing nodes)
- No self-loops in the graph
- No orphan nodes (optional warning)
- All source links resolve (40 Pearson, 21 HF)
- No magic numbers in new code
- No dependency direction violations
- All files <=500 lines (strict AGENTS.md rule)

## 4. Test Markers & Execution
Configured via `pytest.ini` (`pythonpath=["."], testpaths=["tests"]`):
- `@pytest.mark.unit` — Fast, isolated tests with no external dependencies.
- `@pytest.mark.integration` — Tests requiring KùzuDB and potentially environment variables.
- `@pytest.mark.e2e` — Requires `RUN_LIVE_E2E=1`, hits real endpoints for full system testing.

## 5. Secrets Management in CI
- **GitHub Secrets:** `XKIRO_API_KEY`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, `HF_TOKEN`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`
- **Security Rule:** NEVER echo secrets in CI logs.
- Use environment-specific secret sets for staging vs. production.

## 6. Docker Build & Deploy
- **Dockerfile:** Based on `python:3.12-slim` + `tesseract-ocr`.
- **AntDeploy Config:** `.antideploy.json`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn` via `host_inference/hostapp/wsgi.py`
- **Health Check Endpoint:** `/api/readiness`

## 7. Known CI Debt (HONEST STATUS)
- **13 integration test failures** — Caused by outdated mocks, missing JSON artifacts, and baseline drift. Must be fixed before CI can be fully green.
- **~385 magic numbers** remaining in legacy modules.
- **7 root shim files** need retirement.
- Integration tests require fixture reconciliation with the current KùzuDB schema.

## 8. Post-Deploy Validation Script
Executed automatically after deployment:
1. Hit `/health` endpoint to verify service is up.
2. Hit `/api/readiness` to verify corpus is loaded and graph is initialized.
3. Send a test query via `/api/chat` and verify the SSE response stream.
4. Verify the graph endpoint returns valid nodes.
5. Verify the library endpoint returns the expected book catalog.
6. Verify rate limiting is functioning as expected.

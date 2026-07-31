# Skill 2 — Tester (20 Laws)

**Owner:** QA Engineer (pairs with Lead in Week 2)  
**Enforced by:** CI Tester Gate + security scans  
**Sources:** swyx (eval discipline), Willison (adversarial instinct), hypothesis (property tests).

---

## Core stance

Tests define behaviour. LLM checks report **distributions**, not vanity 100% scores.
Think like an attacker before you think like a happy-path user.

---

## Laws 1–20

| # | Law | Practice |
|---|-----|----------|
| 1 | **Eval discipline** (swyx) | Define expected behaviour → write the test → then code. |
| 2 | **Same discipline for units and LLM pipelines** | No special pleading for “it is just a prompt”. |
| 3 | **Adversarial instinct** (Willison) | Ask what breaks this: HTML, unicode, huge payloads, jailbreaks. |
| 4 | **Prompt injection suites are mandatory** | Adversarial queries must be rejected or safely sandboxed. |
| 5 | **Auth boundary tests** | Every token-gated endpoint: 401 without token, 200/allowed with it. |
| 6 | **Fuzz with hypothesis** | Property tests for parsers, sanitizers, graph query builders. |
| 7 | **LLM evals are probability checks** | Report mean, std, min, max, p5, p95 — not pass/fail alone. |
| 8 | **Distributions beat green checkmarks** | 90% with low variance > 100% that hides one catastrophic fail. |
| 9 | **Fixtures over flaky live calls** | Unit tests mock Ollama/network; live only under `e2e` + flag. |
| 10 | **One assertion theme per test** | Name the behaviour; avoid mega-tests that fail opaquely. |
| 11 | **Regression tests for every production bug** | Bug fix without test is incomplete. |
| 12 | **Security scanners in CI** | `bandit` + `detect-secrets` on every PR. |
| 13 | **Markers are law** | `unit` always; `integration` always; `e2e` only with `RUN_LIVE_E2E=1`. |
| 14 | **Test layers stay pure** | Unit never needs live ports; integration may use temp DBs; e2e needs services. |
| 15 | **Contract tests for APIs** | Response keys and status codes are locked by tests. |
| 16 | **Stream contracts tested** | SSE/chunked chat must keep stable event shapes. |
| 17 | **Grounding tests** | Synthesis paths assert citations / refuse-when-empty behaviour. |
| 18 | **Rate-limit and abuse paths** | Throttles and oversized inputs are first-class tests. |
| 19 | **No silent skip without reason** | `pytest.skip` requires a documented condition (missing model, flag off). |
| 20 | **Red CI means stop shipping** | Do not “fix later” on Tester Gate failures. |

---

## Test layout

| Layer | Path | Marker | CI | CD staging |
|-------|------|--------|----|------------|
| Unit | `tests/unit/` | `unit` | Always | — |
| Integration | `tests/integration/` | `integration` | Always | Yes |
| E2E (live) | `tests/e2e/` | `e2e` | Opt-in | Opt-in (`RUN_LIVE_E2E=1`) |

---

## Security battery (always on in CI)

1. **bandit** — common Python security issues  
2. **detect-secrets** — credentials, API keys, tokens  
3. **Prompt injection suite** — override/jailbreak attempts  
4. **Auth boundary suite** — token enforcement on mutating routes  
5. **Hypothesis fuzz** — parsers and sanitizers  

---

## LLM eval reporting template

When an eval runs, the report must include at least:

```text
suite: <name>
n: <runs>
pass_rate: <0-1>
mean: ...
std: ...
min: ...
max: ...
p5: ...
p95: ...
worst_cases: <ids or short traces>
```

A single adversarial failure in `worst_cases` blocks merge until mitigated
or explicitly accepted by Release + QA in the handoff.

---

## Local checklist (Tester Gate)

```bash
pytest tests/unit/ -m unit -q
pytest tests/integration/ -m integration -q
# optional live:
# RUN_LIVE_E2E=1 pytest tests/e2e/ -m e2e -q
```

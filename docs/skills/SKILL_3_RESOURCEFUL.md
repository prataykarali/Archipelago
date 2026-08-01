# Skill 3 — Resourceful (20 Laws)

**Owner:** ML Engineer (pairs with Lead in Week 3)  
**Enforced by:** Model/config review + eval discipline (with QA)  
**Sources:** Howard (prototype first, fine-tune last), Willison (search before write, open source), smaller-model + better-prompt heuristic.

---

## Core stance

Constraints are a feature. Prefer the smallest model, the existing library,
and a notebook prototype before any heavy machinery.

---

## Laws 1–20

| # | Law | Practice |
|---|-----|----------|
| 1 | **Prototype in a notebook, fine-tune last** (Howard) | End-to-end baseline before optimisation. |
| 2 | **First working version is the baseline** | Measure against it; do not rewrite from myth. |
| 3 | **Search before you write** (Willison) | Repo, stdlib, existing deps — then maybe new code. |
| 4 | **Open-source instinct** | Prefer OSS; commercial services need a written justification. |
| 5 | **Smaller model + better prompt** | `qwen3.5:0.8b` default; upgrade only with eval proof. |
| 6 | **Constraints produce creativity** | Limited RAM/context → better retrieval and routing. |
| 7 | **Do not add a dependency you can write in <100 lines** | Thin wrappers over bloat. |
| 8 | **Corpus hygiene** | Stream from canonical public sources; never commit copyrighted PDFs. |
| 9 | **Embeddings are optional weight** | Aura/large embeds only behind `ARCHIPELAGO_LOAD_AURA=1`. |
| 10 | **Prompt craft before fine-tune** | Exhaust prompt + retrieval improvements first. |
| 11 | **Fine-tune needs a case** | Data volume, eval gap, and rollback plan required. |
| 12 | **Reuse ranking/routing primitives** | Extend `routing`, `ranking_seeds`, catalog bridges — do not fork. |
| 13 | **Cache expensive work** | Embeddings, catalog matches, graph neighborhoods — with invalidation. |
| 14 | **Prefer structured retrieval over chatty LLM** | Library facts from graph/catalog when possible. |
| 15 | **One experiment, one branch** | Keep experimental notebooks/scripts out of production packages. |
| 16 | **Document model assumptions** | Context window, temperature, stop behaviour in config/docs. |
| 17 | **Graceful degradation** | If Ollama is down, structured answers still work where possible. |
| 18 | **Eval the change that “feels better”** | Subjective quality is not a merge criterion. |
| 19 | **Delete failed experiments** | Or quarantine under `scratch/` — do not leave half-wired paths. |
| 20 | **Resource budget is product** | Latency, RAM, and disk are user-facing; treat them as features. |

---

## Default stack (pilot)

| Resource | Default | Notes |
|----------|---------|-------|
| Chat / synthesis model | `qwen3.5:0.8b` via Ollama | Override only with eval evidence |
| Embeddings | off unless `ARCHIPELAGO_LOAD_AURA=1` | Optional, larger |
| Graph | Kuzu (`okf` packages) | Schema changes reviewed |
| Catalog | bridge/ranking modules | Prefer catalog hits for library queries |
| New Python deps | last resort | Justify in PR body |

---

## Decision ladder (before adding complexity)

```
1. Is there already a function/module for this?
2. Can a better prompt or better retrieval fix it?
3. Can a smaller structured rule/gate fix it?
4. Can a tiny pure-Python helper (<100 lines) fix it?
5. New dependency / larger model / fine-tune — only now.
```

---

## Local checklist (Resourceful Gate — manual + eval)

```bash
# Prove the smaller path still wins
pytest tests/unit/ -m unit -q -k "routing or ranking or grounded or citation"
# Document model + prompt change in PR
# Attach eval distribution if LLM behaviour changed
```

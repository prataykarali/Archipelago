# HANDOFF — 2026-07-25 · 3 Systemic Bugs (company_bugs plan)

## What was built
Fixed the three Archipelago bugs from `company_bugs/plans/fix_archipelago_3_bugs.md`
using the company agent framework (plan → implement → QA harness loop).

| Bug | Symptom | Root cause | Fix |
|-----|---------|------------|-----|
| 1 | LLM cut mid-sentence | `num_predict > free` context; prompt over-count at 4 chars/token | Honourable budget + 4.5 scale + CTX safety 192 |
| 2 | Only 2–3 page links | Prompt under-ask + strict paragraph cleanse + no sparse top-up | Ask 5–10; permissive ground; top-up to ≥5 |
| 3 | Paper cards ~50% missing | `innerHTML` wipe after finalize + early-return rail + null page | Remount rail; normalize page/url payload |

## Files changed
- `archipelago/inference/stream_budget.py`
- `archipelago/inference/synthesis.py`
- `archipelago/inference/citations.py`
- `archipelago/inference/reply_styles.py`
- `ui/chat/index.html`
- `tests/unit/test_three_bugs_fix.py` (new)
- `scripts/qa_three_bugs_harness.py` (new)
- `company_bugs/plans/fix_archipelago_3_bugs.md` (status updated)

## Test results
```
65 passed  (three_bugs + citations + reply_styles + streaming + stream_contract + chat_ui + latency + grounded)
qa_three_bugs_harness.py → 39/39 PASS across 3 rounds
```

## What the next pair should know
- Restart `serve.sh` before manual UI smoke — chat UI is static-served from `ui/chat/index.html`.
- Do **not** reintroduce `max(MIN_NUM_PREDICT, free)` in `stream_token_budget`; that is the truncation bug.
- `appendEvidenceRail` must remain remove-then-remount; early-return-on-existing is the card race.
- Harness: `python scripts/qa_three_bugs_harness.py --verbose`

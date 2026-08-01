# HANDOFF — 2026-07-25 · Lead Engineer + Frontend Engineer
## What was built
**Full end-to-end LLM response streaming fix.**

### Root causes addressed
| # | Root cause | Files changed |
|---|-----------|---------------|
| 1 | Static routes (`identity`, `help`, `small_talk`, `general_chat`, `not_indexed`, `onboarding`, and graph fallback) yielded one giant string → instant DOM paint | `archipelago/inference/routes_chat.py` |
| 2 | `consumeTextChunk` used `assistantText` (last-rendered lag) to accumulate static chunks → chunks overwrote each other mid-animation | `ui/chat/index.html` |
| 3 | `_shouldReplaceFinal` at `STREAM_DONE` compared against stale `assistantText` instead of the live accumulated buffer | `ui/chat/index.html` |
| 4 | Dangling `[S` / `[S1:` fragments (model emits incomplete citation brackets mid-stream) visible in DOM | `ui/chat/index.html` |

### Changes
#### `archipelago/inference/routes_chat.py`
- Added `_stream_text_in_chunks(text)` helper (inside `api_chat`) — splits text by whitespace into ≤20-char chunks, yields word-by-word.
- `stream_reply` now calls `yield from _stream_text_in_chunks(indexed_text)` when Qwen is bypassed (instead of `yield indexed_text`).
- All static-route generators that previously did `yield some_string` now go through `stream_reply(..., preserve_facts=True)` so they use the same chunking path.
- Misc ruff fixes: `RUF005` list concatenation, `RUF003` multiplication sign in comment, `RUF034` useless ternary.

#### `ui/chat/index.html`
- Added `staticStreamBuffer` variable (mirrors `rewriteBuffer` pattern).
- `consumeTextChunk` plain-stream else-branch now appends to `staticStreamBuffer` and calls `typewriter.update(staticStreamBuffer, { forceTypewriter: true })` — clean word-by-word typewriter on all static routes, no instant paint, no stale-text collision.
- `_shouldReplaceFinal` at `STREAM_DONE` now compares against `staticStreamBuffer || assistantText` (correct accumulated text, not lag).
- `staticStreamBuffer` cleared on `[MODEL_REWRITE]`, `STREAM_DONE` (inline), and the `awaitingFinalFrame` path.
- Added trailing-bracket cleanup regex: `processedText.replace(/\[S\d*:?[^\]]*$/i, '')` in `renderMarkdownSafely` — strips `[S`, `[S1`, `[S1:` fragments before DOM render.

#### `tests/unit/test_stream_contract.py`
- `test_static_stream_buffer_accumulates_chunks` — asserts `staticStreamBuffer` presence, accumulation, `forceTypewriter`, and clearance.
- `test_dangling_citation_bracket_stripped_during_live_stream` — asserts regex is present.
- `test_stream_text_in_chunks_splits_properly` — asserts long text splits into multiple ≤30-char chunks, short text stays as-is, empty yields nothing, concatenation is lossless.

## Test results
```
129 passed, 324 deselected
```
(126 existing + 3 new streaming contract tests)

## What was deferred
- **`[STREAM_DONE]`-less static routes** (identity/help do not emit a `STREAM_DONE` frame and never call `_finishStreamUi`). These routes still typewrite correctly via the `reader.done` path which calls `typewriter.flush()`. A future improvement would be to add an explicit `[STREAM_DONE]\nfinal_text` tail to every static route for consistency, but the UI already handles the `reader.done` flush gracefully.
- **Quality gate magic-number / file-size / dependency-direction violations** — these are pre-existing and tracked separately. No new violations introduced.

## What the next pair should know
- All static text now streams word-by-word from the **server side** (≤20-char chunks). If a new interceptor is added, always use `yield from stream_reply(text, preserve_facts=True)` — never a bare `yield text`.
- `staticStreamBuffer` is the UI's source-of-truth for in-progress static text during a stream. Clear it whenever you reset the stream state.
- The `forceTypewriter: true` flag on `typewriter.update(...)` is required for any path that wants live word-by-word animation — without it the 180-char instant-paint threshold kicks in.

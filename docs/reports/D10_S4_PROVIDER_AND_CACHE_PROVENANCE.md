# D10-S4 Provider and Cache Provenance

## Candidate scope

Base commit: `bcb4989cbd72f47e66785e40cc76a8815c9e4668` (`d10-s3-candidate-runtime`). The candidate code revision is `722b0c58c7fc4d4432da7ada515a7270fba463b3`. This report covers local code and tests; no hosted diagnostic response was captured because the observed authenticated chat flow was blocked by session expiration.

## Execution path and trace changes

- `Engine.stream_chat` selects XKIRO first, then NVIDIA when configured and the first stream has no token. A non-polishable route uses deterministic output. If configured providers yield no token, the grounded draft is returned with `provider_unavailable_fallback`. The local ingestion model is not selected by this hosted answer path.
- The first stream metadata now reports the **selected** provider, model, synthesis mode, template ID and whether template guidance was actually sent to the provider. The selected template is recorded even when it was not used in generation.
- The chat route annotates metadata with the runtime release environment SHA (or `unknown`), graph content hash, route, source document IDs, canonical passage IDs, and `miss_no_reuse`. Unknown or absent passage IDs stay absent rather than being inferred from page numbers.
- The Inspector Trace tab displays those values and separates passage provenance, claim support and reader-page verification. A provenance-verified chunk still says `claim_support_status: not_assessed`; browser page verification remains false until actually tested. General explanations carry `explanation_status: general_explanation`.
- The Trace no longer shows a fabricated `0.42 s` latency or a deterministic provider before provider selection. It displays measured retrieval and provider time to first token where available. Provider duration and total completion time are logged by the route but are **not yet exposed in the initial stream metadata** because completion happens after that frame. These fields are pending, not represented by time to first token.
- The Graph Inspector's `REQUIRES` heading now says indexed relationships are pending review. An indexed graph reference is not labeled verified evidence solely because it exists in the graph.

## Cache audit

`/api/chat` calls `record_request()` and `record_miss()` for every request and does not call the answer cache read or request deduplication path. Both chat response branches set `Cache-Control: private, no-store, no-cache, must-revalidate` and `Vary: Authorization, Cookie`. A source search found no service worker registration or Cache API use in the chat UI. This establishes the current source-code behavior only; an authenticated browser/network capture is still needed to rule out intermediate cache behavior and compare identical queries, paraphrases, fresh sessions and separate authorized accounts.

## Checks and limits

- `ruff check` on changed Python modules and the focused test: passed.
- `pytest -q tests/unit/test_d10_s4_provider_trace.py tests/unit/test_citation_integrity_policy.py`: **12 passed**.
- Existing `test_host_llm_stream_failover.py`: 1 failure in a pre-existing expectation that a short live answer will be the final chunk; the engine intentionally appends the grounded draft when live text is short. This was observed before these candidate edits and was not changed here.
- No authenticated hosted request, provider response, intermediary-cache trace, browser service-worker inspection, or cross-account comparison was performed in this subtask. The provider API and cache claims therefore remain **unverified live**.

## Reviewer verdict

**HOLD for live provenance sign-off.** Run the six authenticated diagnostics after the session fix, capture redacted response metadata and network headers, then compare identical queries, paraphrases, new sessions and two authorized accounts. Do not infer live model generation from the displayed engine preparation latency.

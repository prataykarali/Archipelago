# Follow-up repairs — chat transport, reader honesty and visible UI faults

Scope: repair the previously diagnosed section-2 issues and push to the existing review branch. No merge, deployment, corpus publication, credential changes or production configuration edits.

## Delivered

| Issue | Repair | Verification / limitation |
|---|---|---|
| Raw metadata/error JSON in ordinary chat | Separate transport parser; JSON error/envelope handling; bounded metadata; UTF-8 and control-marker chunk handling; complete final-frame buffering; safe text-only errors | Node boundary tests and eight controlled responses in the real browser. Intended JSON/code answers remain intact. |
| Inspector initially looks like raw JSON | Human-readable response, route, corpus, retrieval and privacy summary; raw JSON behind a second disclosure | Browser checked readable first view and explicit raw-debug expansion |
| Pearson page fragments do not navigate reliably | Book-specific manual handoff: open the book, then select the cited page; citation clicks use the handoff instead of inventing external page anchors | Gateway and resolver tests. This is an honest fallback, **not repaired or verified automatic external page navigation**. |
| False authenticated/verified resolver claims | Metadata-only resolver returns `verified=false`, `access_verified=false`, `page_verified=false`, `status=unverified`, no verification timestamp; HTTPS Pearson-host allowlist | Deterministic tests. Legacy `working` remains URL availability for compatibility; it is explicitly not access verification. |
| HF delivery masks failures / trusts non-PDF responses | Manifest-approved path only; ambiguous basename rejected; configurable dataset ID; distinct unavailable/denied/not-found/network states; PDF signature checked before response; no-store; upstream streams closed | Mocked HTTP and synthetic two-page browser tests, not live private-dataset access |
| PDF reader silently substitutes page 1 | Out-of-range page is an explicit error; actual PDF page count and available labels used; navigation updates raw link/hash | Synthetic page 2 rendered; page 99 refused rather than substituting page 1 |
| Missing local library stays missing even after access configured | Bootstrap retries missing catalogue/manifest independently of an existing graph; a large demo fixture does not suppress restoration; invalid downloads cannot replace usable data | Synthetic restoration tests. No private library was downloaded in this change. |
| Blank avatar, glyphs, header wrapping | Failed/preload-failed clips fall back to existing original librarian video; icon-font specificity corrected; invalid embedded bold-font declaration fixed; graph heading wraps without splitting short badge | Browser confirmed loaded video frames and icon font; mobile and completed-graph screenshots. Original files are not replaced. |

## Still blocked / not claimed complete

- Private HF access, canonical dataset ID confirmation, approved manifest and real PDF/page mappings are not available through a secure connection. Previously pasted credentials were not reused.
- Full Pearson catalogue and graph restoration still require the authorized originals or configured source access.
- Missing original fonts/media remain missing. Existing artwork is used as a fallback, not claimed as restoration of the original clip sequence. Some original font/media requests can still fail.
- Pearson automatic exact-page navigation remains unsupported/unverified for the previously sampled reader; reflowable-reader behavior is not certified.
- Local legacy PDF/resolver paths outside the default hosted-local runner have not all been rewritten or live-certified.
- Ingestion/model benchmarks and other unfinished original specifications remain separate work.

## Verification

- Focused Python regression suite: **120 passed**.
- JavaScript transport regression suite: **12 passed**.
- Actual browser: eight controlled chat-response cases, readable inspector/debug expansion, icon font and loaded avatar, synthetic PDF valid/out-of-range pages.
- Actual learning flow: Normal and Personalized modes, four server-graded questions, confidence/preferences, completed graph; **zero JavaScript page errors**.
- Full Python suite: **1,489 passed / 24 failed / 5 errors / 7 skipped**. No newly failing test identities versus the previous tested commit; existing missing-data/legacy failures remain. Focused tests overlap these totals.
- Scoped Ruff, JavaScript syntax, compilation and whitespace checks were run. This is not a repository-wide lint certification.
- Assertions tied to the old parser's source layout and false Pearson page claims were updated to the new contracts; stronger executable boundary/reader tests were added. Tests were not deleted to hide failures.

## Reproduce

```sh
pytest tests/unit/test_learning_sessions.py tests/unit/test_answer_cache.py \
  tests/unit/test_llm_provider_chain.py tests/unit/test_ui_link_integrity.py \
  tests/unit/test_graphier_export.py tests/unit/test_reader_safety.py \
  tests/unit/test_library_restoration.py --timeout=30 -q
node --test tests/js/chat-transport.test.mjs
python scripts/run_local.py --port 5151
```

Optional browser checks require `playwright` and `reportlab` in the developer environment; neither is added as a product runtime dependency:

```sh
python scripts/smoke_response_ui.py --url http://127.0.0.1:5151 \
  --chrome /path/to/chrome --output /tmp/archipelago-response-check
python scripts/smoke_learning_ui.py --url http://127.0.0.1:5151/chat \
  --chrome /path/to/chrome --screenshot /tmp/learning.png
```

The response smoke uses controlled transport failures and a generated two-page PDF. It does not download or expose private textbook content.
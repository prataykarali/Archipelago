# Remaining-issue repair batch — 2026-10-04

Review branch: `restore/production-readiness-20261004`. No default-branch merge or deployment is authorized by this batch. Existing visual assets and deployment configurations are excluded.

## Delivered code

### Grounding, routing and provider privacy
- Repair late-bound routing collaborators after package splitting, including correct intent classification for maximum-likelihood curriculum requests. A missing indexed concept still rejects honestly; no replacement graph node or forced wrong anchor is introduced.
- Repair the default Kuzu evidence connection and string-target citation lookup. Remove curated demo reading suggestions from retrieved-evidence citations.
- Enforce real evidence-source citations in offline answers and authoritative streamed completion; interrupted partial drafts are replaced instead of concatenating unrelated fallback text.
- Local synthesis uses bounded allowlisted evidence rather than raw graph notes or learner history: at most eight snippets and 6,000 characters. Preserve restrictive node/source flags, redact sensitive literals, and mark retrieved text as untrusted.
- Do not switch providers once a provider has emitted answer text.
- Repair upload-inventory module compilation and isolate its cache by source path.
- Reject escaping local PDF paths and unknown documents rather than inventing a private-HF redirect.

### Workstation ingestion
- Add bounded CSV, TSV, ODS and XLSX readers, with hardened XML parsing and ZIP expansion limits.
- Validate required titles and copy counts. “On loan” is not “available.”
- Persist explicit call number, barcode, rack, shelf and location fields.
- Execute graph catalogue writes transactionally; report failures honestly. Test append, update, idempotence and rollback against an isolated real Kuzu database.
- Add local Tesseract OCR for scanned PDF pages with bounded image size and per-page timeout. Missing dependencies or unreadable scans fail explicitly.
- Use page-bounded chunks in citation ingestion while preserving the legacy multi-page section-chunk API.
- Never automatically publish an uploaded full document to HF merely because ingestion was requested. Rights-reviewed graph publication remains a separate explicit action.
- Empty/OCR/model extraction failures no longer pretend to be completed ingestion.
- The evaluator only loads approved local model files without executing remote model code.

### Learning memory and resources
- Add **optional**, browser-owned mastery memory: 30-day rolling retention, bounded storage, owner isolation and a functioning “Forget saved learning” control.
- Long-term records retain concept mastery and preference only, not quiz answers, raw history or user identities.
- Restore only relevant current-neighborhood mastery. Fading concepts get a current-session verification opportunity; lifetime counters no longer prevent it.
- Map assessed gaps to physical holdings through exact source/resource IDs, not keyword guesses. Show imported copy counts as a snapshot, not live availability.
- Add a verified-staff aggregate endpoint with minimum cohort five and no individual records. Consent text explains aggregate use. Counts represent consenting browser profiles, not distinct students.
- Keep local/hosted settings APIs and both frontend copies synchronized.

## Verification

- Focused source-repair selection: **132 passed**.
- Comparable unit + integration suite: **1,512 passed / 21 failed / 5 errors / 7 skipped**, versus prior **1,489 / 24 / 5 / 7**. No newly failing comparable test identities; three previous failures repaired.
- Wider `pytest` discovery: **1,526 passed / 21 failed / 5 errors / 19 skipped**. This includes additional root/E2E tests, so it is not the same denominator as the comparable suite.
- JavaScript transport: **12 passed**.
- Actual-browser learning: normal and personalized modes, four server-graded questions, completed graph, no JavaScript page errors.
- Actual-browser memory: opt-in, four saved concepts, reload persistence, UI deletion and guest denial for staff aggregates; no JavaScript page errors.
- Existing response/inspector/PDF browser checks also pass. Transport edge cases are controlled responses; PDF reader cases are synthetic documents.
- Actual local OCR recognized every expected word in **one generated clean English scan**. This is not an institutional OCR accuracy benchmark.
- New-source scoped Ruff, modified-source compilation, JavaScript syntax and diff-whitespace checks pass.
- Repository-wide quality checks still fail **five gates**: lint, types, banned patterns, magic-number heuristic and dependency direction. Checks were not disabled or relaxed.

## Not completed or certified

This is not a production-readiness certification or completion of the original entire scope.

- Private HF access and approved catalogue, manifest, full graph, PDFs, missing LFS data/media and model weights remain unavailable.
- Model evaluation metrics remain unset; the readiness report explicitly says the model directory is missing. No model was retrained, downloaded or benchmarked with fabricated scores.
- No live NVIDIA/XKIRO latency/quality benchmark.
- Automatic Pearson exact-page navigation remains unproven; the prior honest book/manual-page handoff remains.
- No live OPAC connector certification, staff dashboard UI, comprehensive cross-account learning memory or institutional analytics rollout.
- Memory is tied to this browser and authentication-token binding. Clearing browser cookies or rotating an authentication token can make earlier memory inaccessible until retention expires.
- Anonymous minimum-cohort counts are not a differential-privacy guarantee.
- Complete ingestion/model-to-production-graph publication remains unverified without approved models/data.
- `Prataykarali/graphier` has not been published; the old library dataset is unchanged.
- Full repository suite remains non-green. Failures include missing institutional data/models and legacy exact-page/library-size assumptions; those assertions were not rewritten to hide the missing corpus.

## Local use

Hosted inference UI: `python scripts/run_local.py --port 5151`.

Workstation ingestion still runs separately. Install the root Python requirements and the OS package `tesseract-ocr` for scanned PDFs.

Readiness probe:

```sh
PYTHONPATH=. python scripts/check_ingestion_readiness.py \
  --model models/lib_qwen_v44_hf \
  --output /tmp/ingestion-readiness.json
```

This probe checks local model-file presence and synthetic OCR only. Use the existing evaluator with approved weights and labelled evaluation data for actual extraction metrics.

Browser memory settings: expand **Learning memory (optional)** on the mode chooser or normal graph. Opt-in applies to subsequent personalized diagnostics; normal mode does not record assessments.

Staff aggregate API: `GET /api/staff/learning-summary` with a verified authorized Archipelago login. Client-supplied role fields never grant access.
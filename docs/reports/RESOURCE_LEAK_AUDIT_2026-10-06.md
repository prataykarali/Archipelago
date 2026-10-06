# Archipelago resource-leak audit — 2026-10-06

This is a read-only audit of the code paths inspected below. No code fix is claimed by this report. It covers the hosted Flask layer, local ingestion, graph/cache support, SQLite learning state, and relevant chat timers. It does not prove that every runtime dependency or production host is leak-free.

## 1. Executive summary

Three confirmed retention paths exist under repeated use: uploaded spreadsheet quarantine directories are never removed by the intake routes; the hosted answer/retrieval/graph caches retain expired keys; and per-client rate-limit maps retain old clients. The local fetch-policy maps have the same retention pattern when many approved hosts are fetched. Two failure-path cleanup risks merit follow-up. No WebSocket implementation was found in the inspected hosted routes.

## 2. Confirmed resource leaks

| Resource | Where | Evidence | Mechanism and trigger | Impact | Confidence | Recommended fix |
| --- | --- | --- | --- | --- | --- | --- |
| Uploaded spreadsheet files/directories | `archipelago/inference/routes_misc/m09_librarian_intake.py:124–130,173–208` | `_resolve_sheet_path()` creates `mkdtemp`, saves the upload, and returns only its path. Neither `/plan` nor `/apply` has a `finally` that removes the directory. | Every successful multipart spreadsheet preview or apply leaves a new directory under the system temp location, including failed plan/apply calls after the save. | Disk fills over repeated librarian imports; uploaded institutional data persists longer than intended. | High | Own the temporary directory for the request/job and remove it in a `finally`, retaining only an approved durable copy when explicitly needed. |
| Expired in-memory cache entries | `host_inference/cache_service.py:148–151,231–258,306–308,332–373` | Three dictionaries receive entries; reads check TTL but do not delete expired entries, and writes have no maximum size/eviction. | New normalized queries/concepts accumulate for the lifetime of each Gunicorn worker, even after TTL. | Worker RSS growth, more GC pressure, restarts under diverse student traffic. | High | Use bounded LRU/TTL containers or scheduled expiry, with size and eviction metrics. |
| Hosted client-IP limiter keys | `host_inference/hostapp/security.py:125–129,151–163` | `defaultdict` inserts every new IP and timestamp maps receive keys; only deque contents are pruned. | Each distinct client/proxy-supplied IP leaves empty maps after its window expires. | Slow memory growth under many unique clients or spoofable proxy headers. | High | Trust only configured proxy headers, bound the key set, expire inactive keys, or use a shared rate-limit store. |
| Local inference limiter keys | `archipelago/inference/rate_limit.py:25–30,59–63` | `_windows` inserts new client keys and never removes empty entries except global `reset()`. | Long-lived local services retain each unique IP/session key. | Memory growth on a library machine or shared service. | High | Evict empty stale windows with a bounded key policy. |
| Fetch-policy host/robots maps | `archipelago/ingestion/fetch_policy.py:98–100,231–251,339–349` | `_hosts` and `_robots_cache` store new hostnames/robots URLs; TTL changes lookup behavior but does not remove entries. | Many allowed source hosts persist in process memory after expiry. | Memory growth during broad source discovery. | High | Prune expired entries and cap the number of hosts, while preserving deny-all policy and audit evidence. |

## 3. Potential or suspected leaks

| Resource | Where | Evidence | Mechanism and trigger | Impact | Confidence | Recommended fix |
| --- | --- | --- | --- | --- | --- | --- |
| Temporary partial corpus download | `host_inference/hostapp/corpus_bootstrap.py:99–115` | A `NamedTemporaryFile(delete=False)` is moved or removed on the size-cap branch, but the broad exception handler does not unlink it. | An exception after file creation and before `shutil.move()` can leave a partial artifact. | Cold-start disk use, stale sensitive/large file. | Medium | Track the staged path and unlink it in `finally` on every failed fetch. |
| SQLite connections | `host_inference/hostapp/learning_memory.py:30–75`; `host_inference/hostapp/quiz_store.py:26–71` | `with sqlite3.connect(...) as db` manages transactions but does not explicitly call `close()`. | Connection finalization relies on reference collection after each request; exceptions and implementation differences may delay descriptor release. | Potential file descriptor/lock pressure. No persistent growth was measured here. | Medium | Use `contextlib.closing()` around the transaction context or explicit `finally: close()`, then load-test open descriptors. |
| Cache-write thread bursts | `host_inference/cache_service.py:310–328` | Each cache miss starts a daemon thread; requests have a four-second timeout, but there is no queue or worker cap. | A cross-IP cache-miss surge can create many concurrent transient threads. | Short-lived memory/thread pressure and dropped writes at shutdown. This is capacity risk, not a proven permanent leak. | Medium | Use a bounded executor/queue and shutdown drain or write synchronously within a safe budget. |
| PDF metadata handle on early error | `archipelago/ingestion/pdf_io.py:35–42` | `fitz.open()` is closed after metadata extraction, without a `finally` spanning extraction. | An exception in hash/title/edition/page-label extraction before line 42 skips explicit close. | Potential descriptor delay until GC. | Medium | Wrap the PDF metadata read in a context manager or `try/finally`. |

## 4. Safe or correctly managed resources

- `archipelago/ingestion/pdf_chunk.py:99–171` closes its opened PDF in `finally` during page processing; there is a small pre-`try` setup window to examine separately.
- `host_inference/hostapp/corpus_bootstrap.py:99–112` uses a context-managed streamed HTTP response and temporary file on its normal path.
- `archipelago/resolver/check_links.py:46–49` owns a `ThreadPoolExecutor` with a context manager, so workers join on exit.
- `host_inference/ui/js/13-render-horizontal-graph-card.js:291–303` and `host_inference/ui/js/09-patterns.js:108–119,216–231` clear their per-element timers after the element disconnects.
- `host_inference/hostapp/quiz_store.py:36–54` deletes expired sessions and caps row count; `learning_memory.py:51–64` caps consenting owners. These bounds protect row growth, apart from the connection-lifecycle concern above.
- The observed HTTP calls in these paths set timeouts. No evidence of a permanently retained `requests.Session` or WebSocket was found in the inspected hosted code.

## 5. Failure-path and cleanup analysis

Spreadsheet temp files survive both the success path and exceptions after save. A corpus download exception can bypass partial-file deletion. A PDF metadata extraction exception can bypass the explicit close. Cache-write threads have a timeout but are daemonized, so shutdown can discard work; this is durability, not necessarily leakage. SQLite transaction contexts roll back on exception, but explicit connection closure is not visible.

## 6. Resource lifecycle map

```text
Librarian upload → mkdtemp/save → parse/apply → no temp cleanup (confirmed)
Chat query → memory/Supabase cache → TTL check → no local eviction (confirmed)
Client request → per-IP deque/maps → deque prune → key retained (confirmed)
Source fetch → robots/host map → TTL check → key retained (confirmed)
PDF chunk → fitz.open → try/finally close (mostly safe)
Diagnostic/memory call → sqlite connect → transaction context → eventual GC close (suspected)
HF boot fetch → streamed response + temp file → move on success / possible orphan on error
Browser graph animation → interval → clear on disconnect (safe in inspected modules)
```

## 7. Production impact

The immediate privacy and disk priority is spreadsheet temp cleanup. Unique questions, client keys, and source hosts can grow process memory without a configured cap. The impact has not been quantified against the actual institutional concurrency profile; a repeated-operation load test should measure RSS, open FDs, temp-file count, and thread count before and after fixes.

## 8. Evidence and reproducibility

The source locations above are exact line/function anchors in the `codex/production-hardening` checkout on 2026-10-06. Code review confirms retained mappings and missing cleanup; this audit did not run destructive upload loops against production or inspect process heap snapshots. Confidence is highest where the control flow contains no cleanup route at all.

## 9. Recommended fixes

Prioritize temp-file cleanup, then bounded caches and limiter maps, then failure-path `finally` cleanup. Test each with repeated operations and exceptions. Keep these engineering fixes separate from this read-only audit report and rerun the audit after deployment.

## 10. Items that cannot be verified here

- Production RSS/FD curves, actual concurrent worker count, and whether the platform restarts workers before growth becomes material.
- Closed-source AntDeploy/Fly/Supabase/Vercel connection-pool behavior and browser lifecycle on every device.
- Whether all PDF/OCR library dependencies release native memory under cancellation or malformed data.
- Whether any server-side process outside the inspected modules runs extra timers, sockets, or long-lived sessions.

## 11. Overall resource-safety assessment

The system has several high-confidence retention bugs and is not yet proven safe for sustained institutional traffic. Managed DB and object-store operations were not found to leak in the reviewed happy paths, but the local process and upload lifecycle need remediation and measured regression tests before a production-readiness claim.

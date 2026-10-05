# Local learning workspace

This change runs locally and does **not** deploy or change Antideploy configuration.
It adds private adaptive diagnostics to the existing UI and both local inference API entrypoints.
The smallest runnable setup uses the standalone Flask app; the full ingestion workstation remains a separate existing stack.

## Quick start (Python 3.12 recommended)

```bash
git fetch origin
git switch restore/production-readiness-20261004
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r host_inference/requirements.txt
python scripts/run_local.py
```

Open **http://127.0.0.1:5151/chat**. The development runner intentionally accepts loopback bindings only.
It is not a production server and must not be exposed publicly with authentication disabled.

No NVIDIA or XKIRO key is required: the app falls back to its indexed, grounded response.
A fresh checkout may start with the **84-concept fixture**, not the complete library.
Check `http://127.0.0.1:5151/api/readiness`: `corpus.source` and `corpus.full` disclose this.

### Visual assets

Install Git LFS, then run `git lfs pull`. Do not delete or replace missing assets.

During validation, 23 unique public LFS objects (100 file paths) were fetched and verified against their SHA-256 pointers. Fifteen other unique objects returned 404 from the public media endpoint, including avatar videos, fonts and some graph artwork. This does not prove whether they are missing server-side or inaccessible through that endpoint; restore/check them from the original author checkout with `git lfs fsck` / `git lfs push --all origin` if necessary. All committed visual asset pointers are unchanged.

### Full local ingestion workstation

The existing `Makefile`, `scripts/ops/serve.sh`, and ingestion modules are retained.
Use their existing setup with the full root requirements and your local corpus/model.
The standalone local runner reports `ingestion: false`; it does not pretend that uploads, OCR, a trained model or production holdings are provisioned.

The local diagnostic routes reuse the same server-authoritative grading/session protocol through `archipelago.personalization_bridge`. Existing unrelated local services and APIs remain in place.

## What to try

1. Say **hi**: a brief greeting, no unrelated graph.
2. Ask **I want to learn RAG**: choose Normal or Personalized.
3. Normal: inspect the ordinary graph without a required quiz.
4. Personalized: select an answer, confidence and optional learning preference.
5. Continue until the server reports completion; click **Explore Your Personalized Knowledge Graph**.
6. Inspect an edge label and a node's evidence/“why” explanation.
7. Open the optional **Query Inspector** for the actual retrieval/context trace.

The graph uses existing prerequisite edges, not an invented target-centered star.
Unassessed nodes stay missing. Three confident checks covering available prerequisite depths can stop the diagnostic; ten is a hard ceiling, not a target. A very small neighborhood can finish sooner rather than generate fake questions.

## Privacy and compatibility

- Server stores issued questions/answer keys and grades only its own question IDs.
- Browser receives one question at a time, without the answer key until grading.
- SQLite sessions are browser/login bound, expire after one hour, and are capped at 1,000.
- Expired sessions become inaccessible immediately; physical cleanup occurs on the next session creation. There is no long-term learner profile or opt-in cross-day memory in this release.
- `ARCHIPELAGO_QUIZ_DB` can select a local database path outside the repository.
- Diagnostic, first-person and learner-state chat requests bypass shared answer caching. Authenticated public knowledge questions can reuse the versioned answer cache.
- Client history/mastery fields are not authoritative.
- Only bounded retrieved academic summaries can reach inference providers; credential-like strings, contacts and private-marked nodes are filtered. Inventory and learner history are excluded. This is a defensive filter, not a formal DLP guarantee.
- Automatic provider order is XKIRO → NVIDIA. Existing explicit provider pinning remains supported.
- The legacy `/api/chat/verify-mcq` practice compatibility endpoint is retained; it is **not** used as authoritative mastery evidence by the new adaptive flow. It must not be used for grades or access control.

## Tests

```bash
python -m pip install pytest pytest-timeout kuzu PyJWT cryptography
pytest tests/unit/test_learning_sessions.py tests/unit/test_answer_cache.py \
  tests/unit/test_llm_provider_chain.py tests/unit/test_ui_link_integrity.py \
  tests/unit/test_graphier_export.py --timeout=30 -q
```

The dedicated `Local learning regression` workflow performs those tests and startup checks without deploying.

Optional real-browser smoke test:

```bash
python -m pip install playwright
playwright install chromium
python scripts/smoke_learning_ui.py
# Or use a system Chrome:
python scripts/smoke_learning_ui.py --chrome /path/to/google-chrome
```

This exercises both modes, confidence/preference controls, server grading, the completed graph and JS error detection. It does not validate every source PDF or unavailable video.

## Graphier export: review first

Create a local rights manifest listing only document IDs whose derived content you have reviewed and are authorized to publish:

```json
{"approved_documents": ["papers/your-authorized-source.pdf"]}
```

```bash
python scripts/export_graphier.py \
  --graph path/to/okf_graph.json \
  --rights-manifest path/to/reviewed-rights.json \
  --output /tmp/graphier-export
```

The offline export strips raw passages, unknown fields, private-marked nodes and dangling edges. Every contributing source for a node must be approved. Review its summaries and metadata before publication; automatic detection is not a rights determination.

Only an explicit `--publish` with `HF_TOKEN` and `huggingface_hub` installed writes to **Prataykarali/graphier**. A newly created dataset is private; an existing dataset's visibility is retained. **Library_books is never modified.** No dataset publication was performed as part of this change.

See `docs/reports/LOCAL_RESTORATION_2026-10-04.md` for measured results and remaining work.
## Reader configuration and follow-up fixes

Set `HF_DATASET_REPO` to the exact authorized `owner/dataset` and provide a
read-only `HF_TOKEN` through your local secret environment (never Git or chat).
The reader default is `Prataykarali/library_books`, matching the supplied URL;
its casing/existence still needs authorized confirmation. Bootstrap runs only
when the dataset is explicitly configured.

Expected approved exports: `okf_graph.json`, `catalogs/pearson_bookshelf.json`,
and `library_manifest.json` with `hf_paths` naming real PDF files. The bootstrap
validates exports and retries missing catalogue/manifest independently of the
graph. Missing access is a blocked restoration, not an empty library reported
as fully restored.

Pearson citations open a book-specific handoff with manual page instructions.
Constructed URLs and catalog metadata are not authenticated page verification.
The internal PDF reader rejects out-of-range pages rather than substituting
page 1; PDF page indices and printed page labels may differ.

See `docs/reports/FOLLOWUP_REPAIRS_2026-10-04.md` for repairs, browser commands
and the remaining missing-originals/access limitations.


## October 4 remaining-issue repairs
See `docs/reports/REMAINING_REPAIRS_2026-10-04.md` for tested scope and unresolved blockers.

- Optional 30-day browser mastery memory is under **Learning memory (optional)**. It saves mastery/preference, not answers. **Forget saved learning** deletes both consent and records.
- Scanned PDF ingestion requires local `tesseract-ocr`; table intake supports CSV/TSV/ODS/XLSX. Root Python requirements include XLSX and hardened XML support.
- Workstation ingestion no longer automatically uploads full documents to HF. Publication requires a separate approved rights-reviewed export.
- Verified staff can request aggregate-only `/api/staff/learning-summary`; no staff dashboard or live OPAC connector is certified.
- Model weights and institutional library exports are not present. Error handling/readiness probes are not successful model/library restoration.

# Source Lifecycle — when a book leaves the library

**Code:** `archipelago/resolver/source_lifecycle.py`,
`archipelago/resolver/ingest_proposals.py` ·
**Tests:** `tests/unit/test_source_lifecycle.py` (56 cases)

The library's catalogue is not static. Pearson lapses a subscription, a
Hugging Face repo removes a file, a licence expires. When that happens the
graph must **stop asserting things from a document the institution no longer
holds** — and say so plainly instead of leaving a citation that 404s.

---

## The three states

| State | Meaning | Citable? |
|------|---------|----------|
| `verified` | Reachable at the last check | Yes |
| `withdrawn` | Confirmed gone upstream | **No** |
| `unknown` | Never checked, or the check itself failed | Yes |

The distinction that carries the weight: **only an authoritative negative
retires a source.** A `gone` / `not_found` / `404` verdict withdraws. A
`timeout`, DNS failure, or missing credential is *inconclusive* and leaves the
book citable, because an unreachable check is not evidence of withdrawal.

The asymmetry is enforced in both directions, because either error is
embarrassing in a different way:

- a timeout must **not** silently delete a book from the record;
- a failed re-check must **not** resurrect a withdrawn title.

Both are pinned by tests.

---

## What happens when a title is withdrawn

```bash
# Record the check (in production this comes from a provider sweep)
record_check(
    "isbn:9789332526532",
    verdict="gone",
    provider="pearson",
    message="HTTP 410 Gone",
    metadata={"title": "Digital Signal Processing, 4e",
              "isbn": "9789332526532",
              "doc_id": "textbooks/DSP_4e.pdf"},
)
```

Three effects, in order of how much they matter:

1. **The concept survives.** Knowledge supported by another live document keeps
   answering. A title's withdrawal is not a reason to delete what the library
   still knows.
2. **Citation falls back.** `best_live_source()` skips the retired document and
   picks the next best live passage for that concept.
3. **The reply says so** when nothing live remains — see below.

Every citation record gains `withdrawn: bool` and, when true, an empty URL plus
a `notice`. The chat payload adds `withdrawn_notice` / `text_override` so the
UI replaces the answer rather than rendering a source list of dead links.

Reply copy (deliberately factual — it does not claim the book was "lost" or
speculate about why):

> This title is no longer in the library's records. It was withdrawn from
> pearson, so it cannot be cited or opened from here.

### Four citation paths, all covered

A withdrawal check is only as good as the paths that honour it. All four are
covered, and two of them were found leaking during this work:

| Path | Mechanism |
|------|-----------|
| Graph citations | `LibraryGraph.cite_record()` → `best_live_source()` |
| Chat payload | `engine/answer.py` sets `withdrawn_notice` |
| **Cache replay** | notice **re-derived** on every replay |
| **Demo cards** | `_mark_withdrawn()` — they hard-code citations and bypass `cite_record` |

The cache case is the subtle one: an answer cached *before* a withdrawal still
carries that citation, so the notice is recomputed from the sources rather than
trusted from the cached payload. A source can be withdrawn after the answer was
written.

---

## Tombstones

Withdrawal is not deletion. Each tombstone snapshots what was known while the
source was live:

```json
{
  "title": "Digital Signal Processing, 4e",
  "isbn": "9789332526532",
  "doc_id": "textbooks/DSP_4e.pdf",
  "withdrawn_at": "2026-10-02T07:41:12+00:00",
  "last_verified": "2026-09-15T09:02:44+00:00",
  "reason": "HTTP 410 Gone"
}
```

This keeps the retirement auditable and lets a re-acquired title be restored
without a full re-ingest. Storage: `data/source_lifecycle.json` (gitignored,
bind-mounted in the appliance).

```bash
python -m archipelago library sources                    # everything
python -m archipelago library sources --withdrawn-only   # retirements only
```

---

## New books: ask, don't ingest

The opposite direction. A provider sweep finds titles the institution is
*entitled* to but the graph does not hold:

```bash
python -m archipelago library propose
# New proposals: 40
# Awaiting librarian review: 40
```

**Nothing is downloaded or ingested.** Ingesting a commercial textbook is a
licensing decision, not a technical one — which is why the ingestion worker
already distinguishes `toc_only` from `full`. New proposals default to
`toc_only`: structure and front matter only.

Fingerprints are ISBN-based, so a retitled book is still one book and one
question, and a recorded decision survives re-sweeps:

```python
from archipelago.resolver.ingest_proposals import decide, fingerprint_for

key = fingerprint_for("pearson", "Digital Signal Processing, 5e", "9789332526532")
decide(key, "approved", license_mode="full")
decide(key, "declined", note="physical copy not yet received")
```

A declined book is never re-asked. Only `approved` proposals are offered to the
ingestion worker.

---

## Provider sweeps

`reconcile()` applies a batch of check results to the ledger:

```python
from archipelago.resolver.source_lifecycle import reconcile

reconcile(
    live_ids=held_ids,
    checked={
        "isbn:9789332526532": ("gone", "pearson", "HTTP 410 Gone"),
        "isbn:9781292014111": ("verified", "pearson", ""),
        # a timeout for a third id simply leaves its state untouched
    },
)
```

**An id absent from `checked` keeps its current state.** Absence of a check is
not evidence of withdrawal — this is why the sweep reports `newly_withdrawn`
separately from the total, so a repeated sweep is a no-op.

Wiring a real Pearson or Hugging Face probe is the remaining work: both
connectors exist (`archipelago/ingestion/pearson_connector.py`,
`archipelago/storage/hf_remote.py`) and need to map their responses onto
`verdict` codes. That mapping must be deliberate — an over-broad mapping is
exactly how a library accidentally deletes its catalogue.

---

## Operational notes

- **Never git-commit the ledger.** It is institutional state that changes on
  every sweep; it is gitignored and bind-mounted.
- **Back it up with the corpus.** Without it the library forgets which sources
  were withdrawn and will start citing dead documents again.
- **Credentials never belong here.** The ledger records *availability*, not
  access. Retrieving a withdrawn title's content uses the licensed connector
  with credentials the operator already holds — see
  [`WEB_FETCH_POLICY.md`](WEB_FETCH_POLICY.md).
# Handoff — 2026-10-05

## Built

- Started from the exact observed hosted source commit (`554c8df`) in an
  isolated checkout. The earlier `archipelago3` working tree and its uncommitted
  work were preserved.
- Removed shared login credentials and quick-login buttons from both copies of
  the landing and login pages. Added the user-supplied IEM and UEM marks without
  changing the cinematic hero or other visual assets.
- Made production Supabase authentication mandatory even if a stale host setting
  says otherwise. Public reading/chat routes remain governed by their explicit
  allowlist; the local development setting remains separate.
- Routed concept questions through the academic graph instead of treating one
  matching paper-title token as a source request. Explicit paper/book and page
  requests still use the source route, with the requested page retained.
- Removed a false physical-copy claim from Pearson e-book catalogue cards.
  Read requests no longer trip the write burst limiter by themselves.
- An authenticated Pearson reader session opened the correct book, but a fresh
  URL ending in `/page/35` displayed page 22. Moving to page 35 in the reader
  did not update the URL. Chat citations now route direct Pearson URLs through
  the book-specific handoff and keep the page as an instruction; they no longer
  manufacture a deep link the reader ignores.
- Shared answer caching now works for ordinary authenticated academic queries.
  First-person, sensitive and learner-state queries still bypass it. Cache
  keys fingerprint the loaded graph and book catalogue, malformed/expired
  Supabase rows are misses, and persistence requires a server-side key.
- Corrected the library-computer Compose graph export mount: the worker writes
  through a checked link to the shared directory volume, and the graph and
  sync services read the same file. The graph port now binds to loopback with
  staff auth and a restricted origin in the Compose configuration.
- Removed literal shared-account values from tracked test and evaluation
  files. The existing repository history may still contain them, so provider
  rotation remains necessary.

## Verification

- Focused clean-checkout suite: 27 passed across release policy, new
  regressions, and rate-limit tiers. Ruff lint/format and `git diff --check`
  passed on touched Python files.
- Existing working-tree suite before the isolated branch: 1,451 passed, 7
  skipped, 1 shelf-routing failure. The failure was fixed and the affected
  142-test regression set then passed. The isolated checkout lacks the private
  corpus, so corpus-dependent tests skip or fail there; it must not be used as
  evidence that the full library runs without its remote artifacts.
- Live site at the time of inspection: release `554c8df`, readiness reported
  520 concepts, 40 Pearson books, Supabase cache, and ingestion disabled. LoRA
  chat returned a graph synthesis reply with a Hugging Face citation. The tested
  Hugging Face PDF returned valid bytes and had four pages. The diagnostic API
  reported a ten-question cap, but its full assessment path was not E2E tested.
- With private graph, catalog, PDF and model fixtures copied into the isolated
  checkout for testing, the complete unit suite passed: **1,520 passed, 7
  skipped**. The copied fixtures were removed afterward. The structural chat
  UI smoke test passed. The Docker Compose plugin is absent on this host, so
  the YAML and shared-export behavior were tested without a container boot.

## Deferred / next pair

- **Do not call this production-ready or deploy it yet.** The repository-wide
  quality gate remains red on pre-existing lint, type-tool availability,
  banned patterns, file-size, magic-number and architecture findings. A
  different-role human review is required by `AGENTS.md` before shipping.
- Antideploy is an uploaded-folder application; a Git push does not deploy it.
  Package and upload only after review, with the original LFS assets and the
  verified Supabase corpus available. Check the public release header after
  upload. Do not replace the live release with the tracked fixture.
- The publicly exposed shared password must be rotated at the identity
  provider. Removing it from HTML does not revoke it. No provider-side rotation
  was performed in this change.
- Pearson currently serves a book-specific handoff with manual page
  instructions. The tested `/page/N` format failed to jump in a fresh
  authenticated reader tab. Do not claim an exact-page opening unless Pearson
  supplies and demonstrates another supported link format.
- Hosted ingestion is intentionally denied and reports disabled. The local
  workstation ingestion, OCR/model gate, Supabase synchronization and rollback
  still need a real end-to-end operator run with authorized sources.
- The committed ingestion-model evaluation reports alias F1 of 0.4219 on 32
  probes, 0% exact empty-input matches, and one contamination failure; its own
  gate marks it unready for a full replacement. Do not auto-promote or publish
  new weights without a held-out eval and rights-reviewed data.
- Validate Supabase authentication as a real student and librarian, XKIRO and
  NVIDIA provider failover, the full diagnostic flow, all source pages and the
  landing assets on the new deployed release before closing this work.

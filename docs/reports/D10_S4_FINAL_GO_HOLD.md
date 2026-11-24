# D10-S4 final technical review — HOLD

**Candidate code revision:** `722b0c58c7fc4d4432da7ada515a7270fba463b3` on isolated branch `d10-s4-stabilization` at `/home/pratay-karali/Desktop/archipelago-d10-s4`. The original checkout, unrelated pages, frozen held-out 50-query benchmark, remote HF assets, and deployed application were not changed. The only browser-facing edits are the requested login/session flow and the existing chat Inspector/operations fragment.

**Technical reviewer verdict: HOLD — exact blockers below.** The candidate is locally testable and suitable for internal review, but cannot be called ready for the primary author's authenticated hosted retest yet.

## What is complete locally

- Hosted auth code now distinguishes idle, absolute, JWT, revoked and upstream states; preserves an unsent question; verifies identity before chat submission; and uses a shared, service-role-only Supabase session RPC across instances. The SQL migration is committed but unapplied. No credential was printed or committed.
- Chat trace records the actual selected provider/model or deterministic fallback, route, synthesis mode, graph/content revision, release SHA, document/passage IDs, measured early timing and explicit cache miss. The Inspector marks claim support and reader verification as pending. Provider duration and final total time are not in the initial stream frame.
- The misleading Transformer summary was corrected at runtime; 54 questionable RAG-adjacent graph edges are quarantined with an edge ledger. The earlier 194 uncertain edges were not promoted. Paging/fault and OSTEP base-and-bounds answers are qualified and source-correct in the offline candidate.
- The pinned approved library inventory yielded 43 PDFs and 3,025 deterministic page-bound passages. The local index has SHA-256 `93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52`; `D10_S4_CANDIDATE_PASSAGE_MANIFEST.json` records document hashes without committing copyrighted body text. The packaged graph has SHA-256 `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76` and matches the inspected graphier asset.
- The 36 D10 diagnostics were run offline on baseline code `c0d90b8484bbf48e605d4dcffb6975bdb6a09e2e` and candidate code above, both with the same graph bytes. The candidate additionally loaded the approved passage index. The original base-and-bounds query changed from a GPT-3 citation to OSTEP PDF p.7/passage `38d81af0ae91:p7:c0`. The CSVs include full responses and empty human judgment fields. No held-out 50-query result or human grade was invented.
- A local candidate launch with the index attached returned 200 for `/api/readiness` and the base-and-bounds `/api/chat` query. That response had the expected OSTEP document/page/passage and `Cache-Control: private, no-store, no-cache, must-revalidate`. Chrome opened original OSTEP pp.2/7, LoRA p.1 and RAG p.1; this is original-PDF evidence only.

## Exact blockers before author hosted retesting

1. **Auth staging migration and browser trace:** Apply `supabase/migrations/20261124000000_d10_s4_durable_sessions.sql` in an approved staging environment, configure the server-only Supabase service key and shared `ARCHIPELAGO_CSRF_SECRET`, and verify idle/active, refresh, reload, logout, role, simultaneous-tab and two-instance behavior. The author's observed Spanner failure is still blocked by authentication in the deployed app. The precise production request path was not captured with authenticated network evidence.
2. **Provider/cache live proof:** Run the six diagnostics through authenticated hosted chat with redacted network responses across identical queries, paraphrases, new sessions and two authorized accounts. Record actual provider/model, fallback, cache headers/intermediaries and completion timing. The current offline worksheet states `provider=none`; it does not claim live API generation.
3. **Application reader:** Verify authenticated `/read`, `/api/page-view`, `/api/reader/info` and original-PDF page display for representative paper, OSTEP and Pearson links. Unauthenticated reader probes correctly returned 401, so no hosted reader result is marked passed. Keep human claim entailment separate from provenance and page visibility.
4. **Index deployment and review:** The body index is local at `/tmp/archipelago_d10_s4_candidate_passages.jsonl`; a staging instance must attach exactly its verified checksum. General graph routes still rely on existing graph source passages, so the new body index is available to catalog and audited source routes but is not a semantic graph rebuild. No graph edge promotion or HF publication occurred.
5. **Repository-wide gate:** `scripts/quality_gate.py` fails on preexisting repository-wide lint, format, mypy, banned-pattern and file-size debt. A selected 116-test unit/integration/security set has **113 passed and 3 deselected**: one preexisting Excel schema assertion, one preexisting research-route assertion (reproduced on baseline), and one immutability assertion that conflicts with the explicitly requested PDF ingestion fix. Do not treat this selected pass as full CI approval. An independent human review remains required under AGENTS.md.

## Reproducible local candidate

From `/home/pratay-karali/Desktop/archipelago-d10-s4`, with the verified index already present on this machine:

```sh
PORT=5152 \
ARCHIPELAGO_CANDIDATE_PASSAGES=/tmp/archipelago_d10_s4_candidate_passages.jsonl \
ARCHIPELAGO_AUTH_REQUIRED=0 \
ARCHIPELAGO_ALLOW_DEV_AUTH=0 \
ARCHIPELAGO_ENV=development \
PYTHONPATH="$PWD:$PWD/host_inference" \
python3 host_inference/server.py
```

This is an isolated loopback development command (`http://127.0.0.1:5152`), not the authenticated staging configuration. To rebuild the index, set `HF_TOKEN` securely in the shell and run `python3 scripts/ops/build_d10_candidate_passages.py --output /tmp/archipelago_d10_s4_candidate_passages.jsonl --summary docs/reports/D10_S4_CANDIDATE_PASSAGE_MANIFEST.json`, then compare the resulting SHA-256 with the manifest. The original HF revisions are `Library_books@b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd` and `graphier@86e29828c38dbf0f8cea5d50ed6a341ccde3a8f3`.

## Required handoff files

1. `D10_S4_AUTH_SESSION_ROOT_CAUSE_AND_FIX.md`
2. `D10_S4_PROVIDER_AND_CACHE_PROVENANCE.md`
3. `D10_S4_SIX_QUERY_ISSUE_REVIEW.md`
4. `D10_S4_INGESTION_AND_SOURCE_STATUS.md`
5. `D10_S4_GRAPH_SEMANTIC_DEFECTS.md`
6. `D10_S4_CITATION_AND_PAGE_REDIRECT_TESTS.md`
7. `D10_S4_BEFORE_AFTER_REGRESSION.csv`
8. `D10_S4_AUTHOR_TEST_WORKSHEET.csv`
9. `D10_S4_FINAL_GO_HOLD.md`

Supporting ledgers: `D10_S4_GRAPH_EDGE_QUARANTINE.csv` and `D10_S4_CANDIDATE_PASSAGE_MANIFEST.json`.

**HOLD — auth migration/live session trace, provider/cache proof, hosted reader verification, index staging attachment, and full quality approval remain open.**

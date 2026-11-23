# D9.5 engineering differential — draft PR #22

Date: 2026-11-23. Base `236526b7ceab7a500b93cdf042336cf9187de4cd`; PR head before D9.5 repairs `7155eea061c7abe686b8f073d62e4361ae82dd62`. Both run in the same system Python 3.12.3 / pytest 9.1.1 environment, each in a separate clean worktree with the same ignored frozen `okf_graph.json` (SHA-256 `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`) seeded before collection. No frozen benchmark, graph, production branch or manuscript was changed.

## Hosted release gate: HOLD

Vercel project inspection reports `archipelago-6383/archipelago` production branch `redesign_research_workspace`. `GET /api/readiness` at `https://archipelago-blond.vercel.app` returned HTTP 200, `X-Archipelago-Release: 236526b7ceab7a500b93cdf042336cf9187de4cd`, graph fingerprint `9818ac0e8fd3`, full corpus, 610 concepts. The research alias returned readiness 200 but no deployed revision header; its exact SHA is unverified. The redacted local hosted harness report for this release records J4 PASS and J1/J2/J3/J5/J6 BLOCKED because authorized Student/Faculty/Librarian test sessions were unavailable. The previous D8 6/6 pass belongs to release `1785846a49db27d5931beb596cf64bbbae778f3c` and is not evidence for this release. Login, PDF bytes, persisted research/XLSX, abstention and cross-user isolation therefore remain unverified on the current release.

## Local CI differential

Command: `python3 -m pytest tests/unit tests/integration -q -m 'unit or integration' --tb=line`, run separately on each seeded checkout. Base: 1,390 passed, 44 failed, 12 errors, 10 skipped, 1,031 deselected. PR head: 1,393 passed, 44 failed, 12 errors, 10 skipped, 1,031 deselected. All 56 failing/error test IDs are identical; the three additional passes are D9 unit tests. There is no demonstrated D9 regression in this controlled comparison. The earlier unseeded PR run had 73 failures because the ignored full graph fixture was absent; that comparison was invalid for regression attribution.

Shared setup/fixture problems include seven Kuzu `Table Concept does not exist` graph-explorer errors, missing institutional Pearson catalog data (five source-link errors), an absent local model directory, and four tests expecting a small fixture while the seeded graph is the full 6.2 MB corpus. Other shared assertion failures cover citation/link formatting, legacy resource catalog expectations, workbook schema and routing behavior. These are existing issues or fixture mismatches because the same IDs fail on the base. Do not weaken them or bulk-edit unrelated modules to make this PR green.

An unfiltered run of `python3 -m pytest tests/unit tests/integration -q --tb=line` on both seeded checkouts gives base **2,321 passed, 122 failed, 27 errors, 17 skipped** and PR head **2,327 passed, 121 failed, 27 errors, 17 skipped**. Of 149 base failing/error IDs, 148 also fail on the PR; the sole base-only failure is `tests/unit/test_link_resolver.py::test_link_resolver_integrated`. There are **zero PR-only failing IDs**. The PR adds five passing D9 tests, and one base failure does not reproduce on the PR. This differential identifies no material D9 regression, but neither checkout meets the full-suite gate.

The repository quality gate remains red on pre-existing Ruff/format findings, 1,326 strict mypy errors, magic numbers, and 86 oversized files. D9.5 changed Python files pass Ruff lint/format, and targeted annotation/reblinding tests pass. A different-role human review is still absent; GitHub reports no PR reviews. Vercel preview statuses alone are not the required CI/review gate.

## Study-tool repair

`reblind_and_prepare_packets.py` now writes a predeclared full or partial assignment manifest. The partial design freezes 10 stratified overlap queries and 171 dual-coded items, then divides the remaining 560 items 281/279 between reviewers. Fresh HMAC IDs and a private 0600 key remain outside Git. `post_annotation_analysis.py` validates all assigned human fields, separate reviewer IDs, overlap-only agreement, ordinal Krippendorff alpha, claim-support agreement, adjudication of dual-coded disagreements, coordinator receipt/checksums and complete top-five human coverage. It refuses missing data and below-threshold reliability before writing human qrels, metrics or local manuscript tables. No human labels exist.

## Gate decision

**HOLD.** Complete authenticated J1–J6 on the exact current release, identify the research release SHA, resolve or formally triage baseline CI/fixture failures, and obtain different-role review while PR #22 stays draft. Do not merge or trigger production deployment from this report.

# D14.0 Release Identity Audit

- **Phase:** D14.0 — Forensic Audit & Baseline Freeze
- **Owner:** `d14-forensic-audit`
- **Date:** 2026-11-28
- **Target System:** Archipelago SIGIR 2027 Demonstrations Track (`https://archipelago-sigir.vercel.app`)
- **UEM Production Isolation:** `https://archipelago-blond.vercel.app` (live on `f76c1c4ddb91bbf1947dbb820c971c51e04753cf`, branch `redesign_research_workspace`, Vercel project `prj_yVvxBExHYiLa67oqnABK2vW9FfCS`, Supabase `spllaastejfwclllfndp`) is strictly untouched and out of scope.

---

## 1. Executive Summary

Reconciliation of the local repository, remotes, tags, and worktrees resolves the apparent commit mismatch between the reported D12 release (`809a70a6434ee18fce65250b98207fa52b2ae8f1`), the live D13 browser-tested SHA (`fe8887c878e27f1770690236513f0f6c79c37d7c`), `sigir/demo-2027` (`71271ec`), and the current D14 worktree (`c0d90b8` / `main`):

1. **`809a70a6434ee18fce65250b98207fa52b2ae8f1` IS the D12 recovery merge commit** (`Merge branch 'd12/ui-3d' into sigir/d12-recovery`, `2026-11-28 00:45:00 +0530`), combining all three D12 recovery branches (`d12/retrieval-nlu` @ `ca99e52`, `d12/synthesis-citations` @ `b0fd195`, `d12/ui-3d` @ `12a0db6`).
2. **`fe8887c878e27f1770690236513f0f6c79c37d7c` (`origin/sigir/d12-recovery`, `sigir/d12-recovery`) is 3 hotfix/polish commits ahead of `809a70a`**, pushed between `06:42` and `06:54 +0530` on `2026-11-28` during pre-D13/D13 browser testing, and is the **exact commit currently deployed live** to `https://archipelago-sigir.vercel.app` (confirmed by `@d14-integrator` in `#7`).
3. **`d14_scientific_recovery_stabilization` is currently checked out at `c0d90b8484bbf48e605d4dcffb6975bdb6a09e2e` (local `main`)**, which diverged from the SIGIR lineage at `ef4e777988d463986b1f1aba54581c2e81e84d73` (`2026-11-22 14:22:40 +0530`) and is **83 commits behind `sigir/d12-recovery` (`fe8887c`)**. D14 implementation MUST branch from `sigir/d12-recovery` (`fe8887c`) — NOT `c0d90b8` — to preserve D10-S3..S8, D11, and D12 SIGIR work.

---

## 2. Commit & Branch Reconciliation Matrix

| Ref / Label | Exact Full SHA | Author Timestamp | Ancestor / Relation | Role in Lineage |
|---|---|---|---|---|
| `sigir/d12-recovery` (`origin/sigir/d12-recovery`) | `fe8887c878e27f1770690236513f0f6c79c37d7c` | `2026-11-28 06:54:41 +0530` | `809a70a` + 3 commits (`0001769`, `8555462`, `fe8887c`) | **Live SIGIR Demo (`archipelago-sigir.vercel.app`) & D13 browser-tested baseline** |
| Reported D12 Release | `809a70a6434ee18fce65250b98207fa52b2ae8f1` | `2026-11-28 00:45:00 +0530` | Merge of `d12/ui-3d` (`12a0db6`) onto `ab30faf` (`d12/retrieval-nlu` + `d12/synthesis-citations`) | **D12 Release Merge Baseline (pre-morning hotfixes)** |
| `sigir/d11-a2-stage3-consolidated` | `b6ec23eee15cf45b3edce801a617fb614cad99e1` | `2026-11-27 23:55:26 +0530` | `3c72443` + 1 UX commit | Last pre-D12 commit on SIGIR lineage |
| Tag `d11-a4-frozen` | `3c724431edd11e8b987e9150b7a526675cc6501f` | `2026-11-27 23:16:06 +0530` | Annotated tag created `2026-11-28 00:28:43 +0530` | **Frozen D11-A.4 Rollback Target** |
| `sigir/demo-2027` (`origin/sigir/demo-2027`) | `71271ecad00ec30a4339ab6d072d9b5dbaf07861` | `2026-11-27 15:30:46 +0530` | 22 commits behind `sigir/d12-recovery` | D10-S8 hosted release evidence (`0.1.0-candidate.2`, deployed `0195b07`) |
| `d14_scientific_recovery_stabilization` / local `main` | `c0d90b8484bbf48e605d4dcffb6975bdb6a09e2e` | `2026-11-22 16:53:41 +0530` | 83 commits behind `sigir/d12-recovery`; 2 commits ahead of merge-base `ef4e777` | Current D14.0 audit worktree only (do NOT base D14.1+ code here) |
| `origin/main` | `9f15cacb7104ad634da72902fb7ecb8fdd665956` | `2026-11-22 18:44:10 +0530` | 7 commits ahead of local `main` (`c0d90b8`) | Remote main (Nov 22 auth/deploy fixes) |
| Merge-base (`main` vs `sigir/d12-recovery`) | `ef4e777988d463986b1f1aba54581c2e81e84d73` | `2026-11-22 14:22:40 +0530` | Common ancestor | Split point between `main` and SIGIR 2027 demo lineage |
| `redesign_research_workspace` (UEM Prod) | `f76c1c4ddb91bbf1947dbb820c971c51e04753cf` | — | UEM production branch | **OFF-LIMITS** (`archipelago-blond.vercel.app`) |

### Detailed Post-`d11-a4-frozen` Commit Chain on `sigir/d12-recovery`

| Order | SHA (short) | Timestamp | Subject |
|---|---|---|---|
| 1 | `3c72443` | `2026-11-27 23:16:06` | `(tag: d11-a4-frozen)` D11-A.4: end-to-end stream deadline, RBAC false-positive fix, terminal telemetry, and generalizable concept specificity |
| 2 | `b6ec23e` | `2026-11-27 23:55:26` | UX: list all available topics as 1), 2)... and show max 3 Colab-style pills from 40-question bank on non-AI/fallback turns |
| 3 | `12a0db6` | `2026-11-28 00:37:23` | `(d12/ui-3d)` feat(d12-ui-3d): restore 3D visual aesthetic, honest citation badges, and visible SVG graph arrows |
| 4 | `b0fd195` | `2026-11-28 00:40:47` | `(d12/synthesis-citations)` fix(d12): task-complete synthesis, 4-way citation source_kind/evidence_backed, and bounded latency telemetry |
| 5 | `ca99e52` | `2026-11-28 00:43:49` | `(d12/retrieval-nlu)` fix(d12): systemic query NLU, domain-aware retrieval, graph semantics, and contextual follow-ups |
| 6 | `ab30faf` | `2026-11-28 00:45:00` | Merge branch `d12/synthesis-citations` into `sigir/d12-recovery` |
| 7 | `809a70a` | `2026-11-28 00:45:00` | **Merge branch `d12/ui-3d` into `sigir/d12-recovery` (Reported D12 Release)** |
| 8 | `0001769` | `2026-11-28 06:42:05` | UI polish: center big circle AI Librarian avatar, typewriter on welcome & landing, remove overlapping Active Mode pill |
| 9 | `8555462` | `2026-11-28 06:51:38` | Reliability: tighten urllib3 v2 socket timeout (8s chunk) & frontend stream idle watchdog (14s vs 75s) |
| 10 | `fe8887c` | `2026-11-28 06:54:41` | **Fix Sources & Resources card: never render empty `href=''` links that open `/chat`; label metadata/unavailable vs verified PDF/Pearson links (Live D13 Baseline)** |

---

## 3. Worktree Inventory (Key Active & Historical Worktrees)

| Worktree Path | Branch | HEAD SHA | Working Tree Status | Notes |
|---|---|---|---|---|
| `/home/pratay-karali/.gemini/antigravity/worktrees/archipelago/d14_scientific_recovery_stabilization` | `d14_scientific_recovery_stabilization` | `c0d90b8` | Clean (D14.0 docs only) | Current D14.0 audit workspace |
| `/home/pratay-karali/.gemini/antigravity/worktrees/66c355ef-147d-4e8e-a8e2-037d4b340ff7/subagent-D11-A-2-Verification--36Q-Diagnostic---Stage-3-Consolidator-self-edf9d920` | `sigir/d12-recovery` | `fe8887c` | **Dirty:** `M ui/chat/landing.html` (66+, 67-) | Active D12/D13 recovery worktree; do NOT commit dirty `landing.html` without review |
| `/home/pratay-karali/Desktop/archipelago-sigir-demo` | `sigir/demo-2027` | `71271ec` | Clean | D10-S8 SIGIR demo checkout; holds `outputs/d11-a-author-diagnostic/` |
| `/home/pratay-karali/Desktop/archipelago` | `main` | `c0d90b8` | Linked to UEM Vercel project | **OFF-LIMITS** for SIGIR deploys |
| `/home/pratay-karali/.gemini/antigravity/worktrees/archipelago/investigate_chat_reliability` | `sigir/d11-a2-f01-hotfix` | `0e59085` | Historical | D11-A.2 F01 hotfix worktree |
| `/home/pratay-karali/.gemini/antigravity/worktrees/archipelago/redesign_research_workspace` | `redesign_research_workspace` | `f76c1c4` | UEM Production | **OFF-LIMITS** |

---

## 4. Verified Rollback Targets (D11 & D12)

All rollback operations MUST remain strictly scoped to the SIGIR Vercel project `archipelago-sigir` (`prj_BjRCpNfUItbG8BO26CIQbPhP1oi9`, org `sigir1`) and NEVER touch UEM production (`archipelago-blond.vercel.app`).

| Rollback Tier | Target Ref / Tag | Exact SHA | Associated Worktree | When to Use |
|---|---|---|---|---|
| **D12 Live Baseline (Current)** | `sigir/d12-recovery` | `fe8887c878e27f1770690236513f0f6c79c37d7c` | `.../66c355ef-.../subagent-D11-A-2-...` | Revert any failed D14 candidate back to pre-D14 live state |
| **D12 Release Merge (Pre-Hotfix)** | `809a70a` (on `sigir/d12-recovery`) | `809a70a6434ee18fce65250b98207fa52b2ae8f1` | — | Revert if the 3 morning hotfixes (`0001769`, `8555462`, `fe8887c`) introduced regressions |
| **D11 Stage-3 Consolidated** | `sigir/d11-a2-stage3-consolidated` | `b6ec23eee15cf45b3edce801a617fb614cad99e1` | — | Roll back all D12 merges while keeping D11-A.4 + topic-list UX |
| **D11 Frozen Baseline (Canonical)** | Tag `d11-a4-frozen` | `3c724431edd11e8b987e9150b7a526675cc6501f` | — | Hard rollback to verified D11-A.4 frozen baseline |
| **D10-S8 Release Evidence** | `sigir/demo-2027` | `71271ecad00ec30a4339ab6d072d9b5dbaf07861` | `/home/pratay-karali/Desktop/archipelago-sigir-demo` | Historical D10-S8 acceptance baseline |

### Discrepancy Flags Raised for Gate 0

1. **`pearson_bookshelf.json` divergence:** `host_inference/fixtures/pearson_bookshelf.json` differs between `c0d90b8` (`507c21e1fd32a61e...`, 25,306 bytes) and `sigir/d12-recovery` / `sigir/demo-2027` (`414d334fedcab1bd...`, 28,628 bytes). Under `ARCHIPELAGO_ACCESS_PROFILE=open_access` on `archipelago-sigir`, Pearson books are disabled (`pearson_books: 0`), confirming isolation from licensed UEM e-books.
2. **Dirty file in `sigir/d12-recovery` worktree:** `ui/chat/landing.html` has uncommitted local edits (`66+, 67-`) not present in `fe8887c`. Creating `sigir/d14-recovery` directly from commit `fe8887c` cleanly excludes those uncommitted changes.
3. **Branch base requirement:** Aligning with `@d14-integrator` (`docs/reports/d14/D14_INTEGRATION_CONTRACT.md`), D14.1–D14.8 implementation MUST create `sigir/d14-recovery` from `fe8887c` and import `docs/reports/d14/*` onto it.

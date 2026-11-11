# Graph layout handoff — 2026-10-23

## Built

- Kept the existing landing layout and moved its background video slightly closer to center (`left: 4%`, `translateY(3%)`).
- Added a data-driven academic graph entry view with nine highly connected saved concepts. The entry view draws a sparse backbone of genuine saved relationships, while reporting the complete indexed concept count.
- Selecting a concept opens a bounded neighborhood, displays one visible link per neighboring node, and shows the saved summary, type, level, source count, and degree in the detail panel. Other neighbors can be selected to continue exploring.
- Preserved the separate research graph on `/research/papers`, where selecting a saved topic reveals papers and selecting a paper loads its persisted OKF. Its projection route excludes institutional and academic nodes.

## Verification

- Local academic graph API: 537 indexed concepts, nine entry nodes, eight valid entry edges.
- Local browser: main concepts rendered; selecting Retrieval-Augmented Generation loaded its saved neighborhood and description.
- `ruff check` and `ruff format` passed for changed Python files; graph JavaScript syntax passed `node --check`.
- Focused academic graph tests: 2 passed. Research projection tests: 7 passed.
- Final production deployment `dpl_GL74ep1Q85y2yXgwhoQExHbGADJZ` reached READY and is aliased to `https://archipelago-archipelago-6383.vercel.app/`. Public landing, library, and readiness returned HTTP 200; readiness reports 537 full-corpus concepts. Staff graph and research routes redirect unauthenticated requests to the app login, as intended.

## Deferred

- A signed-in production session is needed to visually inspect the staff-only research graph against live Supabase records. The research projection tests cover its data isolation; this handoff does not claim a production OKF or GPU ingestion run.
- A broad host-inference test run has two existing expectation mismatches: the legacy “Research overview” page label and OKF schema version `2.0.0` versus the current `2.1.0` response.

## Next pair

- Recheck the deployed academic graph at `/graph` using a staff session, and inspect the `/research/papers` topic-to-paper-to-OKF interaction with saved production records.

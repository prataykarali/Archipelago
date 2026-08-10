# Library pilot: scoped delivery TODO

Updated: 2026-07-21. This checklist reflects the pilot decision: three subjects
(Database Management Systems, Data Structures, Operating Systems), five to six
books, and 10–15 papers/journals. Store book metadata only—title, author,
edition, table of contents/index, and supplied page references—not full
copyrighted books.

## P0 — demo-safe before the five-minute presentation

- [x] Run the complete offline readiness gate after the current UI/chat changes.
- [x] Smoke-test a fresh chat, a cited answer, citation click-to-page highlight,
  graph opening/highlighting, and context carried across two questions.
- [x] Ingest and verify the four catalog `.ods` files into the Kùzu graph on the
  presentation database; record row/node/edge counts in the daily update.
- [x] Add the selected 5–6 book metadata records and confirm that no full book
  text/PDF is uploaded unless it is openly licensed or permission is recorded.
- [x] Curate 10–15 journal/paper records around repeated keywords for the three
  pilot subjects; record source URL, author, year, and stable citation target.
- [x] Validate every displayed citation: title, author, page/section (where
  applicable), URL, and click target. Broken or unavailable targets must not be
  rendered as citations.
- [x] Keep the demo local-first. Do **not** upload Cloudinary assets or any book
  material to a Hugging Face dataset as part of this pilot. Focus: working
  citation links + page-view highlights only.

## P1 — predefined, explainable ranking lists

- [x] Agree on normalized ranking signals: review/curator score, author
  authority, edition/year, availability/copy count, subject match, and journal
  recency/issue status. → `archipelago/inference/ranking_seeds.py`
- [x] Create a small librarian-approved seed list per subject (DBMS, DS, OS,
  AI/ML papers), with a reason for each placement.
- [x] Store ranks and reasons as data, not hard-coded chat prose; wired into
  `library_books` chat route via `rank_seed_entries` / `format_seed_ranking`.
- [x] Define tie-breaking and missing-data rules so a title is never promoted
  merely because metadata is absent (availability defaults to 0).
- [x] Add tests: `tests/unit/test_ranking_seeds.py`.
- [ ] Expand seed lists toward 10–20 books and 10–20 journals per subject with
  librarian sign-off; join live catalog availability_by_title at query time.
- [ ] Surface the same seed ranks in graph side panels (not only chat).

## P2 — safety, quality, and operating process

- [x] Move e-resource secrets out of tracked PDFs/code and into a protected
  librarian-only secret store. Student chat should give access instructions or
  the authenticated portal—not reveal passwords.
- [x] Verify library hours, locations, and e-resource links with the library
  before each demo; label these as operational data with a review date.
- [x] Review the 50 response layouts (`reply_styles.py`): presentation only;
  cleanser strips Sources dumps and caps inline citations at 2 so layouts
  never hurt provenance. Tests: `test_reply_styles.py`, `test_citation_cleanse.py`.
- [x] Add a daily morning update: completed items, test results, data added,
  blockers, and the next day’s one highest-priority task.
- [x] Re-check copyright/permission status for every new source and retain a
  provenance note before ingestion.

# Librarian Space handoff — 2026-11-02

Built: a light Librarian Space with Catalogue, Circulation, Orders, Fine Notes,
and a responsive knowledge graph. Added a shared-session handoff between the
two Vercel origins and restored a landing choice page on the second site.
Research's existing ingestion and OKF pages were not edited.

Persistence: `archipelago_librarian_records` and atomic audit table in the
existing Supabase project. Only librarians and administrators may save via the
server API. Faculty can read. These are Archipelago records, not Koha writes.

Deployed: original site `dpl_73sc9NwKz16ev8m7H9FwpWDWiCNR`; second site
`dpl_2uHGPWq5JMCLQjFb2cbBxLXMHWYE`. Production routes return 200;
unauthenticated staff API returns 401. Four focused unit tests pass, plus Ruff
for the changed Python files. The repository-wide quality gate still reports
existing strict type, format, and file-size baseline failures.

OPAC: the public record lookup succeeded locally but returned 503 from Vercel
for a tested book ID. The server now falls back to a clearly marked dated Koha
export when that exact book ID is present. The export remains stale (2026-10-03)
and covers 109 keyword-filtered holdings, not the full catalogue. Full live
Koha edits, loans, fines, and orders require an authorized Koha write API.

Next pair: verify the browser session handoff with a signed-in staff account;
verify a real librarian save and audit row; obtain an authorized Koha API or
updated export if official record changes must appear automatically.

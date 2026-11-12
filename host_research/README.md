# Second Vercel project: Research and Librarian Space

`archipelago-librarian` hosts the original five Research pages, their source-backed
paper OKF views, and Librarian Space. Staff workspaces at `/librarian/catalog`,
`/librarian/circulation`, `/librarian/orders`, and `/librarian/fines` save
Archipelago records in Supabase with an audit trail. They do not change Koha.
The graph remains at `/academic/graph` with a light theme and source-backed
annotation controls. The first project's `/library` page remains the public
library details page.

The Research API routes proxy to `https://archipelago-blond.vercel.app` using the
same verified Supabase staff bearer token. This preserves the existing job queue,
local workstation approval, Indra paper extraction, automatic OKF, HF publication,
progress view, and research graph without moving that backend yet. The new site
depends on the first Vercel deployment remaining available until the backend is
separately migrated. No job is created by deployment or by scheduled discovery.

Both projects use the same Supabase Auth and data. `SUPABASE_URL`,
`SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SECRET_KEY` are encrypted production
variables on the second project. `CRON_SECRET` protects daily scheduled checks.
The Hugging Face datasets stay `Prataykarali/Library_books` for books and papers
and `Prataykarali/graphier` for graph artifacts.

The second project's root shows a choice page. A signed-in staff member can
choose “Continue with existing Archipelago session” on its sign-in page; an
exact-origin browser handoff shares the verified session from the first site.
The handoff requires a click because browser storage is isolated by origin.

## Koha export flow

The public OPAC is searchable, but its `robots.txt` disallows automated crawling.
The checked OAI endpoint is absent and public MARCXML export was denied. The
local workstation can publish only the four authorized ODS metadata exports in
`data/koha`:

```bash
python3 scripts/ops/sync_koha_snapshot.py --dry-run
python3 scripts/ops/sync_koha_snapshot.py
```

The script checks headers and source checksums, then upserts changed metadata to
the private Supabase Storage object `archipelago-cache/koha_catalog_snapshot.json`.
It does not download PDFs, queue ingestion, or write to Koha. The public
`/api/library/koha` route reads that snapshot and recalculates freshness from
the oldest of the four export dates. Academic → Library details displays the
export date and a stale warning. The local user systemd timer runs this script
daily, while Vercel Cron checks snapshot freshness daily. New OPAC facts require
new authorized exports to arrive in `data/koha`; a scheduler alone cannot make
stale exports current.

The current holdings file is keyword-filtered (109 rows as of 3 October 2026),
not a complete book inventory. Its available barcode and overdue-count columns
are retained in the published metadata, and every row gets a link to its Koha
record. It does not contain ISBNs, call numbers, or rack numbers. To add verified
identifiers for rows in this export, the librarian can place
`data/koha/catalog_identifiers.csv` alongside the four ODS files with columns:

```csv
biblionumber,isbn,call_number,rack_number
```

Each row must match an exported Koha biblionumber. ISBNs are checksum-validated;
unknown or duplicate IDs reject the whole update. Blank ISBN and rack fields
stay blank rather than being guessed. A complete campus inventory requires a
complete authorized catalogue and item export from Koha. Borrower loans, fines,
and passwords are never published into this shared metadata snapshot.

The same local daily run also checks UEM's public NDLI Atom feed and publishes
item titles, stable repository links, update dates, and an `ingestion_status` of
`not_started`. It does not fetch issue PDFs or research-directory files. If the
feed fails, the last published candidate list is retained while Koha export
updates can still proceed. Academic → Library details lists those repository
links for human review.

## Main routes

- `/research`, `/research/progress`, `/research/topics`, `/research/paper`,
  `/research/topic`: original Research interface.
- `/api/research/*`: authenticated proxy to the existing research backend.
- `/librarian` and `/librarian/<section>`: staff overview and editable notes.
- `/academic/graph#library-details`: light knowledge graph with Koha metadata.
- `/api/librarian/<section>`: authenticated staff records; writes require
  librarian or administrator role.
- `/api/library/koha`: dated public Koha export metadata.
- `/api/research/intake/scheduled`: daily candidate discovery for review only.
- `/api/library/koha/scheduled`: daily snapshot freshness status.

# Second Vercel project: research and Academic graph

`archipelago-librarian` hosts the original five Research pages, their source-backed
paper OKF views, the Academic graph, and Koha metadata under Academic → Library
details. The existing `/library` page on the first Vercel project is untouched.

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

## Main routes

- `/research`, `/research/progress`, `/research/topics`, `/research/paper`,
  `/research/topic`: original Research interface.
- `/api/research/*`: authenticated proxy to the existing research backend.
- `/academic/graph#library-details`: Academic graph with Koha metadata.
- `/api/library/koha`: dated public Koha export metadata.
- `/api/research/intake/scheduled`: daily candidate discovery for review only.
- `/api/library/koha/scheduled`: daily snapshot freshness status.

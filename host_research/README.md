# Research transport

This is the small Flask deployment root for the separate `archipelago-librarian`
Vercel project. It does not load the chat engine, graph corpus, book assets, or
GPU ingestion code.

## Environment

- `SUPABASE_URL`: the same Supabase project URL used by the original app.
- `SUPABASE_PUBLISHABLE_KEY`: validates browser sessions through Supabase Auth.
- `SUPABASE_SECRET_KEY`: server-only access to the existing research index.
- `CRON_SECRET`: Vercel Cron bearer secret.
- `ARCHIPELAGO_FRONTEND_ORIGIN`: exact original app origin for browser access.

Both Vercel projects must use the same Supabase project. The Hugging Face
datasets remain `Prataykarali/Library_books` for books and papers and
`Prataykarali/graphier` for graph artifacts; this transport does not copy or
upload either dataset.

## Routes

- `GET /api/readiness`: checks configuration without revealing credentials.
- `GET /api/research/intake/records`: fetches the current shared paper index for
  an authenticated user.
- `POST /api/research/discover`: obtains OpenAlex candidates and a Google Scholar
  review link, with no persistence.
- `GET /api/research/intake/scheduled`: protected daily review discovery. The
  result is returned to Vercel Cron; candidate ingestion stays `not_started`.

The Codex daily research automation separately notifies the user about new
candidates and asks which papers to ingest. A scheduled OPAC refresh still needs
an authorized current Koha export or API; the public OPAC disallows crawling.

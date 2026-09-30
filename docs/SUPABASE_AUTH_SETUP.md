# Supabase login setup

Archipelago uses Supabase Auth for authentication and the `public.profiles`
table for its application roles. Supabase Auth stores password hashes; the
application database never stores passwords or credential-import source rows.

## Apply the database migration

Archipelago's live project records these migrations in order:

- `20260916_000001_auth_roles.sql`
- `20260916_000002_auth_performance.sql`

They create:

- `profiles` — each user’s username and one of `student`, `librarian`, or
  `administrator`.
- `credential_import_permissions` — an administrator’s time-limited approval
  for a specific librarian and source.
- `credential_import_audits` — counts and file hash only; never passwords.

## Configure deployment secrets

Set the following in the platform’s secret manager, not in Git:

```ini
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
ARCHIPELAGO_AUTH_REQUIRED=1
```

The browser receives only the first two values through `/api/auth/config`.
Never give `SUPABASE_SECRET_KEY` (or a legacy `SUPABASE_SERVICE_ROLE_KEY`) to
the browser or put it in a public environment file.

## Provision approved accounts

Only an administrator may run the one-time provisioning script. Make an
approved local CSV with the headers below, then delete it after use:

```csv
username,role,display_name
12024002028038,student,Student Name
librarian01,librarian,Library Staff
admin01,administrator,Library Administrator
```

Set `SUPABASE_SECRET_KEY` (or a legacy `SUPABASE_SERVICE_ROLE_KEY`) and a temporary
`ARCHIPELAGO_BOOTSTRAP_PASSWORD` only in that administrator’s shell, then run:

```bash
python scripts/supabase_provision_users.py approved_accounts.csv
```

Students sign in with the 14-digit enrollment number; staff sign in with their
assigned username. Use a unique temporary password per import where possible,
require a password change after first sign-in, and never use one shared password
for a real student or staff rollout.

## Local login check

For a local run, put `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and
`ARCHIPELAGO_AUTH_REQUIRED=1` in the ignored `.env`, then run the API on port
`5051` and the login-enabled chat UI on port `5152` (or another free local
port). The login page is `/login`; it proxies its Auth configuration to the API
and never receives the Supabase secret key.

## Credential-import approval

The SQL migration records which librarian has a time-limited import permission.
The upcoming import worker must check that permission before reading a CSV/XLSX,
create Supabase Auth accounts through the server-only Admin API, record only the
audit counts/hash, and destroy the uploaded credential file after processing.

-- Archipelago identity, authorization, and credential-import approval model.
-- Apply through the Supabase SQL Editor or `supabase db push` before enabling
-- ARCHIPELAGO_AUTH_REQUIRED=1 in the deployed API.

create type public.archipelago_role as enum ('student', 'librarian', 'administrator');

-- Security-definer helpers and triggers belong in a non-exposed schema.  The
-- Data API must not be able to call them directly.
create schema private;
revoke all on schema private from public;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text not null unique check (username ~ '^[A-Za-z0-9._-]{3,64}$'),
  role public.archipelago_role not null default 'student',
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.credential_import_permissions (
  id uuid primary key default gen_random_uuid(),
  librarian_id uuid not null references public.profiles(id) on delete cascade,
  granted_by uuid not null references public.profiles(id),
  source_label text not null check (char_length(source_label) between 1 and 160),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create unique index active_credential_import_permission
  on public.credential_import_permissions (librarian_id, source_label)
  where revoked_at is null;

create index credential_import_permissions_granted_by_idx
  on public.credential_import_permissions (granted_by);

create table public.credential_import_audits (
  id uuid primary key default gen_random_uuid(),
  permission_id uuid references public.credential_import_permissions(id),
  librarian_id uuid not null references public.profiles(id),
  source_filename text not null,
  source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
  records_received integer not null check (records_received >= 0),
  records_created integer not null check (records_created >= 0),
  records_rejected integer not null check (records_rejected >= 0),
  created_at timestamptz not null default now()
);

create index credential_import_audits_permission_id_idx
  on public.credential_import_audits (permission_id);

create index credential_import_audits_librarian_id_idx
  on public.credential_import_audits (librarian_id);

-- Passwords and source rows are intentionally never stored in public tables.
-- Supabase Auth alone stores password hashes.

create or replace function private.create_profile_for_auth_user()
returns trigger
language plpgsql
security definer set search_path = public, pg_temp
as $$
begin
  insert into public.profiles (id, username, display_name)
  values (
    new.id,
    lower(coalesce(new.raw_user_meta_data ->> 'username', split_part(new.email, '@', 1))),
    nullif(new.raw_user_meta_data ->> 'display_name', '')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure private.create_profile_for_auth_user();

create or replace function private.is_administrator()
returns boolean
language sql
stable
security definer set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.profiles
    where id = (select auth.uid()) and role = 'administrator'
  );
$$;

revoke all on function private.create_profile_for_auth_user() from public;
revoke all on function private.is_administrator() from public;
grant usage on schema private to authenticated;
grant execute on function private.is_administrator() to authenticated;

alter table public.profiles enable row level security;
alter table public.credential_import_permissions enable row level security;
alter table public.credential_import_audits enable row level security;

create policy "profiles are visible to owner or administrator"
  on public.profiles for select to authenticated
  using (id = (select auth.uid()) or (select private.is_administrator()));

create policy "librarians view their own import permissions"
  on public.credential_import_permissions for select to authenticated
  using (librarian_id = (select auth.uid()));

create policy "import audits visible to librarian or administrator"
  on public.credential_import_audits for select to authenticated
  using (
    librarian_id = (select auth.uid())
    or (select private.is_administrator())
  );

-- Browser sessions may read only what the RLS policies permit.  All account
-- creation, role changes, and credential imports are server-side operations
-- using the service-role key, which is never sent to a browser.
grant usage on schema public to authenticated;
grant select on public.profiles to authenticated;
grant select on public.credential_import_permissions to authenticated;
grant select on public.credential_import_audits to authenticated;

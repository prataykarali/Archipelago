-- Follow-up hardening for the initial Auth/RLS migration.  It is idempotent
-- so it is safe for a database provisioned from the corrected initial file.

create index if not exists credential_import_permissions_granted_by_idx
  on public.credential_import_permissions (granted_by);

create index if not exists credential_import_audits_permission_id_idx
  on public.credential_import_audits (permission_id);

create index if not exists credential_import_audits_librarian_id_idx
  on public.credential_import_audits (librarian_id);

drop policy if exists "administrators view credential import audits"
  on public.credential_import_audits;
drop policy if exists "librarians view their own credential import audits"
  on public.credential_import_audits;
drop policy if exists "import audits visible to librarian or administrator"
  on public.credential_import_audits;

create policy "import audits visible to librarian or administrator"
  on public.credential_import_audits for select to authenticated
  using (
    librarian_id = (select auth.uid())
    or (select private.is_administrator())
  );

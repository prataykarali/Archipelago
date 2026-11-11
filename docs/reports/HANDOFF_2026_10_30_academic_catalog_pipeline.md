# Handoff — Academic catalogue pipeline, 30 October 2026

## Built

- Confirmed the two Vercel deployments share Supabase; the new Research API
  forwards authenticated calls to the original backend. The original `/research`
  route still serves its own login.
- Verified the user's Koha patron login can show active checkouts, due dates,
  call numbers, barcodes, checkout history, and charges. No credentials or
  borrower records were copied into Archipelago.
- Extended the authorized ODS snapshot with available barcodes, overdue counts,
  Koha record links, and optional checksum-validated ISBN/call/rack identifiers
  matched by biblionumber. The current 109-row export has no ISBN or rack data.
- Added a bounded NDLI Atom feed monitor that publishes seven repository item
  links as review candidates with `ingestion_status=not_started`. It downloads
  no source documents.
- Published the revised metadata snapshot to shared private Supabase Storage.
  The existing public `/api/library/koha` route now serves schema version 2.
  The local daily Koha timer remains enabled.
- Added Academic Library Details rendering for OPAC and repository links in
  local source. Research UI and inference code were not changed.

## Deferred

- The new Academic UI source is not yet deployed. The repository quality gate
  reports existing type and file-size failures, and the company standards
  require review before shipping code.
- A complete campus book inventory and exact ISBN/call/rack mapping require a
  complete authorized Koha export from the library. The current export is
  keyword-filtered and last updated 3 October 2026.
- Student self-service inside Archipelago requires a supported Koha patron API
  or a proper delegated authentication flow. The tested enrollment/password
  must not be stored in Vercel or a public shared snapshot.

## Next pair

1. Obtain a complete authorized bibliographic and item export, including
   biblionumber, ISBN, call number, barcode, and any rack map.
2. Review and deploy only the Academic UI and pipeline changes after the quality
   gate and peer review are resolved.
3. Confirm whether the library can enable a scoped patron API for student-only
   checkout and charge views.

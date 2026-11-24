# Institutional Permissions, Consent Approvals & Operational Ownership

> **Governance Rule:** Campus Pilot `GO` cannot be granted by software engineering alone. Every institutional approval below must be explicitly signed off by the responsible UEM Kolkata authority prior to onboarding live student cohorts.

---

## 1. Required Institutional Approvals & Sign-Offs

| # | Approval Item | Approving Authority | Scope / What Is Being Authorized | Current Status |
|---|---|---|---|---|
| **A1** | **Campus Pilot Charter & Cohort Scope** | Dean / Registrar / Head of CSE (UEM Kolkata) | Approves bounded pilot cohort size (e.g., 1–2 course sections, <= 120 students), start/end dates, and non-graded/supplemental academic framing (AI answers are study aids, not authoritative exam/syllabus rulings). | **PENDING** |
| **A2** | **Student Privacy Notice & External AI Sub-Processor Disclosure** | UEM IT Security & Legal / Data Governance | Approves hosted data flows to Supabase (auth, quotas, research runs) and external LLM inference APIs (`XKIRO`, `NVIDIA NIM`), retention TTLs, and student opt-in / deletion workflow. | **PENDING** (Blocked by P1-2) |
| **A3** | **Identity Provisioning & Offboarding Policy** | UEM IT / Campus Directory Team | Approves account onboarding mechanism (Supabase Auth CSV import via `credential_import_permissions` vs institutional `@uem.edu.in` SSO/OIDC) and semester-end revocation of graduated/dropped accounts. | **PENDING** (Blocked by P1-3) |
| **A4** | **Koha OPAC Integration & Rate-Limit Consent** | UEM Central Library & L2C2 Koha Vendor | Authorizes (a) read-only live HTTP queries to `https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-*` at bounded concurrency (<= 2 req/s) and/or (b) periodic authorized Koha ODS/CSV holdings exports (`koha_catalog_snapshot.json`). | **PENDING** |
| **A5** | **Institutional Website Crawl Authorization** | UEM / IEM Webmaster & IT | Authorizes daily Vercel Cron (`03:00 UTC`) sitemap sync of public `uem.edu.in` and `iem.edu.in` pages (`research_schedule.py:37-42`). | **PENDING** |
| **A6** | **Pearson eLibrary & HF Dataset License Clearance** | UEM Central Library Licensing & Legal | Confirms (a) Pearson eLibrary contract allows TOC/metadata indexing and `#book/{id}/page/{n}` deep-linking, and (b) every PDF in `Prataykarali/Library_books` is either open-access or licensed for UEM student streaming (only after **P0-1** is fixed). | **PENDING** (Blocked by P0-1) |
| **A7** | **Staff Operational Ownership & Incident Escalation** | UEM Central Library + Campus IT + Archipelago Maintainers | Names primary and backup owners for uptime, takedown requests, secret rotation, and local library workstation maintenance. | **PENDING** |

---

## 2. Required Staff Operational Ownership Matrix (Pre-Launch Assignment)

Before lifting the Campus Pilot `HOLD`, each role below must have a **named human owner** and a **named backup** recorded in the pilot runbook:

| Operational Domain | Responsibilities | Target Owner Role | Recovery / Escalation SLA |
|---|---|---|---|
| **Service & Serverless Ops** | Vercel deployments (`archipelago-blond`, `archipelago-librarian`), Supabase DB health, cron monitoring (`/api/research/intake/scheduled`, `/api/internal/s5-monitor-tick`), error-budget alerts. | Campus IT / Platform Engineer | Acknowledge <= 4 business hours; rollback via Vercel instant rollback <= 30 min. |
| **Library Content & Takedown Ops** | Local library workstation (`deploy/library-computer/`), staging review sign-off (`analytics.py:366-372`), Koha snapshot upload, source withdrawal (`source_lifecycle.json` sync). | Central Library Staff (`librarian` role) | Copyright/takedown withdrawal <= 24 hours. |
| **Identity & Access Ops** | Issuing/revoking `faculty`/`librarian`/`administrator` roles, auditing `credential_import_audits`, revoking compromised sessions. | Campus IT Admin (`administrator` role) | Compromised account revocation <= 1 hour. |
| **Security & Secret Rotation** | Rotating `SUPABASE_SECRET_KEY`, `CRON_SECRET`, `HF_TOKEN`, `XKIRO_API_KEY`, `NVIDIA_API_KEY`, `ARCHIPELAGO_CSRF_SECRET`; reviewing `archipelago.research.audit` logs. | Security Lead / Maintainer | Emergency key rotation <= 1 hour; routine rotation every 90 days. |
| **Academic Governance & Student Support** | Handling student complaints, citation inaccuracy reports, privacy deletion requests, and pilot feedback. | Pilot Faculty Coordinator | Student data deletion <= 7 business days. |

---

## 3. Monitoring, Alerting & Recovery Readiness Gaps

Verified from repo inspection (`host_inference/vercel.json`, `host_research/vercel.json`, `host_inference/hostapp/routes/pages.py:91-147`):
- **What exists:** `/api/readiness` reports corpus fullness (`full: bool`, `concepts >= 200`), Supabase storage config, and cache metrics; graceful shutdown (`SIGTERM` drain + `503 Retry-After: 5`) is implemented in both Vercel apps (`middleware.py:126-144`, `host_research/app.py:73-96`).
- **What is missing for Campus GO:**
  1. External uptime monitoring & alerting (e.g., 5-minute probes on `/api/readiness` checking `corpus.full == true` and HTTP 200).
  2. Persistent log drain from Vercel to an institutional log archive (currently `archipelago.research.audit` writes to ephemeral stdout).
  3. Supabase automated daily backups & tested point-in-time restore drill.
  4. Documented local library workstation backup/restore procedure for `okf_graph.db` and `data/source_lifecycle.json`.

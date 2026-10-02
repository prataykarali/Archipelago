# Web Fetch Policy — what Archipelago will and will not do

**Owner:** Lead Engineer · **Enforced by:** `archipelago/ingestion/fetch_policy.py`
**Tests:** `tests/unit/test_fetch_policy.py` (43 cases) · `tests/unit/test_apify_source.py`

This document exists because "scrape the site for us" is the request most
likely to put the institution in legal jeopardy, and because the honest answer
is often *not* what the requester assumes. It states the boundary in code, not
just in prose.

---

## The one-paragraph version

Every outbound fetch passes `check_fetch()` first. It is **default-deny**: a
host must be explicitly allowlisted, `robots.txt` must not forbid the path, and
the request must carry **no credentials whatsoever**. If the institution holds a
licence to a title, it is ingested through the licensed connector (Pearson
eLibrary, Hugging Face) using credentials the operator already holds — never by
scraping around a login or a paywall. Access-control circumvention is not a
retrieval technique; it is a breach.

---

## What the gate enforces

| Rule | Behaviour | Reason code |
|------|-----------|-------------|
| **Default deny** | Host not on `ARCHIPELAGO_FETCH_ALLOWLIST` → refused | `host_not_allowlisted` |
| **Scheme restriction** | Only `http`/`https`; `file:`, `ftp:`, `javascript:` refused | `scheme_not_allowed` |
| **robots.txt** | `Disallow` honoured; longest match wins; `Allow` beats `Disallow` at equal length | `robots_disallowed` |
| **No credentials** | Any `token`/`api_key`/`session`/`PHPSESSID`… query param, or `Authorization`/`Cookie`/`X-API-Key` header → refused | `credentials_supplied` |
| **Rate spacing** | Minimum 1 s between fetches to the same host | `rate_limited` |
| **Audit** | Every decision, refusals included, appended to a JSONL log | — |

A refusal is **fail-closed and all-or-nothing**. If a batch of Apify
`startUrls` contains one disallowed URL, the whole run is refused. Silently
filtering to "whatever passed" would produce a partial dataset that looks
complete — a worse failure mode than an error.

### The inconclusive-vs-withdrawn distinction

Worth stating because it is easy to get backwards: an unreachable `robots.txt`
means *unrestricted by convention*, so the fetch proceeds. A network failure
during a lifecycle check means *unknown*, so the source stays citable. Neither
is treated as "no".

---

## What will never be implemented

These are not on the roadmap at any priority. A test asserts the module source
contains no bypass helper, so this stays true:

- paywall circumvention or `X-Forwarded-For`/user-agent spoofing to defeat a
  paywall;
- CAPTCHA solving;
- credential replay — reusing a session cookie or token to read what an
  anonymous visitor cannot;
- proxy rotation for the purpose of evading a rate limit or an access control.

A proxy provider (see below) may be used to reach **public** pages from the
institution's network when the institution's own egress is blocked, or to
distribute load politely. It must never be the mechanism that turns an
unauthorised request into an authorised one.

---

## Configuration

```bash
# Comma-separated hosts or suffixes. Empty means every fetch is refused.
ARCHIPELAGO_FETCH_ALLOWLIST=arxiv.org,openaccess.org,ndl.iitkgp.ac.in

# Append-only JSONL audit trail.
ARCHIPELAGO_FETCH_AUDIT_LOG=/var/log/archipelago/fetch-audit.jsonl

# Identify honestly, per robots.txt convention.
ARCHIPELAGO_FETCH_USER_AGENT=ArchipelagoLibraryBot/1.0 (+institutional graph)
```

---

## Provider assessment

### Apify — configured and verified

Per `https://apify.com/agents.md`. Token verified working against the live API
on this account:

| Property | Value |
|----------|-------|
| Account | `recommendable_xenomorph` |
| Plan | `FREE` — $5/month usage credit, then pauses (never over-bills) |
| Actor compute cap | 625 CU/month, 16 GB max memory |
| Store search | verified: `openlibrary`, `arxiv`, `google books` all return results |

Cost control follows the agent guide exactly:

- a **paid** Actor run requires an explicit human go-ahead (`approved=True`);
  `ApifyApprovalRequired` is raised otherwise;
- the per-run ceiling goes in the **call options** as
  `max_total_charge_usd` — never in `run_input`, where `maxTotalChargeUsd`
  would either be a meaningless Actor field or silently ignored;
- `max_items` caps a pay-per-result Actor's billed items;
- default ceiling **$1.00/run**, overridable with `APIFY_MAX_TOTAL_CHARGE_USD`;
- results are read from the run's **dataset** (`get-dataset-items`), never
  inferred from run metadata.

All Actors now go through `gate_start_urls()` first, so the robots/credential
rules apply to a hosted Actor exactly as they do to a direct fetch.

Free Actors found for institutional sources (all `pricingModel: free`, so they
consume only the monthly credit): `parseforge/open-library-scraper`,
`easyapi/arxiv-search-scraper`, `seemuapps/google-books-search-scraper`.

### Scrapling — recommended, and usable

| Property | Value |
|----------|-------|
| Repository | `D4Vinci/Scrapling` |
| Licence | **BSD-3-Clause** — permissive, no copyleft obligation on this codebase |
| Activity | 85k stars, actively maintained |

BSD-3 is compatible with this project's open-source posture, so adopting it
creates no licensing conflict. It is the right tool for *permitted* fetches:
robust selectors, auto-healing when a site changes markup, and polite
crawl-rate controls.

When adopted, it must be invoked **through `guarded_fetch()`** — or with the
same three checks applied to its request objects. A Scrapling fetch that skips
`check_fetch()` reintroduces every problem the gate exists to prevent.

### Decodo — proxy provider, behind the same gate

Decodo (Smartproxy) is a legitimate proxy vendor and fine as *transport*. Used
here it means: reach a public page from the library's egress, spread load
politer, or work around an institutional firewall on a page we are already
entitled to read. It is **not** a licence to fetch pages that require an
account we do not hold.

Recommendation: **prefer Scrapling direct → Apify for scale → Decodo only when
institutional egress genuinely requires it**, and always with the gate in front.

---

## Procurement questions that must be answered before any live fetch

1. **Which hosts are permitted?** A written list, not "the web".
2. **What is the licence basis** for each — open access, institutional
   subscription, public domain, or written permission?
3. **Is there a preferred proxy?** Decodo was named; Hyperbrowser is the
   catalog-recommended alternative. Either sits behind the gate.
4. **Per-run USD cap** for Apify, given the FREE plan's $5/month ceiling.

Until (1) and (2) exist, the allowlist stays empty and the gate refuses
everything — which is the correct, safe default, not an oversight.
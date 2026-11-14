# Archipelago — Dual Vercel Graph Theme & Release Parity Report

**Repository:** `prataykarali/Archipelago` (`feature/s6-final-platform-integration`)  
**Latest Deployed Git SHA (`archipelago-6383`):** `8b4c1bc5ad3836102d3f77456a67e00afb77640b` (theme & asset fixes in `9151711`, reliability/latency/test fixes in `8b4c1bc`)  
**Main Production (`archipelago-6383`):** `https://archipelago-blond.vercel.app/` (Vercel deployment `21oPzNC73y622ZCymNHrc6FHvP2k`)  
**Librarian Production (`shinaura`):** `https://archipelago-librarian.vercel.app/` (older deployment; CLI lacks `shinaura` team access — see Blockers below)

---

## 1. Root Cause of the Outdated White Librarian UI

Live inspection of `https://archipelago-librarian.vercel.app/academic/graph`, `host_research/ui/academic_graph.html`, `host_inference/ui/academic_graph.html`, and `host_research/ui/academic_light.css` revealed three compounding causes:
1. **Conflicting `!important` light stylesheet:** Both `host_research/ui/academic_graph.html` and `host_inference/ui/academic_graph.html` linked `<link rel="stylesheet" href="/academic_light.css">` on line 40. In `host_research/ui/academic_light.css`, `!important` rules forced `html, body { background: #f7faf9 / #f6faf8 !important }`, white `.graph-frame`, light radial gradient `#graph`, and white `.graph-panel` over the dark Tailwind classes (`bg-[#08071b] text-slate-100`).
2. **404 / MIME mismatch on `host_inference`:** `host_inference/ui/` did not contain `academic_light.css`, so `https://archipelago-blond.vercel.app/academic_light.css` returned HTTP `404` (`content-type: application/json`) while leaving `host_inference` dark by accident.
3. **Outdated `shinaura` deployment & low-contrast Cytoscape styles:** `https://archipelago-librarian.vercel.app/academic/graph` is still serving an older `25,284`-byte HTML build (`last-modified: Sat, 20 Oct 2018`) with light-mint Cytoscape nodes (`#ecfaf4`), whereas the updated repo source is `43,147+` bytes. Additionally, the local Vercel CLI (`aura2026socials-8112`) is authorized only for `archipelago-6383`, not `shinaura`.

---

## 2. Accessible Dark Navy/Violet Theme & Asset Fixes (`9151711`, `8b4c1bc`)

- **Files updated:** `host_research/ui/academic_graph.html`, `host_inference/ui/academic_graph.html`, `host_inference/ui/graph.html`, `host_research/ui/academic_light.css`.
- **Palette & WCAG AA Contrast (measured in Chromium `1440×960` on `https://archipelago-blond.vercel.app/academic/graph`):**
  - Main background: `#0F172A` (`#F1F5F9` text -> **`16.3:1`**)
  - Graph canvas (`#graph` / `.graph-frame`): `#111827` (`#F1F5F9` text -> **`16.19:1`**)
  - Details panel (`.graph-panel`): `#1E293B` (`#F1F5F9` title -> **`13.35:1`**, `#CBD5E1` secondary text -> **`9.85:1`**)
  - Buttons / selects (`#show-core`, `#relation-filter`, `#zoom-fit`): `#F1F5F9` on `#0F172A` -> **`16.3:1`**
  - Relationship colors: `REQUIRES` (`#60A5FA` blue), `UNLOCKS` (`#F472B6` pink), `RELATED` (`#A78BFA` purple), `SOURCED_FROM` (`#2DD4BF` teal).
  - **Before (`https://archipelago-librarian.vercel.app/academic/graph`):** `#node-summary` and `#graph-status` rendered `#66887D` on `#FFFFFF` (**`3.9:1` — FAILS WCAG AA 4.5:1**).
- **Asset cleanup:** Removed `<link rel="stylesheet" href="/academic_light.css">` from both `academic_graph.html` files, replaced `host_research/ui/academic_light.css` with dark-safe variables (`#0F172A` / `#111827` / `#1E293B`), and fixed `/assets/research_archipelago_v2.webp` -> `/assets/research_archipelago_v2.png` in `host_inference/ui/academic_graph.html`.

---

## 3. Live Production Browser Verification (Desktop `1440×960` & Mobile `390×844`)

Verified via Playwright + `/usr/bin/google-chrome` (`headless=True`) against live production URLs:
- **`https://archipelago-blond.vercel.app/academic/graph`:**
  - `0` `/academic_light.css` 404s, `0` MIME/CSP errors, `0` `page_errors`.
  - Cytoscape: `12` nodes, `24` edges, `24/24` `curve-style: bezier`, `24/24` `target-arrow-shape: triangle`.
  - **Node tap (`Deep Learning`):** Populated `#node-title`, `#node-summary` (`186` chars), `#node-relationships` (`158` chars), `#node-sources` (`94` chars), `#explore-node`, `#ask-archipelago` (`/chat?q=Explain%20Deep%20Learning`). (`#take-quiz` remains hidden when a node has no quiz items.)
  - **Edge tap (`REQUIRES`):** `chain_of_thought_prompting:REQUIRES:gpt` revealed `#edge-details` with provenance `papers/Wei2022_ChainOfThought.pdf:chunk_020`.
  - **Controls:** `#relation-filter` (`REQUIRES` filtered `24 -> 4 -> 24`), zoom (`0.831 -> 1.039 -> 0.831`), `Fit` (`0.839`), `Reset` (`0.843`), `Explore Concept` + `← Back` (`#nav-back`) navigation verified.
  - **Mobile `390×844`:** `scrollWidth === innerWidth === 390` (`0` horizontal overflow), touch tap on `Neural Network` succeeded.
- **`https://archipelago-blond.vercel.app/research` & `/chat`:** Dark theme (`17.76:1` and `19.24:1`), `0` `page_errors`, `0` horizontal overflow on desktop & mobile; `/chat` verified XKIRO synthesis + inline Concept Graph card + PDF/DOI/arXiv citations + OPAC response.
- **Screenshots ZIP:** `Archipelago_Dual_Release_Screenshots.zip` (`11` PNGs + `verification_report.json` in `dual_release_screenshots/`).

---

## 4. Rate-Limit Security Hardening & 11-Test Dispositions

- **Rate-Limit Proxy Hardening (`host_inference/hostapp/security.py`, `tests/unit/test_rate_limit_proxy_headers.py`):** Fixed `RateLimiter.client_ip()` so untrusted client-supplied `X-Forwarded-For` headers are ignored unless `VERCEL` or `ARCHIPELAGO_TRUST_PROXY=1` is set (and even then prioritizes `X-Vercel-Forwarded-For` and reads the rightmost proxy-appended hop). Removed `X-Forwarded-For` rotation from `artifacts/validation/run_domain_benchmark.py`.
- **11 Test Dispositions:** `9` were outdated S1/S2a assertions (`render_graph=True` for S6 inline graph cards, `MULTI_CONCEPT` route, Koha OPAC wording/headers, date-coverage phrasing); `2` surfaced a genuine regression in `host_inference/engine/compose_catalog.py` (`library_inventory_reply` missed word-boundary `\bos\b`). All fixed and verified (`190 passed, 0 failed`).

---

## 5. Remaining Access / Governance Blockers

- **Librarian `shinaura` Vercel Deployment (`https://archipelago-librarian.vercel.app/`):** The updated `host_research/ui/academic_graph.html` and `host_research/ui/academic_light.css` are committed and pushed to `feature/s6-final-platform-integration` (`8b4c1bc`), but the local Vercel CLI session (`aura2026socials-8112`) only has membership in `archipelago-6383`. Promoting/deploying `host_research/` to `https://archipelago-librarian.vercel.app/` requires an authorized `shinaura` team member or Vercel team token.

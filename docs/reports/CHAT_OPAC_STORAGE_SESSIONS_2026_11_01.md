# Chat, OPAC, storage, and concurrent-user audit — 2026-11-01

## What is live

- The screenshot is the hosted `/chat` page on `archipelago-blond.vercel.app`. The public readiness endpoint returned HTTP 200 with 537 academic concepts. It reports `inference-only` and `ingestion: false`: Vercel answers from published data; it does not run the local ingestion workers.
- The public research intake endpoints returned 1,710 paper records, 64 campus pages, and recent topic/source activity. The chat endpoint requires a Supabase session, so an authenticated combined answer was not observed in production during this audit.
- The main chat implementation prepares an academic graph answer and may append up to three relevant saved research sources with original HTTPS URLs. Topic-inventory requests use the live research index. These are two context paths in one UI, not one merged knowledge graph. The research projection has topic, paper, provider, citation, and mention edges; research does not automatically add academic `REQUIRES`/`UNLOCKS` edges.
- The Library page's searchable student Research Activity section and source links are prepared locally, not yet live. The local change also shows OKF processing/field counts rather than implying every indexed paper has full-text OKF.

## OPAC and ingestible content

- The authorized Koha ODS snapshot has 109 filtered holdings and seven repository candidates. Its export date is 2026-10-03 and it reports `stale: true`. A fresh local dry run returned `changed: false`, 1,212 journal issues, 952 subject counts, and 2,882 subject-title entries.
- A Koha holding is bibliographic metadata and an availability lead. It is not automatically a PDF, chapter text, or a license to redistribute content. The live OPAC lookup endpoint returned HTTP 401 without a staff session; no authenticated full-text fetch was tested. Ingestion needs an authorized file, permitted open-access full text, or an approved publisher API/entitlement. PDF access and redistribution rights are separate decisions.
- The academic local worker can extract concepts and relation candidates from supplied pages. A direct `lib-qwen:latest` sample produced one concept but got an `unlocks` direction wrong, so its relations require review before graph publication. The research worker can save source records and partial OKF from abstracts or permitted full text; a direct `qwen3.5:0.8b` abstract call returned Ollama HTTP 500 during this audit. Indexed counts are not proof of successful model extraction for every paper.
- Research OKF has fields for provenance, methods, evidence, experiments, reproducibility, relevance, relationships, and author metrics. The `i10_index` and `h_index` come from author-level OpenAlex data; `m_index` is derived when enough career data exists. They are not a paper's own “i-index,” and absent observations remain null.

## Models and GPU

- Two *default model names* are configured for distinct extraction tasks: `lib-qwen:latest` for academic ingestion and `qwen3.5:0.8b` for research extraction. `dual-ingest:v3` and other tags are installed locally but are not the selected defaults. Installed tags do not mean simultaneously loaded GPU models. The chat's hosted phrasing path instead selects XKIRO or NVIDIA NIM when configured and otherwise retains the grounded draft.
- Local Ollama `/api/ps` reported both `lib-qwen:latest` and `qwen3.5:0.8b` with `size_vram: 0` when inspected. `nvidia-smi` reported no usable device. GPU utilization, model residency, and available VRAM therefore cannot be asserted from the screenshot. Vercel does not use this laptop's GPU for hosted ingestion.

## Hugging Face destination changes prepared locally

- [Library_books](https://huggingface.co/datasets/Prataykarali/Library_books/tree/main) is the destination for authorized uploaded books/papers and paper catalogue metadata/source pointers. The research worker now publishes `catalogs/research_papers/<job>.jsonl` there. It does not copy research PDFs unless rights and an authorized file path permit a separate librarian upload.
- [graphier](https://huggingface.co/datasets/Prataykarali/graphier/tree/main) is the destination for research OKF JSONL and the academic graph snapshot. The academic graph publisher now uploads `graph/okf_graph.json` after its local approved swap. Chat/reader link fallback and cold bootstrap now read book files/catalogue from Library_books and the graph from graphier. The old filename-based PDF copy in `scripts/sync_to_graphier.py` was removed.
- Both HF repositories were verified through the authenticated Hub API and are private. Existing historical PDFs in graphier were left untouched; this change routes future writes. No live dataset mutation or production deployment was performed in this audit.

## Concurrent users and sessions

- Supabase Auth identifies each user; verified profile roles separate student, faculty, librarian, and administrator access. The browser persists and refreshes sessions, and protected requests send a bearer token. Hosted daily chat quotas and research job enqueue limits use durable Supabase RPCs. Public read requests are not proof of authenticated multiuser behavior.
- Twelve concurrent public research-metrics requests all returned HTTP 200. This is a small read-only smoke test, not a capacity or mixed-role load test. Staff ingestion remains constrained by the local worker/GPU and its job queue.
- Two session issues remain: the browser idle timer is one hour while `AuthGuard` rejects a token after five minutes of inactivity in process-local state; logout invalidation and per-IP burst limiting are also process-local, so behavior can vary across Vercel instances. Supabase refresh/revocation is the durable identity layer, but these local guards should be made consistent before a multiuser launch.
- Vercel already includes a CDN and scales Functions for incoming requests. Cloudflare is not needed to make the current site support multiple user sessions. Prioritize session consistency, role-aware authenticated load testing, background-worker capacity, and cache/data latency before adding another proxy.

## Verification and release state

- 42 targeted tests passed for repository routing, model selection, research worker, academic route, and source links. Targeted Ruff lint/format and JavaScript syntax checks passed.
- The wider existing gate remains red (formatting, strict typing, and oversized files reported in the earlier pipeline audit), and the working tree contains extensive unrelated changes. The required human review gate has not run. These repository-routing changes are local and are **not yet reflected on Vercel**.

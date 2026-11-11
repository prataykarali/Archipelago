# Academic and research pipeline audit — 2026-11-01

## Scope and live evidence

- Production inference: `https://archipelago-archipelago-6383.vercel.app/api/readiness` returned HTTP 200, `ok: true`, 537 concepts, full corpus, `mode: inference-only`, `ingestion: false`, and research intake enabled.
- Production research store: `/api/research/intake/metrics` returned 1,710 papers and 64 campus pages. `/api/research/intake/activity` returned HTTP 200 with eight recent topics and eight recent source links. The most recent topic had 25 papers.
- The research transport at `https://archipelago-librarian.vercel.app/api/readiness` returned HTTP 200 with `ready: true`. Its protected research API returned HTTP 401 without a staff session. The production chat API also returned HTTP 401 without a Supabase session, so this audit cannot claim a live authenticated answer or completed job from a new request.
- Public Koha metadata returned HTTP 200 from the librarian deployment. The export is dated 3 October 2026 and covers a keyword-filtered 109 holdings, not a complete or current circulation feed.
- The previous local worker handoff records a completed 25-paper job with one verified full-text paper, six abstracts with extracted facts, and an OKF JSONL export to Hugging Face. This is historical evidence, not a fresh end-to-end job run in this audit.

## Academic books and papers

Academic ingestion runs locally with `lib-qwen:latest` by default. It extracts concept name, type, difficulty, summary, prerequisites, unlocks, related concepts, tags and source page. These records can be merged into the academic graph by the local ingestion worker. Vercel does not run this ingestion worker.

The local Ollama instance lists `lib-qwen:latest`, and a direct extraction call produced one concept. The result was **not reliable enough to merge unreviewed**: on a short attention passage it assigned `Transformer Encoder` a summary about scaled dot-product attention and an `unlocks` direction that contradicted the passage. The academic path is operational, but this sample failed relation quality.

## New research pipeline

The research worker is local. It discovers source records, ranks papers, uses permitted PDFs with Indra where possible, extracts literal abstract/PDF facts, persists rows in Supabase, and publishes per-paper OKF to Hugging Face. The research abstract extractor defaults to `qwen3.5:0.8b`; the academic extractor defaults to `lib-qwen:latest`. The chat synthesizer also uses `qwen3.5:0.8b` locally when available. `dual-ingest:v3` is installed locally but is not the default selected by these paths.

Research OKF includes identity, authors, venue, citation metrics, relevance, graph/novelty observations, methodology, experiments, evidence, reproducibility, relationships, integrity and provenance. `i10_index` is a first-author metric from OpenAlex, not a paper-level “i-index.” `h_index` is also sourced for the first author; `m_index` is derived when career age and h-index exist. Unknown values remain null. A contract field existing does not mean every paper has that observation.

The local research model is present in Ollama, but a direct abstract extraction attempt returned Ollama HTTP 500. The worker catches model request failures and can save metadata or fallback abstract facts, so a completed paper count alone does not prove model extraction succeeded for every paper. The recent completed job demonstrates partial extraction, not full paper coverage.

## Graph, chat and source links

The academic inference graph has 537 deployed concepts. The research graph is a separate live projection over saved rows. It builds topic-to-paper, provider-to-paper, citation, and literal title/topic concept-mention edges. It does not automatically add new research concepts or `REQUIRES`/`UNLOCKS` edges to the academic inference graph. A staff annotation edits concept details, not graph topology.

The main chat code can attach relevant saved paper excerpts and original HTTPS links to an academic graph answer, and can answer topic-inventory questions from the live store. A catalogue answer to an explicit paper/research request now also gets matching research evidence. It treats these as source evidence and retains the academic answer. It cannot yet reason over newly researched prerequisites as if they were established academic graph edges. Live chat behavior was not verified in this audit because the endpoint requires a session.

Some recent topic assignments need review: the latest “quantum computing in machine learning” activity includes a general supervised-learning survey. Topic count and ingestion status must not be presented as a relevance or OKF quality score.

## Student library view prepared in workspace

The Library page now includes a Research Activity section with searchable indexed topics, recent original paper links, OKF processing status, and the number of verified fields. It reads the existing public activity API and refreshes periodically. Staff controls remain linked separately. This change is local only. Production Library has not been redeployed, and the existing CI quality gate fails on unrelated formatting, strict typing, and file-size baselines. The working tree contains extensive pre-existing changes, so a production deploy would include work outside this audit.

## Verification

- 26 targeted academic/research tests passed; 11 graph/reply/overview tests passed.
- Targeted Ruff lint and format checks and JavaScript syntax check passed for changed code.
- The full quality gate failed: five unrelated files need formatting, 763 existing strict typing errors were reported in the current environment, and four existing files exceed its 400-line threshold.
- No new research job or production graph mutation was performed.

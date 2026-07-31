# Daily Handoff

## 2026-07-26 - Lead Engineer + ML Engineer

### Built

- Switched inference-time answer generation and lightweight query classification
  to the Gemini API.
- Configured `gemini-flash-lite-latest` as the primary model with
  `gemini-flash-latest` as fallback.
- Kept retrieval, graph traversal, deterministic grounded fallback, citation
  validation, and final response cleansing in Python.
- Added generation provenance to chat stream metadata and Gemini status to the
  readiness endpoint.
- Removed inference startup loading and the remaining callable Aura/Qwen local
  text generator.

### Verification

- Confirmed the configured Gemini model with a live API request.
- Focused Gemini, routing, citation, streaming, and inference contract tests
  pass.
- Confirmed the chat UI requests Gemini synthesis and no inference runtime
  imports or starts Ollama.

### Deferred

- Repository-wide quality gates still report extensive pre-existing lint,
  typing, file-size, architecture, and magic-number debt outside this change.
- Local models used by ingestion or embedding workflows remain available; they
  are not used to generate inference replies.

### Next Pair

- Rotate the Gemini credential because it was shared through a chat message,
  then update the ignored local `.env` and deployment secret.
- Run the full live E2E suite when the complete corpus and all three services
  are available.

## 2026-07-26 - Lead Engineer + ML Engineer

### Built

- Expanded the Gemini `generateContent` pool to eleven text models.
- Added support for both `models/gemini-...` and `gemini-...` configuration
  forms.
- Configured ordered failover rather than parallel fan-out: HTTP 404/429 marks
  the current model unavailable temporarily and advances to the next model.

### Next Pair

- Monitor readiness `synthesis.gemini.model` and `exhausted_models` to determine
  which aliases provide the best quota and latency for the deployment key.

## 2026-07-26 - Lead Engineer + QA Engineer

### Built

- Replaced neighbor-wide citation retrieval with generic target-concept
  evidence selection.
- Added explicit target-term eligibility, document diversity, page
  deduplication, and a four-source cap.
- Removed chunk IDs from Gemini context and moved deep links exclusively into
  structured citation metadata.
- Added deterministic bare `[S#]` rendering, route-free source labels, and a
  maximum of two inline uses per source.
- Prevented dependent clauses such as "LoRA and how it..." from being
  misrouted as independent multi-topic queries.

### Verification

- Live LoRA response used only `Hu2021_LoRA.pdf` and
  `Dettmers2023_QLoRA.pdf`.
- No `/api/page-view`, `doc_id`, `chunk_NNN`, page-arrow, network-security,
  GAT, or unrelated-attention leakage reached visible prose.
- Focused evidence, pipeline, citation-hygiene, and routing regressions passed.

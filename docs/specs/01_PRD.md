# 01_PRD (Product Requirements Document)

## 1. Product Vision
Archipelago is a Curriculum-aware Hybrid Graph-Vector RAG Institutional Library Intelligence System designed for IEM/UEM/institutional libraries. It bridges physical library assets and digital learning, combining vector embeddings with an explicit knowledge graph to deliver precise, citation-backed intelligence, personalized diagnostic learning, and deep catalog routing.

## 2. User Personas
- **Students**: Anonymous or authenticated users engaging in campus reading, querying concepts, and experiencing personalized learning through diagnostics.
- **Faculty**: Educators seeking diagnostic analytics, learning gap analysis, and curriculum mapping.
- **Librarians**: Administrators responsible for ingestion, catalog management, demand analytics, and OPAC integration.
- **Developers**: Engineers interacting with the query inspector, debugging mode, and graph admin features.

## 3. Core Product Capabilities & Status

| Capability | Status | Notes |
| :--- | :--- | :--- |
| **Six Response Contracts** | WORKING | Foundation immutable (GRAPH_SYNTHESIS, CATALOG_SHELF_ROUTING, AUTH_GATEWAY, MCQ_DIAGNOSTIC, INGESTION_ANALYSIS, GUARDRAIL_INTERCEPT) |
| **Chat UI** | WORKING | Streaming SSE responses are fully implemented |
| **Knowledge Graph Viz** | WORKING / PARTIAL | Backend/Full graph (WORKING); Mini chat graph (WORKING); Personalized Q&A graph (PARTIAL — MCQ_MAX_QUESTIONS currently hardcoded to 4, spec says 10) |
| **Book Stack Experience** | PARTIAL | `books_showcase_src.tsx` exists as symlink stub, `library_showcase_3d.js` is a 36-byte stub |
| **Page-level Citation System** | WORKING | Deep links (`#page=N`) work for 40 Pearson and 21 HF books |
| **Adaptive Learning** | WORKING (Capped) | Diagnostic MCQs functional but currently capped at 4 questions (needs to be 10) |
| **Physical Inventory Lookup** | WORKING | Works via Koha ODS and Pearson bookshelf mappings |
| **OCR Ingestion** | WORKING | Operational via Tesseract |
| **Pearson Deep Linking** | PARTIAL | Cold redirect fails without session cookie |
| **HuggingFace Integration** | WORKING / PENDING | Currently uses `Prataykarali/Library_books`, needs migration to `Prataykarali/graphier` |
| **Caching** | PARTIAL | `cache_service.py` exists with Supabase backend but requires Supabase tables |
| **Rate Limiting** | WORKING | Implemented in `rate_limit.py` |
| **Query Inspector** | NOT BUILT | Glass-Box Diagnostics UI not yet implemented |
| **Fading Mastery** | NOT BUILT | Time decay functionality missing |
| **Confidence-Aware Diagnostics** | NOT BUILT | Needs implementation |
| **Socratic Misconceptions** | NOT BUILT | Detection logic not yet implemented |
| **OPAC Live Integration** | NOT BUILT | Currently uses a static catalog lookup |
| **Librarian Intelligence Dash** | NOT BUILT | Aggregate dashboard pending |
| **Faculty Diagnostic Mode** | NOT BUILT | Faculty persona UI/UX pending |
| **AdMob/Monetization** | NOT BUILT | Pending integration |

## 4. Landing Page Requirements
The landing page must contextualize the application for the IEM, UEM, and Archipelago institutional library setting.
- **Current Status**: `landing.html` successfully implements the KNOWLEDGE OPERATIONS eyebrow and dual CTAs (WORKING).

## 5. Non-Functional Requirements
- **Performance targets**: Low latency inference, streaming chunk rendering.
- **Security**: Strict PII handling, no exposed credentials (see [00_MASTER_RULES](00_MASTER_RULES.md)).
- **Accessibility**: Support screen readers, high contrast modes for textual content, keyboard navigation for the chat UI.
- **Institutional Branding**: The UI must reflect IEM/UEM institutional color palettes and typography.

## 6. Success Metrics
- **Response Accuracy**: 0% hallucination on physical shelf routing and page citations.
- **Latency SLOs**:
  - p50 < 500ms for initial SSE chunk.
  - p95 < 20s for full response completion.
- **Cache Hit Ratio**: > 40% on static queries and frequent syllabus questions.
- **Ingestion Throughput**: High accuracy processing of syllabus PDFs and OCR workloads without blocking the primary chat thread.

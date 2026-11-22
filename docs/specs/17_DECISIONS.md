# Architectural Decision Records

## ADR-001: KùzuDB as Graph Database
- **Status**: Accepted
- **Context**: Need embedded columnar graph DB for concept topology
- **Decision**: Use KùzuDB (embedded C++ columnar) over Neo4j (server-based) or NetworkX (in-memory only)
- **Rationale**: Embedded = no separate server process, columnar = fast traversal, supports Cypher, atomic swap via POSIX rename
- **Consequence**: Graph limited to single-writer (swap_lock), no distributed graph

## ADR-002: Six Response Contracts
- **Status**: Accepted
- **Context**: Need deterministic routing to prevent LLM from answering everything
- **Decision**: Six immutable contract types (GRAPH_SYNTHESIS, CATALOG_SHELF_ROUTING, AUTH_GATEWAY, MCQ_DIAGNOSTIC, INGESTION_ANALYSIS, GUARDRAIL_INTERCEPT)
- **Rationale**: Every route maps to exactly one contract, graph render is pure function of contract
- **Consequence**: New query types require explicit contract mapping in ROUTE_CONTRACT

## ADR-003: xkiro as Primary LLM Provider
- **Status**: Accepted
- **Context**: Need OpenAI-compatible inference for response polishing
- **Decision**: xkiro (free tier qwen3.8-max) as primary, NVIDIA NIM as fallback
- **Rationale**: Free tier = zero cost for institutional deployment, OpenAI-compatible = one code path
- **Consequence**: Depends on xkiro availability, fallback to NVIDIA requires API key

## ADR-004: Vanilla HTML5 Frontend (No Framework)
- **Status**: Accepted
- **Context**: Frontend serves institutional library kiosks and student browsers
- **Decision**: Vanilla HTML5/CSS3/JS with D3.js and Three.js, no React/Vue/Angular
- **Rationale**: Zero build step, works on any browser, no npm dependency chain, kiosk-friendly
- **Consequence**: No component reuse framework, manual DOM manipulation, harder to maintain complex UI

## ADR-005: Dual Runtime Architecture (host_inference/ vs archipelago/)
- **Status**: Needs Resolution
- **Context**: AntDeploy runs host_inference/hostapp/, local development uses archipelago/ package
- **Decision**: UNRESOLVED — both coexist with significant overlap
- **Rationale**: host_inference/ was built for lightweight hosted deployment, archipelago/ was refactored for clean architecture
- **Consequence**: Code duplication, confusion about canonical runtime, maintenance burden
- **Action Required**: Decide canonical runtime and consolidate

## ADR-006: In-Memory JSON Graph for Hosted Deployment
- **Status**: Accepted
- **Context**: AntDeploy has no persistent disk for KùzuDB
- **Decision**: Export graph to okf_graph.json (~6.3MB), load in-memory via LibraryGraph
- **Rationale**: Stateless deployment, fast cold start, no DB file management
- **Consequence**: Graph updates require re-export + re-deploy, no live ingestion on hosted

## ADR-007: Supabase for Authentication
- **Status**: Accepted
- **Context**: Need managed auth with JWT, roles, and RLS
- **Decision**: Supabase (PostgreSQL + JWT) with roles: student, librarian, admin
- **Rationale**: Managed service, JWT standard, row-level security, free tier sufficient
- **Consequence**: External dependency, faculty role migration pending

## ADR-008: Snowflake Arctic for Embeddings
- **Status**: Accepted
- **Context**: Need dense embeddings for semantic similarity ranking
- **Decision**: Snowflake Arctic Embed (snowflake-arctic-embed-m-v1.5, 1024-dim or 384-dim hash)
- **Rationale**: Good quality, runs locally on CPU, no API cost
- **Consequence**: Model loading adds ~2s to cold start, GPU optional

## ADR-009: Section-Aware PDF Chunking
- **Status**: Accepted (with known debt)
- **Context**: Academic PDFs have TOC, bibliography, index that pollute graph
- **Decision**: PyMuPDF section-aware chunking via pdf_chunk.py
- **Rationale**: Preserves page boundaries, section headers, structural context
- **Known Debt**: TOC/bibliography/index filtering not yet implemented (F7 audit finding)

## ADR-010: Grounded Draft + Optional LLM Polish
- **Status**: Accepted
- **Context**: LLM may be unavailable or drop citations
- **Decision**: Always generate grounded draft from graph data first, then optionally polish with LLM
- **Rationale**: Draft is source of truth, LLM only improves phrasing
- **Consequence**: Answers always available even without LLM, citations preserved

## ADR-011: DENY-ALL Fetch Policy
- **Status**: Accepted
- **Context**: Outbound web fetches could leak institutional data or violate terms
- **Decision**: Default DENY-ALL via fetch_policy.py, explicit allowlist required
- **Rationale**: Security-first, compliance with robots.txt, audit trail
- **Consequence**: New sources require explicit allowlist entry

## ADR-012: Diagnostic MCQ from Graph Prerequisites
- **Status**: Accepted (with planned extension)
- **Context**: Personalized learning needs knowledge gap assessment
- **Decision**: Generate MCQs from K-hop prerequisite chain, distractors from neighbor pool
- **Rationale**: Graph-grounded questions, no LLM needed for question generation
- **Current Limit**: 4 questions max (MUST increase to 10 per spec)
- **Planned**: Confidence calibration, fading mastery, adaptive budget

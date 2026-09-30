# ADR 0002: Context Serialization Boundary (Preventing Internal DB Metadata Leakage)

## Status
Accepted

## Context
When retrieved database records are passed into LLM prompt templates as raw Python dictionaries, internal infrastructure metadata (such as `chunk_id`, `doc_id`, internal URLs like `/api/page-view`, table column names, or raw system tokens) can leak into model responses. This poses an operational security hazard and degrades pedagogical clarity.

## Decision
1. **Strict Serialization Layer:** All retrieved text passages must pass through `ContextSerializer` before entering prompt assembly.
2. **Internal vs Model Representation:**
   - **Internal Representation:**
     ```python
     @dataclass(frozen=True)
     class RetrievedChunk:
         source_id: str
         document_title: str
         page_number: int
         text: str
         content_hash: str
     ```
   - **Model-Facing Representation:**
     ```text
     [S1]
     Document: Operating Systems: Three Easy Pieces
     Page: 48

     Text:
     Virtual memory translates virtual addresses to physical addresses...
     ```
3. **Automated Sanitization Firewall:** The serializer systematically filters out `/api/`, `/internal/`, `/admin/`, `doc_id:`, `chunk_id:`, and internal file paths.
4. **Adversarial Regression Testing:** Automated unit tests intentionally inject malicious metadata strings and assert 100% rejection from the model prompt.

## Consequences
- The LLM context never receives internal database keys or routing artifacts.
- Synthesized citations strictly conform to clean badges (`[S1]`, `[S2]`).

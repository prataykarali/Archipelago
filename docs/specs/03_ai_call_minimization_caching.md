# AI CALL MINIMIZATION & SUPABASE CACHING

## 1. Core Objective

**Minimize external/expensive AI inference calls without reducing answer quality.**

The system must check existing cached knowledge before invoking the AI model.

Target flow:

```text
Student Query
     ↓
Authentication
     ↓
Rate Limit
     ↓
Normalize Query
     ↓
Cache Lookup
     │
     ├── HIT ───────────────→ Return Cached Response
     │
     └── MISS
           ↓
      Retrieval Cache
           ↓
      Graph Retrieval
           ↓
      Context Construction
           ↓
      AI Inference
           ↓
      Validate Response
           ↓
      Cache Response
           ↓
      Return
```

---

# 2. Supabase Response Cache

Use a dedicated Supabase cache table for reusable responses.

Example:

```text
ai_response_cache

cache_key
normalized_query
query_hash
response
sources
graph_data
roadmap_data
model_version
graph_version
prompt_version
created_at
expires_at
hit_count
```

The cache key should incorporate the important context that affects correctness:

```text
hash(
    normalized_query
    + graph_version
    + library_version
    + model_version
    + prompt_version
)
```

This prevents an old answer from being returned after the underlying knowledge graph or model changes.

---

# 3. Cache HIT

For a cache hit:

```text
Query
 ↓
Supabase Cache
 ↓
Valid cached response
 ↓
Return immediately
```

**Do not call the AI API.**

The response should still contain:

* answer;
* source links;
* graph;
* roadmap;
* relevant library resources.

---

# 4. Cache MISS

Only when no valid response exists:

```text
Query
 ↓
Retrieve relevant knowledge
 ↓
Graph retrieval
 ↓
AI inference
 ↓
Response validation
 ↓
Supabase cache
 ↓
Return
```

---

# 5. Semantic Query Normalization

Normalize obvious variations before caching.

For example:

```text
"What is machine learning?"
"Explain machine learning"
"Can you explain machine learning?"
"Tell me about machine learning"
```

should be able to share retrieval/cache results where the system determines they are semantically equivalent.

Do **not** blindly merge semantically different questions.

Use:

```text
exact normalized cache
+
retrieval cache
+
optional semantic similarity cache
```

rather than relying only on exact string matching.

---

# 6. Retrieval Cache

Cache expensive retrieval operations separately from final AI responses.

Example:

```text
retrieval_cache

query_hash
concept_ids
document_ids
graph_nodes
graph_edges
retrieval_version
created_at
expires_at
```

This allows:

```text
Query
 ↓
Cached retrieval
 ↓
New prompt/context
 ↓
AI
```

without repeating graph/vector retrieval.

---

# 7. Graph Cache

Frequently requested graph neighborhoods should also be cached.

Example:

```text
graph_cache

concept_id
graph_version
nodes
edges
roadmap
created_at
expires_at
```

Common queries such as:

```text
"Prerequisites for Transformers"
"ML roadmap"
"Neural network prerequisites"
```

should not repeatedly execute identical expensive graph traversals.

---

# 8. Request Deduplication

Handle simultaneous identical requests.

Example:

```text
100 students
     │
     ├── "What is backpropagation?"
     ├── "What is backpropagation?"
     ├── "What is backpropagation?"
     └── ...
              ↓
       Request Deduplication
              ↓
       ONE inference request
              ↓
       Shared result
```

Do not allow 100 simultaneous cache misses to generate 100 AI calls.

Use a short-lived distributed lock / request-coalescing mechanism.

---

# 9. Cache Invalidation

Caching must never make the librarian knowledge stale indefinitely.

Invalidate/re-version caches when:

```text
Graph changes
Library changes
Book metadata changes
New papers/books are indexed
Model changes
Prompt changes
Retrieval algorithm changes
```

Prefer versioned cache keys over manually deleting millions of cache entries.

Example:

```text
graph_version = 42

cache_key:
query + graph_version + model_version
```

After ingestion:

```text
graph_version = 43
```

Old responses automatically become irrelevant.

---

# 10. Don't Cache Everything

Do **not** cache responses containing:

* private user data;
* user-specific information;
* sensitive information;
* personalized authorization-dependent results;

unless the cache is explicitly scoped to that user/session.

Public knowledge questions are the primary candidates for shared caching.

---

# 11. AI API Budget Protection

Add an AI-call metric:

```text
ai_requests_total
ai_cache_hits
ai_cache_misses
ai_requests_saved
tokens_saved
inference_latency
```

Dashboard:

```text
Total student requests       100,000
Cache hits                    72,000
AI calls                      28,000
AI calls avoided              72,000
Cache hit ratio                  72%
```

The exact target should be determined from real traffic rather than hard-coded.

---

# 12. Final Student Request Path

The production path should therefore become:

```text
                    STUDENT
                       │
                       ▼
                 AntDeploy API
                       │
                 Auth + Rate Limit
                       │
                       ▼
                Query Normalizer
                       │
             ┌─────────┴─────────┐
             │                   │
          Cache HIT           Cache MISS
             │                   │
             ▼                   ▼
        Supabase Cache      Retrieval Cache
             │                   │
             │                   ▼
             │              Graph Retrieval
             │                   │
             │                   ▼
             │             Context Builder
             │                   │
             │                   ▼
             │              AI Inference
             │                   │
             │                   ▼
             │             Response Validator
             │                   │
             │                   ▼
             │              Supabase Cache
             │                   │
             └──────────┬────────┘
                        ▼
                  Student Response
```

### Main principle

**Supabase should act as the persistent shared response/retrieval cache, while the library computer remains the authoritative institutional knowledge/graph system.**

That gives Archipelago three useful layers:

**HF → model distribution**

**Library Docker → ingestion + graph + institutional knowledge**

**AntDeploy + Supabase → scalable serving + caching + authentication + inference orchestration**

This is much more appropriate for an institution than sending every student question directly to an AI API.

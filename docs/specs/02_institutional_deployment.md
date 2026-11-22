# Archipelago — Institutional Deployment

## 1. Three-Part Architecture

### A. Central Inference/API — AntDeploy

Deploy the production-facing:

* Chat API
* Retrieval API
* Inference orchestration
* Authentication/authorization
* API rate limiting
* Graph/query API
* Library API
* Health/metrics endpoints

**AntDeploy is the public application/API layer.**

Do not expose database, graph, or model secrets to the frontend.

---

### B. Library Computer — Docker Appliance

The institution's **library/IEDC computer** should run a self-contained Docker stack containing:

```text
archipelago-ingestion
archipelago-graph
archipelago-library-index
archipelago-sync
```

This machine owns the institutional knowledge state.

It should be possible to ship the entire stack as:

```bash
docker compose pull
docker compose up -d
```

or as an offline/exportable Docker image bundle.

The library computer should therefore remain useful even if the central ingestion service changes.

---

### C. Downloadable Local Ingestion Model — Hugging Face

Publish the **ingestion/extraction model** as a versioned Hugging Face model repository.

The library computer downloads the pinned model:

```bash
hf download <ORG>/<ARCHIPELAGO-INGESTION-MODEL> \
  --revision <VERSION>
```

Hugging Face supports version/revision-pinned model downloads and local caching, making this suitable for distributing the model separately from the institutional Docker stack.

The Docker ingestion service loads that local model.

### Separation

```text
HF
 │
 │ model download
 ▼
Library Computer
 │
 ├── Docker
 │    ├── Ingestion
 │    ├── Graph
 │    ├── Index
 │    └── Sync
 │
 └── Local model
       │
       ▼
   extraction
```

**Do not put the model inside the main application image if that makes updates unnecessarily large.**

---

# 2. Institutional Data Flow

```text
                 INTERNET
                    │
                    ▼
             ┌─────────────┐
             │  AntDeploy  │
             │ API + Chat  │
             │ Inference   │
             └──────┬──────┘
                    │
              secure API
                    │
                    ▼
        ┌──────────────────────┐
        │ Library / IEDC PC    │
        │                      │
        │ Docker               │
        │ ├─ Ingestion         │
        │ ├─ Graph             │
        │ ├─ Library Index     │
        │ └─ Sync              │
        │                      │
        │ Local HF Model       │
        └──────────┬───────────┘
                   │
                   ▼
          Institutional data
```

The library computer should **not send the entire institutional corpus to AntDeploy for every request**.

Cache and index institutional knowledge locally.

Only send the minimum required retrieval context / graph result / authorized data to the inference API.

---

# 3. 5,151-Node Graph

The existing **5,151-node graph** is a baseline dataset/integrity target.

CI must verify:

```text
5,151 baseline nodes
+
valid edges
+
no broken references
+
no duplicate IDs
+
valid provenance
```

If ingestion legitimately changes the graph to 5,300 nodes, CI should not blindly fail; it should validate the graph against the expected dataset/version and produce a graph diff.

---

# 4. Ingestion Package

Make ingestion independently portable.

Example:

```text
archipelago-ingestion/
├── Dockerfile
├── docker-compose.yml
├── models/
├── ingestion/
├── adapters/
├── validators/
├── graph_writer/
├── index_writer/
└── CLI
```

Commands:

```bash
archipelago ingest --source dataset.csv
archipelago ingest --source library.ods
archipelago ingest --source huggingface
archipelago graph validate
archipelago graph stats
archipelago graph diff
```

A second institution should be able to receive:

```text
Docker image
+
configuration
+
HF model identifier/version
+
database/graph configuration
```

and deploy the ingestion system without modifying the source code.

---

# 5. Automatic Update Loop

The library computer should support:

```text
New CSV / ODS / HF dataset
          ↓
Change detection
          ↓
Schema validation
          ↓
Deduplication
          ↓
Local ingestion model
          ↓
Concept extraction
          ↓
Relationship extraction
          ↓
Graph validation
          ↓
Graph update
          ↓
Library index update
          ↓
Statistics update
          ↓
Sync/API notification
```

This must be **idempotent**.

---

# 6. CI/CD Must Test the Real System

Do not make CI merely run:

```bash
pytest
npm test
```

The pipeline must include real staging tests:

```text
BUILD
 ↓
UNIT TESTS
 ↓
INTEGRATION TESTS
 ↓
GRAPH INTEGRITY
 ↓
BUILD DOCKER
 ↓
START LIBRARY STACK
 ↓
DOWNLOAD/PIN HF MODEL
 ↓
RUN REAL INGESTION
 ↓
VERIFY NEW BOOK
 ↓
VERIFY NEW CONCEPT
 ↓
VERIFY GRAPH RELATION
 ↓
VERIFY LIBRARY UPDATE
 ↓
DEPLOY ANTIDEPLOY STAGING
 ↓
REAL INFERENCE REQUEST
 ↓
VERIFY ANSWER
 ↓
VERIFY SOURCE LINK
 ↓
VERIFY GRAPH RESPONSE
 ↓
VERIFY ROADMAP
 ↓
VERIFY RATE LIMIT
 ↓
SMOKE TEST
 ↓
PRODUCTION
```

---

# 7. Live End-to-End Test

CI should inject a known test document.

For example:

```text
TEST_BOOK
    ↓
ingestion
    ↓
concept = X
    ↓
requires = Y
```

Then automatically verify:

```text
Book exists in library       ✓
X exists in graph            ✓
Y exists in graph            ✓
X → REQUIRES → Y             ✓
Chat retrieves TEST_BOOK     ✓
Chat answers query           ✓
Source URL returned          ✓
Graph returned               ✓
Roadmap returned             ✓
```

This proves that **ingestion → graph → library → retrieval → inference → UI** actually works.

---

# 8. 5K+ Student Architecture

Do **not** design around:

> 5,000 students = 5,000 inference requests/sec.

Those are different quantities.

For an institution with 5,000+ students, estimate **concurrent active users and request burst rate**, not enrollment alone.

If the expected peak is currently only **100–200 requests/sec**, design the system so that the API layer can scale horizontally beyond that rather than trying to make one inference server handle everything.

Recommended:

```text
                 Load Balancer
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       API #1       API #2       API #3
          │            │            │
          └────────────┼────────────┘
                       ▼
                Retrieval Layer
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
        Graph/Index          Cache
             │
             ▼
       Inference Queue
             │
       ┌─────┼─────┐
       ▼     ▼     ▼
    Worker Worker Worker
```

The critical principle is:

### **Do not make every student request perform expensive ingestion or graph construction.**

Those are background/offline workloads.

Student request:

```text
Query
 ↓
Auth
 ↓
Rate limit
 ↓
Cache
 ↓
Retrieve
 ↓
Graph lookup
 ↓
Inference
 ↓
Response
```

Ingestion:

```text
New data
 ↓
Queue
 ↓
Worker
 ↓
Local model
 ↓
Graph update
 ↓
Index update
```

These must be separate workloads.

---

# 9. Rate Limiting

Implement rate limiting at the AntDeploy API boundary.

For example:

```text
anonymous      → very low
authenticated  → normal student limit
library/admin  → higher limit
ingestion      → separate service limit
```

Do not use one global rate limit for everything.

Return proper:

```text
429 Too Many Requests
Retry-After
```

and prevent one student/client from exhausting inference capacity.

---

# 10. Scaling Strategy

For 100–200 peak API requests/sec:

### Scale cheaply first

Use:

```text
CDN/cache
+
horizontal API replicas
+
retrieval caching
+
graph caching
+
request queue
+
inference worker pool
```

before simply buying a massive inference machine.

Also distinguish:

```text
API requests/sec
≠
LLM inference requests/sec
≠
tokens/sec
≠
concurrent generations
```

**Inference capacity must ultimately be sized from tokens/sec, prompt length, generation length, model size, batching capability and latency SLO—not student count alone.**

---

# 11. Institutional Deployment Principle

The final product should therefore behave as:

```text
                  STUDENTS
                     │
                     ▼
             ┌───────────────┐
             │ AntDeploy API │
             │ Auth + Limit  │
             │ Chat + Inference
             └───────┬───────┘
                     │
              Retrieval Context
                     │
                     ▼
          ┌─────────────────────┐
          │ Library / IEDC PC   │
          │                     │
          │ Graph               │
          │ Library Index       │
          │ Ingestion           │
          │ Local HF Model      │
          └─────────────────────┘
```

**AntDeploy = serving/control plane.**

**Library computer = institutional knowledge/data plane.**

**Hugging Face = versioned model distribution plane.**

That separation is the important architectural decision: the institution can update its knowledge base and ingestion system independently, while the public inference/API layer remains scalable and deployable.

# ARCHIPELAGO — PRODUCTION ENGINEERING & CI/CD IMPLEMENTATION BRIEF

## 1. Mission

Take the **existing Archipelago project** and bring it to a production-ready state while **preserving all existing functionality**.

Do not rewrite working systems unnecessarily.

Archipelago must remain a **knowledge/librarian system**, not just a chatbot:

* books and papers remain indexed;
* ingestion remains available;
* the local models remain available for ingestion/extraction;
* the knowledge graph remains the core knowledge structure;
* graph-aware chat remains functional;
* library context remains available to the assistant;
* roadmap/relation retrieval remains functional;
* source links remain directly accessible;
* production inference/API infrastructure is deployed securely.

### Important architecture requirement

**Keep the existing local ingestion pipeline and local extraction models.**

The local model/inference used for ingestion, concept extraction, graph construction, etc. should NOT be unnecessarily replaced.

However, the **production-facing inference/API layer should be deployable on AntDeploy**, with proper authentication, API rate limiting, monitoring, failure handling and CI/CD.

---

# 2. Product Architecture

The target architecture should approximately be:

```text
                    ┌─────────────────────┐
                    │   Archipelago UI    │
                    │ Landing / Chat /    │
                    │ Library / Graph     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Authenticated API │
                    │    AntDeploy        │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼──────────────────┐
             ▼                 ▼                  ▼
        Chat/Inference      Retrieval          Library
             │                 │                  │
             ▼                 ▼                  ▼
        Inference API       Graph RAG          Supabase
             │                 │
             ▼                 ▼
       Model Provider       Graph DB
                               │
                               ▼
                         Knowledge Graph

LOCAL / CONTROLLED PIPELINE

Books / Papers / CSV / ODS / HF
              │
              ▼
       Local Ingestion
              │
              ▼
       Local Extraction Model
              │
              ▼
       Concept / Relation Extraction
              │
              ▼
       Graph Validation
              │
              ▼
       Graph + Index Update
              │
              ▼
       Library Statistics
```

The exact implementation may differ after repository inspection, but the architectural principles must remain.

---

# 3. Core Requirement: The Assistant Must Actually Work

The chat system should not merely return technically valid responses.

It must correctly answer **all normal supported queries using available library/graph context**.

Test questions should include:

* general knowledge questions;
* book-related questions;
* paper-related questions;
* library questions;
* concept questions;
* prerequisite questions;
* "what should I learn first?" questions;
* relation questions;
* roadmap questions;
* comparison questions;
* source questions;
* "which book covers X?" questions;
* "what concepts are related to X?" questions;
* graph-navigation questions;
* unsupported queries;
* ambiguous queries;
* malformed queries;
* empty queries;
* very long queries;
* repeated queries.

The response should gracefully distinguish:

```text
Known from Archipelago
        ↓
Retrieved from sources
        ↓
Inferred through graph
        ↓
Not available / insufficient evidence
```

The system must **not fabricate books, papers, graph relationships, URLs or library statistics**.

---

# 4. Chat UI — FULL PRODUCTION EXPERIENCE

The chat UI must include:

### Response

* Correct answer.
* Proper formatting.
* Markdown where appropriate.
* Source attribution.
* Book/paper references.
* Relevant graph context.

### Graph

When applicable, show an **interactive graph directly inside the chat**.

Example:

```text
User:
"What should I learn before Transformers?"

A:
Transformers depend on:

Attention
   ↓
Self-Attention
   ↓
Sequence Modeling
   ↓
Transformer Architecture
```

The actual graph must be generated from the Archipelago graph rather than a fake frontend diagram.

### Roadmap

When the query implies learning progression, show:

```text
Prerequisite
      ↓
Concept
      ↓
Current Target
      ↓
Next Concepts
```

### Sources

Each source should provide a clickable link.

---

# 5. Direct Source Links — NON-NEGOTIABLE

When a book, paper or dataset is mentioned, the user should be able to click through to the **exact relevant source page** whenever an authorized source URL exists.

This must work from:

### Chat

```text
Assistant response
       ↓
[Book]
       ↓
Exact source page
```

### Library Details

```text
Book Details
       ↓
Source
       ↓
Exact Pearson / Hugging Face / other verified page
```

### Book Stack / Library Cards

```text
Book Card
   ↓
Open Source
   ↓
Exact source page
```

Do NOT merely link users to a generic homepage if an exact source page is available.

Known resources to integrate where applicable:

* IEM CRP: `https://iemcrp.com/`
* UEMK OPAC: `https://uemk-opac.l2c2.co.in/`

For Hugging Face and Pearson, use the **exact verified dataset/book/content page associated with the indexed record**, not a generic homepage.

Never fabricate URLs.

---

# 6. Library

The library must function as a real knowledge catalogue.

Each record should support, where available:

```text
Title
Author
Type
Publisher
Year
ISBN / Identifier
Source
Source URL
Indexed Status
Concepts
Graph Connections
Related Resources
```

Library statistics must be generated from actual data.

Do not hard-code:

```text
5151 nodes
500 books
200 papers
```

Instead calculate them from the authoritative data layer.

---

# 7. Knowledge Graph

The graph must remain a first-class component.

Support:

```text
CONCEPT
BOOK
PAPER
AUTHOR
DOMAIN
RESOURCE
```

and relationships such as:

```text
REQUIRES
UNLOCKS
RELATED
MENTIONED_IN
AUTHORED_BY
BELONGS_TO
```

The actual existing schema must be preserved where already implemented.

### Graph UI

The graph UI should support:

* zoom;
* pan;
* node selection;
* relationship visibility;
* node details;
* source information;
* concept highlighting;
* neighborhood exploration;
* graph filtering;
* roadmap visualization;
* graph loading states;
* empty graph state;
* large graph handling.

Do not load an unnecessarily huge graph into the browser.

Use neighborhood/filtered retrieval where appropriate.

---

# 8. 5151 Graph Validation

The existing **5151 graph** must be treated as a production regression target.

CI must verify:

```text
node count
edge count
duplicate nodes
orphan nodes
invalid edges
duplicate edges
invalid relationship types
missing source attribution
broken references
```

The test should detect accidental graph shrinkage or corruption.

Example:

```text
Expected baseline:
5151 nodes

Actual:
5151 nodes

Status:
PASS
```

If the number legitimately changes because ingestion added resources, CI should compare against the expected dataset/version rather than blindly failing.

---

# 9. Ingestion Must Remain LOCAL

Do not remove the current local ingestion architecture.

Local ingestion should support:

```text
Hugging Face datasets
Books
Papers
CSV
ODS
Authorized library metadata
Other configured sources
```

Pipeline:

```text
Source
 ↓
Downloader / Reader
 ↓
Schema Validator
 ↓
Normalizer
 ↓
Deduplication
 ↓
Local Model
 ↓
Concept Extraction
 ↓
Relation Extraction
 ↓
Graph Validation
 ↓
Graph Update
 ↓
Library Update
 ↓
Index Update
```

The pipeline must be **idempotent**.

Running it twice must not duplicate:

* books;
* papers;
* concepts;
* nodes;
* edges;
* library records.

---

# 10. Automated Graph + Library Population

Implement an automated update pipeline.

When a new authorized dataset/CSV/ODS is introduced:

```text
New File
   ↓
Detect Change
   ↓
Validate
   ↓
Parse
   ↓
Normalize
   ↓
Compare Existing Data
   ↓
Identify New/Changed Records
   ↓
Run Local Extraction Model
   ↓
Generate Concepts
   ↓
Generate Relations
   ↓
Validate Graph
   ↓
Update Graph
   ↓
Update Library
   ↓
Update Statistics
   ↓
Run Retrieval Test
```

It should support:

```text
CREATE
UPDATE
UNCHANGED
DELETE / RETIRE
```

where deletion is appropriate.

---

# 11. LIVE INGESTION TESTING IN CI/CD

The CI/CD system must not stop at unit tests.

Create a **staging integration environment** containing representative test data.

The pipeline must actually execute:

```text
test dataset
     ↓
ingestion
     ↓
local model
     ↓
concept extraction
     ↓
graph population
     ↓
library update
     ↓
retrieval
```

Then verify automatically:

### Example

Input:

```text
test_book.csv
```

Expected:

```text
Book appears in library
        +
Concepts generated
        +
Graph nodes generated
        +
Relationships generated
        +
Source URL retained
        +
Chat can retrieve the book
        +
Chat can answer a question about it
```

This is a **real end-to-end test**, not a mocked success response.

---

# 12. LIVE INFERENCE TESTING

After deployment to the AntDeploy staging environment, CI must execute real inference smoke tests.

Example:

```text
Deploy
 ↓
Health Check
 ↓
Authenticate
 ↓
Send Chat Query
 ↓
Inference
 ↓
Retrieval
 ↓
Graph Retrieval
 ↓
Response Validation
 ↓
Source Link Validation
 ↓
Graph Response Validation
```

Test queries should include:

```text
"What is X?"

"Which books cover X?"

"What should I learn before X?"

"How is X related to Y?"

"Give me a roadmap for learning X."

"Which source supports this?"

"Show me the graph around X."
```

The test must verify **semantic response structure**, not just HTTP 200.

---

# 13. Response Validation

Automated tests should check that a response:

* contains an answer;
* does not contain obvious hallucinated source data;
* includes expected retrieved context where applicable;
* includes valid links;
* returns graph data when requested/appropriate;
* returns roadmap information when appropriate;
* references actual library records;
* handles unavailable information honestly.

For deterministic tests, use known fixtures and expected entities rather than demanding exact wording.

---

# 14. XKIRO / Inference API

Production inference must support:

### Rate limiting

Implement:

```text
per-IP limit
per-user limit
per-endpoint limit
```

where appropriate.

Handle:

```text
429 Too Many Requests
```

with proper client behavior.

### Reliability

Support:

* timeout;
* retry;
* exponential backoff;
* provider failure;
* malformed response;
* connection failure;
* quota exhaustion.

Never retry infinitely.

---

# 15. AntDeploy Production Deployment

Deploy the production-facing inference/API service to **AntDeploy**.

The deployment must include:

```text
Application
Environment Variables
Secrets
Health Checks
Logging
API Rate Limiting
Authentication
Database Connectivity
Graph Connectivity
Inference Connectivity
```

The frontend must never receive private:

* API keys;
* database passwords;
* service-role keys;
* inference credentials;
* internal service credentials.

---

# 16. Supabase

Use Supabase appropriately for the existing architecture.

Verify:

* authentication;
* sessions;
* authorization;
* database access;
* Row Level Security;
* migrations;
* indexes;
* constraints;
* protected data.

Test unauthorized access explicitly.

Example:

```text
User A
  ↓
Attempts User B data
  ↓
403 / denied
  ↓
PASS
```

---

# 17. Software Engineering Methodology

Use an **Agile / iterative engineering model**.

Work in small vertical slices:

```text
Feature
 ↓
Implementation
 ↓
Unit Test
 ↓
Integration Test
 ↓
UI Test
 ↓
Regression Test
 ↓
Staging
 ↓
Production
```

Do not build everything first and test at the end.

Each major feature should have:

```text
Requirement
Acceptance Criteria
Implementation
Tests
Code Review
Deployment
Verification
```

---

# 18. Team / Employee Roles

Create explicit ownership for the project.

### 1. Project/Product Lead

Responsible for:

* requirements;
* scope;
* priorities;
* acceptance criteria;
* release decisions.

### 2. Technical Lead / Architect

Responsible for:

* architecture;
* API contracts;
* graph architecture;
* system integration;
* technical decisions.

### 3. Frontend Engineer

Responsible for:

* landing page;
* chat;
* library;
* library details;
* graph UI;
* source links;
* UX.

### 4. Backend Engineer

Responsible for:

* APIs;
* authentication;
* inference service;
* rate limiting;
* library API;
* graph API.

### 5. AI/ML Engineer

Responsible for:

* local model;
* extraction;
* retrieval;
* Graph RAG;
* inference evaluation;
* response quality.

### 6. Data / Knowledge Engineer

Responsible for:

* HF datasets;
* books;
* papers;
* CSV/ODS;
* ingestion;
* normalization;
* graph population.

### 7. Graph Engineer

Responsible for:

* graph schema;
* graph integrity;
* traversal;
* roadmap generation;
* graph visualization data.

### 8. DevOps / SRE Engineer

Responsible for:

* AntDeploy;
* Supabase;
* CI/CD;
* secrets;
* monitoring;
* deployment;
* rollback.

### 9. QA / Test Engineer

Responsible for:

* regression;
* integration;
* E2E;
* edge cases;
* load testing;
* production smoke tests.

### 10. Security Engineer

Responsible for:

* authentication;
* authorization;
* API security;
* dependency scanning;
* secrets;
* penetration/security checks.

### 11. Documentation / Release Engineer

Responsible for:

* API documentation;
* deployment documentation;
* changelog;
* runbooks;
* release notes.

If there are fewer actual employees, combine roles but **retain the responsibilities**.

Never invent employee names. Map real developers to these roles through Git ownership/configuration.

---

# 19. Git Workflow

Use:

```text
main
develop
feature/*
fix/*
hotfix/*
```

Recommended flow:

```text
feature
   ↓
Pull Request
   ↓
CI
   ↓
Code Review
   ↓
Merge
   ↓
Staging
   ↓
E2E
   ↓
Production
```

Use meaningful commits:

```text
feat(chat): add graph-aware responses
fix(api): handle inference rate limits
feat(ingestion): add ODS importer
test(graph): validate graph integrity
ci(e2e): add live inference tests
fix(library): preserve exact source URLs
```

---

# 20. CI/CD Pipeline

The pipeline should continuously run:

```text
                 COMMIT
                    ↓
             Static Analysis
                    ↓
              Formatting
                    ↓
               Linting
                    ↓
              Type Checks
                    ↓
              Unit Tests
                    ↓
          Integration Tests
                    ↓
          Database/Graph Tests
                    ↓
           Ingestion E2E Test
                    ↓
          Build Frontend/API
                    ↓
         Security/Vulnerability Scan
                    ↓
             Deploy Staging
                    ↓
            Health Checks
                    ↓
        LIVE INFERENCE TEST
                    ↓
       LIVE GRAPH RETRIEVAL TEST
                    ↓
       LIVE INGESTION TEST
                    ↓
      LIBRARY UPDATE VERIFICATION
                    ↓
       SOURCE LINK VERIFICATION
                    ↓
       RESPONSE QUALITY CHECK
                    ↓
             APPROVAL GATE
                    ↓
          DEPLOY PRODUCTION
                    ↓
          PRODUCTION SMOKE TEST
                    ↓
          MONITOR / VERIFY
```

---

# 21. Continuous Regression Loop

This is critical.

After every significant change:

```text
Code Change
     ↓
CI
     ↓
Regression
     ↓
Ingestion
     ↓
Graph
     ↓
Library
     ↓
Inference
     ↓
Chat
     ↓
Links
     ↓
Roadmap
     ↓
Graph UI
```

A feature is **not complete** if it works in isolation but breaks another subsystem.

---

# 22. Edge Cases

Explicitly test:

### Chat

* empty message;
* huge message;
* repeated message;
* malformed request;
* timeout;
* rate limit;
* inference unavailable;
* graph unavailable;
* no relevant documents;
* ambiguous query;
* unsupported question.

### Library

* missing title;
* missing author;
* missing URL;
* duplicate ISBN;
* duplicate document;
* malformed metadata;
* deleted source;
* inaccessible source.

### Graph

* zero nodes;
* one node;
* disconnected nodes;
* duplicate edges;
* cycles;
* orphan nodes;
* missing source;
* invalid relationship;
* extremely large neighborhood.

### Ingestion

* empty CSV;
* malformed CSV;
* malformed ODS;
* wrong encoding;
* missing columns;
* duplicate rows;
* changed row;
* deleted row;
* partial failure;
* interrupted ingestion.

### API

* 401;
* 403;
* 404;
* 409;
* 422;
* 429;
* 500;
* 502;
* 503;
* timeout.

---

# 23. Performance Testing

Test:

* concurrent chat requests;
* concurrent library requests;
* graph queries;
* ingestion throughput;
* inference latency;
* large library;
* large graph;
* repeated requests.

Measure:

```text
P50 latency
P95 latency
P99 latency
error rate
throughput
memory
CPU
```

Do not optimize prematurely, but identify production bottlenecks.

---

# 24. Security Testing

CI must detect:

* committed secrets;
* exposed API keys;
* insecure endpoints;
* unauthorized graph mutation;
* unauthorized library modification;
* privilege escalation;
* injection vulnerabilities;
* unsafe file uploads;
* malicious CSV/ODS;
* dependency vulnerabilities.

---

# 25. Observability

Implement:

```text
request ID
structured logs
error tracking
latency metrics
inference metrics
graph query metrics
ingestion metrics
```

At minimum monitor:

```text
API errors
429 rate
inference failures
ingestion failures
graph failures
authentication failures
latency
```

---

# 26. Health / Readiness

Provide:

```text
/health
/ready
```

Health:

```text
application alive
```

Readiness:

```text
application
+
required database
+
required graph service
+
required inference dependency
```

where appropriate.

---

# 27. Deployment Safety

Production deployment must support:

```text
backup
↓
migration
↓
deployment
↓
health check
↓
smoke test
↓
monitor
```

If critical smoke tests fail:

```text
deployment
    ↓
FAIL
    ↓
rollback
```

Never silently leave a broken production release running.

---

# 28. Definition of Done

Archipelago should only be declared production-ready when:

### Product

* [ ] Landing page works.
* [ ] Chat works.
* [ ] Library works.
* [ ] Library details work.
* [ ] Graph UI works.
* [ ] In-chat graph works.
* [ ] Roadmaps work.
* [ ] Relations work.
* [ ] Source links work.
* [ ] Exact HF links work.
* [ ] Exact authorized Pearson links work.
* [ ] IEMCRP link works.
* [ ] UEMK OPAC link works.

### AI

* [ ] Local ingestion model retained.
* [ ] Graph extraction works.
* [ ] Retrieval works.
* [ ] Inference works.
* [ ] Responses are validated.
* [ ] Hallucinated sources are prevented as far as practical.
* [ ] Graph-aware responses work.

### Data

* [ ] HF datasets indexed.
* [ ] Books indexed.
* [ ] Papers indexed.
* [ ] CSV ingestion works.
* [ ] ODS ingestion works.
* [ ] Automated graph population works.
* [ ] Library statistics update automatically.
* [ ] Graph integrity passes.

### Infrastructure

* [ ] AntDeploy deployment works.
* [ ] Supabase works.
* [ ] Authentication works.
* [ ] Authorization works.
* [ ] API rate limiting works.
* [ ] Secrets protected.
* [ ] Health checks work.
* [ ] Logging works.

### Testing

* [ ] Unit tests.
* [ ] Integration tests.
* [ ] Regression tests.
* [ ] E2E tests.
* [ ] Live ingestion test.
* [ ] Live inference test.
* [ ] Live graph test.
* [ ] Live library-update test.
* [ ] Source-link test.
* [ ] Edge-case tests.
* [ ] Security tests.
* [ ] Performance tests.
* [ ] Production smoke tests.

### CI/CD

* [ ] Every PR runs CI.
* [ ] Staging deploy is automated.
* [ ] Live E2E tests execute.
* [ ] Ingestion is actually executed in staging.
* [ ] Graph population is verified.
* [ ] Inference is actually executed.
* [ ] Chat response is validated.
* [ ] Links are validated.
* [ ] Production deployment has an approval gate.
* [ ] Failed deployment can roll back.

---

# 29. Final Engineering Principle

**Do not optimize for "the code runs."**

Optimize for:

```text
Correctness
    +
Data integrity
    +
User experience
    +
Security
    +
Reliability
    +
Testability
    +
Observability
    +
Reproducibility
    +
Maintainability
    +
Deployability
```

The final system should behave as a **real production knowledge platform**, where:

```text
DATA
 ↓
INGESTION
 ↓
LOCAL AI
 ↓
GRAPH
 ↓
LIBRARY
 ↓
RETRIEVAL
 ↓
INFERENCE
 ↓
CHAT
 ↓
GRAPH UI
 ↓
SOURCE / ROADMAP
```

are one continuously tested system—not independent features that merely happen to exist in the same repository.

**Do not report "production ready" until the complete pipeline has successfully demonstrated this flow in staging and passed the required regression/E2E tests.**

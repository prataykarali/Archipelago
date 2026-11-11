# S3 graph reconciliation — 2026-11-11

## Storage, export, API, and browser

The local Kùzu database `okf_graph.db` is the persisted baseline. It was opened
read-only for this audit. No ingestion, graph rebuild, or publishing occurred.

| Layer | Before S3 | After S3 |
| --- | ---: | ---: |
| Kùzu persisted graph | 6,186 nodes; 20,160 edges | Unchanged |
| `okf_graph.json` and hosted export copies | 610 concepts; 1,988 concept edges | Unchanged |
| Main `/api/graph` | 610 concepts; 1,988 edges, but source-bearing top-level nodes were ignored | 610 concepts; 1,988 edges, source-bearing nodes retained |
| Hosted `/api/graph/hubs` | 12 hubs maximum | Unchanged |
| Hosted `/api/research/graph/full` | All 610 exported concepts | Unchanged |
| New main `/api/graph/global` | Unavailable | All 6,186 nodes and 20,160 edges reachable by independent pages |
| New hosted `/api/graph/page` | Unavailable | All 610 exported concepts reachable by pages |
| Main browser default | All 610 concepts at once | Focused experience retained; separate global view shows 100 per desktop page or 40 per mobile page |
| Hosted browser default | 12 hubs | Focused experience retained; global view shows 60 concepts per page |

The persisted node types are Concept 610, Document 79, Chunk 808, Resource
2,498, Subject 1,010, and JournalIssue 1,181. Persisted relationships are
REQUIRES 267, UNLOCKS 387, RELATED 1,334, HAS_CHUNK 786, MENTIONS 1,380,
PROVIDES_TEXT 49, CATEGORIZES 14,776, and HAS_ISSUE 1,181. All returned
edges have valid endpoints. The persisted graph has 32 nodes without any
edge; the concept-only export has 58 isolated concepts because it omits
document and resource links. These are separate counts.

The 610 exported concept IDs exactly match persisted Concept IDs. The 1,988
exported concept relationships match their persisted `(source, target, type)`
triples. There are no missing or extra concept IDs, duplicate concept IDs, or
invalid exported edge endpoints. The new read-only API preserves all eight
persisted relationship types. Its snapshot version at audit was
`d0ee0363629a`, derived from stable node and edge IDs; the database mtime is
reported as `last_sync` for API compatibility and labeled as storage modified
in the UI because an actual upstream sync event is not recorded. Three local
JSON copies (root, hosted fixture, hosted
cache) were byte-identical, SHA-256 prefix `9818ac0e8fd30e2e`. None carries
the fixture marker; local hosted `Engine` selects the root full concept export.
The actual remote deployment's selected artifact was not inspected.

## What changed

`archipelago/graph/explorer.py` exposes a read-only snapshot of all persisted
entity and relation types, deterministic paging, search, type filtering, and
bounded two-hop expansion. `graph_server.py` exposes it through staff-gated
APIs. The new `ui/graph/global.html` supports search, page controls, relation
toggles, node and edge details, source page navigation, zoom, fit, and reset.
The main graph index links to this view. The hosted graph page has an
independent global mode over its existing concept export, with counts, version,
sync time, source trail, and typed edge details. Focused graph and diagnostic
learning flows remain separate. The hosted browser no longer draws a synthetic
`SOURCED_FROM` edge for a citation record.

The main API and static fallback now prefer the top-level exported nodes. This
restores 1,358 stored concept source entries that were hidden by the
source-free `visualization.nodes` projection. No source record was generated.

## Source record reconciliation

Every document ID cited by the 610 exported concepts exists among the 79
persisted Document IDs: **zero missing referenced Document records**. Nineteen
persisted Documents are not cited by exported concept source entries. This is
an uncited set, not evidence of deletion:

`doc_retrieval_augmented_generation_for_knowledge_intensive_nlp`; textbook
paths for Aho compilers, Tanenbaum networks, Ramakrishnan DBMS, Silberschatz
database systems and operating systems, Ross probability, CLRS algorithms,
Hopcroft automata, Strang linear algebra, and OSTEP; upload IDs
`116fd637`, `12148e40`, `53c0f47f`, `bdedc151`, `cd81a72b`, `d837c9b2`,
`db9b9808`, and `e7b08341` (each with `upload_` prefix). Some may be resource
records without concept citation coverage. Physical PDF access for every
record was not independently established.

## Verification

- 30 focused unit tests passed: S3 main and hosted API tests, legacy graph API,
  bounded subgraph, hosted diagnostic behavior, and personalized MCQ graph.
  This includes pagination reaching all 6,186 persisted node IDs; edge endpoint
  validity; immutable filtering; export ID/type reconciliation; all eight
  relation types surviving a JSON export/import round trip; and independent
  personalized behavior.
- Ruff lint and formatting passed for changed Python graph files and tests.
- Browser probes loaded desktop and mobile pages, advanced to the next page,
  and filtered Resource records. The mobile page renders 40 of 6,186 nodes.
  Screenshots: `artifacts/validation/s3-graph/global-desktop.png` and
  `artifacts/validation/s3-graph/global-mobile.png`. A hosted page probe against
  the local hosted API rendered 60 of 610 concepts; its screenshot is
  `artifacts/validation/s3-graph/hosted-global-desktop.png`. For that probe,
  the hosted graph HTML was served locally because the normal `/graph` entry
  redirects to the separate research origin.
- The broader hosted page file has two unrelated failing assertions about a
  research JavaScript asset version and a research login redirect. They were
  excluded from the 30-test graph regression run; neither assertion touches
  graph routes or graph UI.

## Limits

The hosted runtime ships a concept-only JSON export; its global view reaches
all 610 exported concepts but not the 5,576 other persisted entities. The main
Kùzu-backed global view reaches all persisted types. A page shows only edges
whose endpoints are on that page; the edge API and node expansion expose
cross-page relationships. The main UI uses Cytoscape from a CDN and falls back
to the paginated node list if it cannot load. The audit proves local artifact
coverage, not the current artifact deployed on a remote host.

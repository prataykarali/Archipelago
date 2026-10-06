# Archipelago Library Computer — Docker Appliance

Self-contained Docker stack for institutional library/IEDC computers. Runs the
whole institutional half of Archipelago locally: ingestion, the KùzuDB graph,
and the library catalogue. The hosted inference API receives counts and
retrieval context only — never the corpus.

## Architecture

```
Library Computer (air-gap capable)
├── ollama                  — local extraction SLM (no internet needed)
├── archipelago-ingestion   — local HTTP ingestion API + single worker (internal port 5151)
├── archipelago-graph       — Graph server + library UI (port 5150)
└── archipelago-sync        — reports graph size to the hosted API
```

Each service declares a **healthcheck**, and dependents wait on the condition
rather than merely on start order:

| Service | Healthcheck | Waits for |
|---------|-------------|-----------|
| `ollama` | `ollama list` | — |
| `archipelago-ingestion` | `GET /health` on the internal API | `ollama` healthy |
| `archipelago-graph` | `GET /api/health` | ingestion healthy |
| `archipelago-sync` | process liveness | graph started |

## Quick Start

```bash
# 1. Configure
cd deploy/library-computer
cp .env.example .env       # Supabase credentials, inference API URL, secrets

# 2. Point at the extraction model on this machine.
#    The compose file mounts ${ARCHIPELAGO_MODEL_DIR} read-only at /app/models.
export ARCHIPELAGO_MODEL_DIR=/opt/archipelago/models
export ARCHIPELAGO_STATE_DIR=/opt/archipelago/data

# 3. Start
docker compose up -d --build

# 4. Verify
docker compose ps                       # all four should be healthy
curl -s http://127.0.0.1:5150/api/health | python -m json.tool
curl -s http://127.0.0.1:5150/api/readiness | python -m json.tool
```

`docker compose up -d` on a cold machine will not be healthy instantly: the
graph server waits on ingestion's healthcheck, which in turn waits for Ollama.
Allow ~60 s on first boot.

The graph port binds to loopback on the library computer. Put an authenticated
reverse proxy in front of it before allowing access from other machines. The
worker writes `/app/graph-state/okf_graph.json` through a legacy-path link;
the graph and sync services read the same named volume. A regular file at the
legacy path prevents startup rather than being silently overwritten.

### Fetching the extraction model

Ingestion needs a local extraction model. Either point `ARCHIPELAGO_MODEL_DIR`
at one you already have, or download a pinned revision:

```bash
# In the repo, on the host that has HF_TOKEN
python -m archipelago model download --repo Prataykarali/lib-qwen --revision v5 \
  --dest ./models/lib_qwen_v44_hf
```

`okf.config.resolve_local_model_path()` searches, in order:
`$OKF_LOCAL_MODEL` → `models/<name>` → a sibling of the repo → each root in
`$ARCHIPELAGO_MODEL_ROOTS`. Recognised names are `lib_qwen_v44_hf`, `lib-qwen`,
`lib-qwen-v44`, `aura-qwen`.

**No absolute developer paths are baked into the config.** A hardcoded
`/home/<someone>/…` fallback previously made the container silently fall back to
a default model name whenever the real model was mounted elsewhere.

## Populating the Library Catalogue

The catalogue is the librarian-facing surface. It is populated from the
institution's own exports, idempotently:

```bash
# Merge Koha/OPAC periodicals + the Pearson eLibrary bookshelf into the graph
docker compose exec archipelago-ingestion \
  python -m archipelago library populate

# Verify
docker compose exec archipelago-ingestion \
  python -c "
import kuzu; c = kuzu.Connection(kuzu.Database('okf_graph.db', read_only=True))
print('resources:', c.execute('MATCH (r:Resource) RETURN count(r)').get_next()[0])
"
```

Expected: **109** Koha periodicals + **40** Pearson titles = **149** resources.
Re-running adds zero duplicates (verified by test).

Inputs, both read from paths you mount:

| Source | Default path | Provides |
|--------|--------------|----------|
| Koha ODS exports | `data/koha/*.ods` | Periodicals, call numbers, barcodes |
| Pearson eLibrary bookshelf | `data/catalogs/pearson_bookshelf.json` | Institutional **books**, ISBNs, reader URLs |

The Koha export contains periodicals only, so without the bookshelf step the
catalogue can answer nothing about a textbook.

## Ingesting Documents

```bash
# Upload (librarian, through the graph server to the internal ingestion API)
curl -X POST http://localhost:5150/api/ingest \
  -H "Authorization: Bearer $ARCHIPELAGO_LIBRARIAN_TOKEN" \
  -F file=@syllabus.pdf

# Or from inside the container
docker compose exec archipelago-ingestion \
  python -m archipelago ingest --source /app/data/uploads/syllabus.pdf
```

The Compose stack now starts one local API process that owns the ingestion
worker and Kùzu writer. The graph server forwards upload, status, and document
operations only to that internal service; no raw upload is sent to the hosted
inference origin. This wiring has unit and static YAML coverage, but the
container has not been booted or exercised with a real upload in this release
worktree. Keep the upload UI closed to users until the P5 upload-to-citation
test passes. The CLI route remains available for operator-controlled local
ingestion.

## Source Lifecycle

When Pearson or Hugging Face removes a title, mark it and the library forgets
it — the chat stops citing it and answers that it is no longer in records:

```bash
docker compose exec archipelago-ingestion \
  python -m archipelago library sources --withdrawn-only
```

State lives in `${ARCHIPELAGO_STATE_DIR}` and is mounted as a **bind**, not a
named volume, so `docker compose down` cannot silently discard which sources
were withdrawn. Back it up together with the corpus.

Newly-entitled books are proposed rather than auto-ingested, because ingesting
commercial text is a licensing decision:

```bash
docker compose exec archipelago-ingestion python -m archipelago library propose
# review, then record the decision (see docs/guides/SOURCE_LIFECYCLE.md)
```

## Web Fetch Policy

The stack refuses all outbound web fetches by default. See
[`docs/guides/WEB_FETCH_POLICY.md`](../../docs/guides/WEB_FETCH_POLICY.md) before
setting `ARCHIPELAGO_FETCH_ALLOWLIST`.

## Backups

```bash
# Graph database (a directory — copy it wholesale, not a single file)
docker run --rm -v archipelago-library_graph-data:/data -v "$PWD":/backup \
  alpine tar czf /backup/okf_graph_db.tgz -C /data .

# Source lifecycle + proposals
tar czf state.tgz -C "$ARCHIPELAGO_STATE_DIR" data

# Source PDFs
tar czf pdfs.tgz -C "$ARCHIPELAGO_MODEL_DIR/../.." pdfs
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `archipelago-ingestion` never healthy | `jobs` volume not writable | check the bind mount's permissions |
| readiness says `ready: false` | Ollama not reachable | `docker compose exec ollama ollama list` |
| catalogue empty after `library populate` | export files not mounted | verify `data/koha/` and `data/catalogs/` are visible in the container |
| model not found at `/app/models/...` | `ARCHIPELAGO_MODEL_DIR` unset | export it before `docker compose up` |

## Operations

```bash
docker compose logs -f archipelago-ingestion
docker compose restart archipelago-ingestion
docker compose down          # volumes survive; the data bind persists
```

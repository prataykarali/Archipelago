# Archipelago Library Computer — Docker Appliance

Self-contained Docker stack for institutional library/IEDC computers.

## Architecture

```
Library Computer
├── archipelago-ingestion   — Background ingestion worker
├── archipelago-graph       — Graph server (port 5150)
└── archipelago-sync        — Sync/health monitor
```

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your Supabase credentials and inference API URL

# 2. Download the ingestion model from Hugging Face
python -m archipelago model download \
  --repo Prataykarali/lib-qwen \
  --revision v5

# 3. Start the stack
docker compose up -d

# 4. Verify
docker compose ps
curl http://localhost:5150/api/health
```

## Ingesting Data

```bash
# Place files in the data/uploads/ directory, then:
docker compose exec archipelago-ingestion \
  python -m archipelago ingest --source /app/data/uploads/your_file.csv

# Or use the CLI directly:
python -m archipelago ingest --source dataset.csv
python -m archipelago ingest --source library.ods
```

## Graph Operations

```bash
# Validate graph integrity
python -m archipelago graph validate

# View statistics
python -m archipelago graph stats

# Compare against baseline
python -m archipelago graph diff --baseline baseline_graph.json
```

## Updating the Model

```bash
python -m archipelago model download \
  --repo Prataykarali/lib-qwen \
  --revision v6
docker compose restart archipelago-ingestion
```

## Offline Deployment

Export images for air-gapped installation:

```bash
docker compose pull
docker save archipelago-ingestion archipelago-graph archipelago-sync \
  | gzip > archipelago-library-stack.tar.gz
```

On the target machine:

```bash
docker load < archipelago-library-stack.tar.gz
docker compose up -d
```

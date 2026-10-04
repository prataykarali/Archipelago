# Archipelago

Archipelago is a library and learning assistant built around a knowledge graph. It combines document ingestion, graph backed retrieval, grounded answers with source links, a chat interface, and tools for exploring the graph and library catalogue.

The repository contains both a local graph and inference stack and a lightweight hosted inference service. The hosted service is in `host_inference/`; the main application code is in `archipelago/` and `okf/`.

## What is in the project

- **Chat and question answering** — routes questions, retrieves relevant graph evidence, and formats grounded replies and citations.
- **Knowledge graph** — stores concepts, prerequisite relationships, document provenance, and library resources in KùzuDB.
- **Library catalogue** — searches book and periodical metadata and provides source links.
- **Document ingestion** — extracts and cleans concepts from PDFs and other supported documents before adding them to the graph.
- **Graph and library interfaces** — static browser interfaces under `ui/` and `host_inference/ui/`.
- **Hosted inference service** — Flask application and deployment-specific UI under `host_inference/`.

Feature behavior depends on the configured model provider, graph data, and optional external services. See [known gaps](#known-gaps) before treating the system as production ready.

## Repository layout

```text
archipelago/           Application, APIs, inference, graph access, ingestion
okf/                   Knowledge extraction, cleanup, graph persistence, evaluation
host_inference/        Standalone hosted inference service and its UI
ui/chat/                Main chat UI
ui/graph/               Knowledge graph UI
frontend/               Frontend source and shared assets
tests/                  Unit, integration, frontend, and end-to-end tests
docs/                   Architecture, operations, audits, and feature guides
deploy/                 Local library-computer deployment files
scripts/                Evaluation, maintenance, and operations commands
training/               Dataset preparation and model training utilities
pilot_corpus/           Small evaluation corpus and expected results
```

The canonical Python application package is `archipelago/`. Root scripts such as `chat_server.py`, `graph_server.py`, and `inference_server.py` are launch entry points. `host_inference/` is a separate service boundary with its own requirements and Dockerfile.

## Run locally

Python 3.10 or newer is required. Create an environment and install the main dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set only the integrations you plan to use. Keep credentials in local environment variables or the hosting platform's secret store; never commit populated secrets.

Start individual services from the repository root:

```bash
python -m archipelago.apps.inference_app
python chat_server.py
python graph_server.py
```

The hosted inference service has separate dependencies and is started from the repository root with:

```bash
pip install -r host_inference/requirements.txt
PYTHONPATH="$PWD" gunicorn --chdir host_inference --bind 127.0.0.1:5151 hostapp.wsgi
```

For local ingestion and the library-computer stack, follow [`deploy/library-computer/README.md`](deploy/library-computer/README.md). Additional operational instructions are in [`PILOT_LAUNCH.md`](PILOT_LAUNCH.md).

## Tests and checks

Run the offline test suites from the repository root:

```bash
pytest tests/unit/ -k 'not test_heavy_gpu'
pytest tests/integration/
```

Live end-to-end checks are opt-in and may need external services and credentials. Quality tooling is defined in `requirements-dev.txt` and the GitHub Actions workflow at `.github/workflows/ci.yml`.

## Configuration and data

- `.env.example` documents supported local configuration. Do not put live credentials in `.antideploy.json` or commit them.
- `host_inference/requirements.txt` and `host_inference/Dockerfile` describe the standalone inference service.
- `deploy/library-computer/` contains the local library deployment configuration.
- Runtime graph databases, uploaded documents, model weights, and generated outputs may be ignored by Git. A clean checkout may therefore need a corpus or graph export before retrieval can return useful evidence.

## Known gaps

The checked-in readiness notes report that the SLM extraction evaluation is below its acceptance threshold; unattended model-based ingestion should remain disabled until that evaluation passes. Integration behavior also depends on the selected synthesis provider and available graph evidence. Review [`docs/reports/PRODUCTION_READINESS_AND_PLATFORM_PLAN.md`](docs/reports/PRODUCTION_READINESS_AND_PLATFORM_PLAN.md) and [`docs/guides/SLM_EXTRACTION_EVAL.md`](docs/guides/SLM_EXTRACTION_EVAL.md) for measured results and open work.

Do not consider a deployment verified until the test suites pass, the configured `/api/readiness` check is healthy, and representative chat, citation, catalogue, and graph workflows have been exercised against the deployed service.

## More documentation

- [Architecture guide](docs/guides/ARCHITECTURE.md)
- [Pilot launch and smoke checks](PILOT_LAUNCH.md)
- [Production readiness report](docs/reports/PRODUCTION_READINESS_AND_PLATFORM_PLAN.md)
- [Security guidance](docs/SECURITY.md)
- [CI workflow](.github/workflows/ci.yml)

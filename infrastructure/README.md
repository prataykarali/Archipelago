# Infrastructure Architecture

Production deployment and external service connectors:

- `huggingface/`: Hugging Face Spaces Dockerfile and hub datasets sync
- `supabase/`: PostgreSQL migrations, RLS policies, and JWT multi-role schemas
- `inference/`: Gunicorn WSGI configs and multi-worker execution specs
- `deployment/`: Production Dockerfile, docker-compose.yml, and operational management scripts
- `apify/`: Web-data actor discovery integration
- `monitoring/`: Health probes, readiness checks, and latency telemetry

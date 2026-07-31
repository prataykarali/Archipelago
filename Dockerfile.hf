# Hugging Face Spaces (Docker) — Archipelago pilot chat + inference
# Secrets (Space Settings → Repository secrets):
#   OLLAMA_HOST (remote Ollama GPU endpoint, required)
#   ARCHIPELAGO_TOKEN   (optional but recommended)
#   ARCHIPELAGO_ERESOURCE_JSON content via mounted secret file if needed
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARCHIPELAGO_BIND=0.0.0.0 \
    ARCHIPELAGO_DB_READ_ONLY=1 \
    PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces expect the app on $PORT (default 7860)
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/readiness" || exit 1

CMD ["bash", "scripts/ops/hf_space_start.sh"]

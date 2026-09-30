FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARCHIPELAGO_ENV=production \
    ARCHIPELAGO_AUTH_REQUIRED=1 \
    ARCHIPELAGO_BIND=0.0.0.0 \
    PORT=5151 \
    ARCHIPELAGO_LLM_PROVIDER=xkiro

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5151
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/readiness" || exit 1

# Compose/platforms override this command for graph and chat services.
CMD ["gunicorn", "--bind", "0.0.0.0:5151", "--workers", "1", "--threads", "8", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "archipelago.apps.inference_app:create_app()"]

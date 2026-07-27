# ── Archipelago — single-container production image ──────────────────────────
# Inference server  → port 5051  (ARCHIPELAGO_BIND=0.0.0.0)
# Graph server      → port 5050  (ARCHIPELAGO_BIND=0.0.0.0)
#
# Build:  docker build -t archipelago .
# Run:    docker run -p 5050:5050 -p 5051:5051 \
#           -e GEMINI_API_KEY=<key> \
#           archipelago

FROM python:3.11-slim

# ── System deps ───────────────────────────────────────────────────────────────
# libgomp1: required by PyMuPDF (MuPDF rendering)
# build-essential: needed by some pip packages with C extensions (e.g. kuzu)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Source code ───────────────────────────────────────────────────────────────
COPY . .

# ── Runtime environment ───────────────────────────────────────────────────────
# Bind both Flask apps to all interfaces so Docker can route traffic
ENV ARCHIPELAGO_BIND=0.0.0.0

# Disable Aura (fine-tuned model) by default — enable if you have weights
ENV ARCHIPELAGO_LOAD_AURA=0

# KuzuDB path — defaults to /app/okf_graph.db (inside container)
# Override with -e ARCHIPELAGO_DB_PATH=/data/okf_graph.db for persistent volume
ENV ARCHIPELAGO_DB_PATH=/app/okf_graph.db

# Flask: don't use dev reloader in production
ENV FLASK_ENV=production

# ── Ports ─────────────────────────────────────────────────────────────────────
EXPOSE 5050
EXPOSE 5051

# ── Startup ───────────────────────────────────────────────────────────────────
# start.sh launches both servers; inference server is primary (PID 1 via exec)
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]

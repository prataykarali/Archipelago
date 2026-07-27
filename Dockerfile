# ── Archipelago — single-container production image ──────────────────────────
FROM python:3.11-slim

# ── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# ── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ──────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source ──────────────────────────────────────────────────────────────
COPY . .

# ── Runtime environment ──────────────────────────────────────────────────────
ENV ARCHIPELAGO_BIND=0.0.0.0
ENV ARCHIPELAGO_LOAD_AURA=0
ENV ARCHIPELAGO_DB_PATH=/app/okf_graph.db
ENV FLASK_ENV=production

# Northflank injects PORT automatically
ENV PORT=5050

# ── Expose public port ───────────────────────────────────────────────────────
EXPOSE 5050

# ── Startup ──────────────────────────────────────────────────────────────────
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
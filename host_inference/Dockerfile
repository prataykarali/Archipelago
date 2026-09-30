FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARCHIPELAGO_ENV=production \
    ARCHIPELAGO_AUTH_REQUIRED=1 \
    PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} --threads 8 --timeout 120 server:app"]

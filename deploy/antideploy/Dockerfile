FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARCHIPELAGO_ENV=production \
    ARCHIPELAGO_AUTH_REQUIRED=1 \
    PORT=8080

WORKDIR /app/host_inference
COPY host_inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY host_inference/ ./
EXPOSE 8080
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 300 'live_wsgi:create_release_app()'"]
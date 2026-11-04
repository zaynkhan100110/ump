FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UMP_DATA_DIR=/data \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY backend /app/backend
COPY frontend /app/frontend
RUN mkdir -p /data && useradd --system --uid 10001 ump && chown -R ump:ump /app /data
USER ump
WORKDIR /app/backend
EXPOSE 8000
CMD ["gunicorn", "--workers", "1", "--threads", "16", "--timeout", "180", "--bind", "0.0.0.0:8000", "app:app"]

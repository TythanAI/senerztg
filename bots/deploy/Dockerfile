# Single image, reused by every bot. The only thing that differs per bot is the
# --config argument and the secrets passed via the environment.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core ./core
COPY config ./config

# Run as a non-root user; keep the writable DB dir owned by it.
RUN useradd --create-home --uid 10001 botuser \
    && mkdir -p /app/data \
    && chown -R botuser:botuser /app
USER botuser

ENTRYPOINT ["python", "-m", "core"]
CMD ["--config", "config/tg_accounts_01.yaml"]

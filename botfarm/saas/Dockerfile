# One image serves any service in the rack; SERVICE picks which.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY saascore/ ./saascore/
COPY services/ ./services/
COPY serve.py ./

RUN useradd --create-home --uid 10001 saas \
    && mkdir -p /app/data \
    && chown -R saas:saas /app
USER saas

ENV SERVICE=qr PORT=8000 HOST=0.0.0.0
EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8000\")}/healthz', timeout=4).status==200 else 1)"

CMD ["sh", "-c", "python serve.py \"$SERVICE\" --host \"$HOST\" --port \"$PORT\""]

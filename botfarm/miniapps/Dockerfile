FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY miniapps/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY miniapps/ ./miniapps/

RUN useradd --create-home --uid 10001 mini \
    && mkdir -p /app/miniapps/data \
    && chown -R mini:mini /app
USER mini

ENV PORT=8100
EXPOSE 8100
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\")}/healthz',timeout=4).status==200 else 1)"

CMD ["python", "miniapps/serve.py"]

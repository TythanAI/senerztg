# YouTube Аккаунты (ru-315-youtube-channel)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY core/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY bots/ru/315-youtube-channel/ ./bot/

ENV PYTHONPATH=/app/core
WORKDIR /app/bot

RUN useradd --create-home --uid 10001 botuser && chown -R botuser:botuser /app
USER botuser

EXPOSE 9314
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9314/healthz', timeout=4).status==200 else 1)"

CMD ["python", "bot.py"]

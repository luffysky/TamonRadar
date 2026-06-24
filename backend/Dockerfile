# TamonRadar 後端 — 輕量版(雲端用,不含 Chromium)
# 雲端用搜尋 API(SerpAPI/Brave/SearXNG/DuckDuckGo),不需要瀏覽器,
# 映像小很多 → 部署更快、停機更短。
# 若要在容器內跑 Selenium,改用 Dockerfile.selenium(含 Chromium)。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]

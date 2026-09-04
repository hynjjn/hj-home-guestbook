# ---------- 프론트 빌드 ----------
FROM node:24-slim AS web

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# vite.config.ts의 outDir이 ../backend/static이라 여기서만 dist로 돌린다
RUN npx vite build --outDir dist --emptyOutDir

# ---------- 파이썬 의존성 ----------
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS deps

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# ---------- 런타임 ----------
FROM python:3.14-slim-bookworm

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/guestbook.db \
    MEDIA_DIR=/data/media \
    STATIC_DIR=/app/static

COPY --from=deps /app/.venv /app/.venv
COPY backend/app ./app
COPY --from=web /web/dist ./static

RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown -R app /data
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

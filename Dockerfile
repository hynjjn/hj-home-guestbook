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
    PYTHONUNBUFFERED=1

COPY --from=deps /app/.venv /app/.venv
COPY backend/app ./app

RUN useradd --create-home --uid 10001 app
USER app

# Cloud Run이 PORT를 넣어 준다. exec 형식으로는 치환이 안 되므로 sh를 한 겹 둔다.
# EXPOSE는 Cloud Run이 보지 않지만 로컬에서 docker run 할 때를 위해 남긴다.
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

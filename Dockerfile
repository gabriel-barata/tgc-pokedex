# syntax=docker/dockerfile:1

FROM node:26-slim AS frontend
WORKDIR /app/frontend
RUN npm install --global corepack@latest && corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.13-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.13-slim
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=backend /app /app
COPY --from=frontend /app/frontend/dist /app/spa
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TCG_POKEDEX_ENVIRONMENT=prod \
    TCG_POKEDEX_SPA_DIR=/app/spa
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"]
CMD ["sh", "-c", "python -m tcg_pokedex.migrations && exec uvicorn tcg_pokedex.app:create_app --factory --host 0.0.0.0 --port 8000"]

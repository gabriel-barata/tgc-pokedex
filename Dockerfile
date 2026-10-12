# syntax=docker/dockerfile:1

ARG TARGETARCH

FROM scratch AS supercronic-amd64
ADD --checksum=sha256:a53ae236602c7338aba3fbaff40bda6300eae3b9fedb8261eb06cfe3724430c1 --chmod=755 \
    https://github.com/aptible/supercronic/releases/download/v0.2.49/supercronic-linux-amd64 /supercronic

FROM scratch AS supercronic-arm64
ADD --checksum=sha256:02aa0cb229ba09050cba6638059dadb9eedc2276632ea43d6a57a2f8c1629dd5 --chmod=755 \
    https://github.com/aptible/supercronic/releases/download/v0.2.49/supercronic-linux-arm64 /supercronic

FROM supercronic-${TARGETARCH} AS supercronic

FROM arigaio/atlas:latest-community@sha256:ff36c7ec43b3d4ab32ea980058b4682af9d3e95abdb81b63a25553fb80218156 AS atlas

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
    && useradd --system --uid 10001 --gid app --no-create-home app \
    && mkdir -p /data/images \
    && chown app:app /data/images
WORKDIR /app
COPY --from=backend /app /app
COPY --from=frontend /app/frontend/dist /app/spa
COPY --from=supercronic /supercronic /usr/local/bin/supercronic
COPY --from=atlas /atlas /usr/local/bin/atlas
COPY deploy/crontab /app/crontab
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TCG_POKEDEX_ENVIRONMENT=prod \
    TCG_POKEDEX_SPA_DIR=/app/spa \
    TCG_POKEDEX_IMAGE_DIR=/data/images
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"]
CMD ["sh", "-c", "tcg migrate && exec uvicorn tcg_pokedex.app:create_app --factory --host 0.0.0.0 --port 8000"]

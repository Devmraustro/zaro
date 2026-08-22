# syntax=docker/dockerfile:1
# =============================================================================
# ZARO API (FastAPI) - production image
#
# Hardening (Phase 1.4):
# - runs as an unprivileged user, no shell login, no home dir writes needed
# - HEALTHCHECK for orchestrator restarts
# - curl retained only for the healthcheck probe
# =============================================================================

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

FROM base AS dependencies

WORKDIR /app

COPY apps/zaro-api/pyproject.toml apps/zaro-api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=dependencies /app/.venv /app/.venv
COPY apps/zaro-api ./

# Unprivileged runtime identity; storage dir is writable only by this user.
RUN groupadd --system --gid 1001 zaro \
    && useradd --system --uid 1001 --gid zaro --create-home zaro \
    && mkdir -p /app/storage \
    && chown -R zaro:zaro /app/storage
USER zaro

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8001/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

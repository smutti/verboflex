# syntax=docker/dockerfile:1.8

FROM ghcr.io/astral-sh/uv:0.11.12 AS uv

FROM python:3.14-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14-slim AS runtime

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system verboflex \
    && useradd --system --gid verboflex --home-dir /app verboflex

WORKDIR /app
COPY --from=builder --chown=verboflex:verboflex /opt/venv /opt/venv
COPY --from=builder --chown=verboflex:verboflex /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=verboflex:verboflex /app/alembic /app/alembic

USER verboflex
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).read()"]

CMD ["uvicorn", "verboflex.main:app", "--host", "0.0.0.0", "--port", "8000"]

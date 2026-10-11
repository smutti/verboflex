# syntax=docker/dockerfile:1.8
FROM ghcr.io/astral-sh/uv:0.11.12 AS uv
FROM python:3.12-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    VERBOFLEX_MCP_SESSION_FILE=/sessions/mcp-session.json
RUN groupadd --gid 10001 verboflex && useradd --uid 10001 --gid verboflex --create-home verboflex \
    && mkdir /sessions && chown verboflex:verboflex /sessions && chmod 700 /sessions
COPY --from=builder /opt/venv /opt/venv
USER verboflex
ENTRYPOINT ["verboflex-mcp"]
CMD ["serve"]

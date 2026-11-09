FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first so code changes reuse this layer.
COPY advanced-agent/pyproject.toml advanced-agent/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy only the application code, never the whole directory (it may hold a local .env).
COPY advanced-agent/api.py advanced-agent/main.py ./
COPY advanced-agent/src ./src

RUN useradd --create-home --uid 10001 app
USER app

ENV PATH="/app/.venv/bin:$PATH" PORT=8080

# Cloud Run supplies PORT at runtime.
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT}"]

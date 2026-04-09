# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# --- dependency layer (cached unless pyproject.toml / uv.lock change) ---
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --compile-bytecode .

# --- application code ---
COPY backend/ .
COPY scripts/ ./scripts/

# --- slim runtime (no uv) ---
FROM python:3.14-slim
WORKDIR /app
COPY --from=base /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=base /usr/local/bin /usr/local/bin
COPY --from=base /app /app

CMD ["python", "-m", "nodelens.workers.ingestor"]

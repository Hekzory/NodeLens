FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# --- dependency layer (cached unless pyproject.toml changes) ---
COPY backend/pyproject.toml .
RUN uv pip install --system --no-cache --compile-bytecode .

# --- application code ---
COPY backend/ .
COPY scripts/ ./scripts/

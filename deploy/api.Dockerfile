FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY backend/ .
COPY scripts/ ./scripts/

RUN uv pip install --system --no-cache .

EXPOSE 8000

CMD ["python", "-m", "nodelens.api"]

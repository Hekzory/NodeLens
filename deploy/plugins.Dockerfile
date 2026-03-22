FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY backend/ .
COPY plugins/ ./plugins/

RUN uv pip install --system --no-cache .

# Install per-plugin extra requirements (if any).
RUN find plugins -name requirements.txt -size +0 \
        -exec uv pip install --system --no-cache -r {} \; || true

CMD ["python", "-m", "nodelens.workers.plugin_runner"]

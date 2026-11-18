# Edge collector: MQTT + outbox + sender. Core deps only.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY collector ./collector
RUN useradd --uid 10001 --no-create-home edge && mkdir -p /data && chown edge /data
USER edge
CMD ["uv", "run", "--no-sync", "python", "-m", "collector.main"]

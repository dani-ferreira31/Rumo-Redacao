FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    RUFF_CACHE_DIR=/tmp/ruff-cache \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY . .

FROM base AS prod
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
RUN useradd --create-home app && mkdir -p /data/storage && chown app /data/storage
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

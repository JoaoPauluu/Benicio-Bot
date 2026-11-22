# ---- build: resolve deps with uv into /app/.venv ---------------------------
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# ---- runtime ---------------------------------------------------------------
FROM python:3.12-slim-bookworm
# libmagic: neonize (python-magic) media detection; ffmpeg: neonize probes/thumbnails videos it sends
RUN apt-get update \
 && apt-get install -y --no-install-recommends libmagic1 ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 1000 benicio
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY prompts ./prompts
ENV PATH=/app/.venv/bin:$PATH \
    BOT_HOME=/app \
    DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1
RUN mkdir -p /app/data && chown benicio:benicio /app/data
USER benicio
# WhatsApp session (session.db) + bot state (schedules, toggles) live here
VOLUME ["/app/data"]
CMD ["whatsapp-bot"]

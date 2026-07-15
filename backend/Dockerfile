# Build from the REPO ROOT so the CSV dataset is in context:
#   docker build -f backend/Dockerfile -t fleet-copilot-api .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /srv

COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev

COPY backend/app ./backend/app
COPY archive ./archive

# Seed the SQLite database at BUILD time so the container boots instantly and
# passes the healthcheck immediately (no 2-3 min first-boot seed racing the
# probe). No API key needed here - seeding is pure ETL + optional OSRM fetch.
RUN cd backend && uv run python -m app.etl.seed

WORKDIR /srv/backend
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Shell form so $PORT is expanded at runtime (Railway provides it).
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

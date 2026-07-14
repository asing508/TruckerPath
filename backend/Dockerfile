# Build from the REPO ROOT so the CSV dataset is in context:
#   docker build -f backend/Dockerfile -t fleet-copilot-api .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /srv

COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev

COPY backend/app ./backend/app
COPY archive ./archive

WORKDIR /srv/backend
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# first boot seeds SQLite from ../archive (takes ~1 min, incl. OSRM fetch)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

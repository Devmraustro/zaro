# ZARO API

Backend API for the ZARO Commerce + OS platform.

## Development

```bash
# Install dependencies
uv sync

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Run tests
uv run pytest

# Run linting
uv run ruff check .
uv run ruff format .
```

## Docker

```bash
docker compose up zaro-api
```

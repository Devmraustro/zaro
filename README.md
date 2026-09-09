# ZARO

Modern furniture & metalwork commerce platform. A full-stack application for managing orders, quotes, production, inventory, and customers in a workshop environment.

## Architecture

ZARO is a monorepo managed with **pnpm workspaces** and **Turborepo**, containing:

| Package | Technology | Description |
|---------|------------|-------------|
| `apps/zaro-api` | Python 3.12+, FastAPI, SQLAlchemy Async, PostgreSQL, Redis | REST API backend |
| `apps/zaro-web` | Next.js 14, React, TypeScript | Web frontend (admin dashboard) |
| `packages/zaro-sdk` | TypeScript | Shared TypeScript SDK for API communication |

### Backend Stack (`apps/zaro-api`)

- **FastAPI** - Modern, fast web framework for building APIs
- **SQLAlchemy 2.0 (Async)** - Async ORM with full type safety
- **PostgreSQL 16** - Primary relational database
- **Redis 7** - Caching, sessions, rate limiting
- **Alembic** - Database migrations
- **Argon2id** - Password hashing
- **PyJWT** - JWT authentication
- **cryptography (Fernet)** - Field-level encryption
- **Pydantic v2** - Settings management & request/response validation
- **structlog** - Structured logging
- **uv** - Fast Python package installer

### Frontend Stack (`apps/zaro-web`)

- **Next.js 14 (App Router)** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first styling
- **React Query** - Server state management

## Key Features

- **Commerce Core** - Quotes, orders, customers, materials
- **Production Management** - Production orders, material reservations, quality control
- **Inventory Control** - Stock levels, movement ledger, idempotent mutations
- **Authentication & Authorization** - JWT access/refresh tokens, RBAC, session management
- **Audit Logging** - Comprehensive audit trail for all mutations
- **Security Hardening** - Rate limiting, host validation, secure cookies, CORS controls

## Development Setup

### Prerequisites

- **Node.js >= 20** (for frontend & tooling)
- **Python >= 3.12, < 3.15** (for backend)
- **pnpm >= 9** (package manager)
- **Docker & Docker Compose** (for PostgreSQL & Redis)
- **uv** (recommended for Python dependency management)

### Quick Start with Docker

```bash
# Start PostgreSQL, Redis, API, and Web
docker compose -f docker-compose.zaro.yml up -d --build

# Development with hot reload
docker compose -f docker-compose.zaro.yml -f docker-compose.zaro.dev.yml up
```

Services will be available at:
- API: http://localhost:8001 (docs at `/docs`)
- Web: http://localhost:3001
- PostgreSQL: localhost:5433 (user: zaro, password: zaro_dev_password)
- Redis: localhost:6380 (password: zaro_dev_redis_password)

### Local Backend Development

```bash
cd apps/zaro-api

# Install dependencies (uses uv)
uv sync

# Copy environment template
cp .env.example .env
# Edit .env with your settings

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Local Frontend Development

```bash
cd apps/zaro-web

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

## Environment Configuration

All configuration is via environment variables prefixed with `ZARO_`. See `apps/zaro-api/.env.example` for the complete list.

### Required for Production

| Variable | Description |
|----------|-------------|
| `ZARO_SECRET_KEY` | 32+ char random string for JWT signing |
| `ZARO_ENCRYPTION_KEY` | Fernet key for field encryption (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `ZARO_DATABASE_URL` | PostgreSQL connection string |
| `ZARO_REDIS_URL` | Redis connection string |
| `ZARO_CORS_ORIGINS` | Explicit list of allowed origins (JSON array) |
| `ZARO_ALLOWED_HOSTS` | Explicit list of allowed Host headers (JSON array) |

The application **fails fast** in production if insecure defaults are detected.

## Database Migrations

```bash
cd apps/zaro-api

# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Downgrade
uv run alembic downgrade -1
```

## Testing

```bash
cd apps/zaro-api

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_security.py -v
```

## Linting & Type Checking

```bash
cd apps/zaro-api

# Lint with Ruff
uv run ruff check .
uv run ruff format .

# Type check with mypy
uv run mypy app
```

## Security Principles

- **No secrets in code** - All credentials via environment variables
- **Production posture validation** - App refuses to start with insecure defaults
- **Argon2id** - Memory-hard password hashing
- **JWT with short expiry** - Access tokens (30 min), refresh tokens (30 days, rotated)
- **Fernet encryption** - Field-level encryption for sensitive data
- **Rate limiting** - Per-IP and per-endpoint limits
- **Host header validation** - Rejects requests with unexpected Host in production
- **Secure cookies** - HttpOnly, Secure, SameSite=Lax in production
- **CORS** - Explicit origins only, no wildcards in production

## Project Structure

```
ZARO/
├── apps/
│   ├── zaro-api/           # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/        # API routes & dependencies
│   │   │   ├── core/       # Config, security, exceptions
│   │   │   ├── db/         # Database session & base
│   │   │   ├── models/     # SQLAlchemy models
│   │   │   ├── schemas/    # Pydantic schemas
│   │   │   └── services/   # Business logic
│   │   ├── alembic/        # Database migrations
│   │   ├── tests/          # Unit & integration tests
│   │   └── pyproject.toml  # Python project config
│   └── zaro-web/           # Next.js frontend
├── packages/
│   └── zaro-sdk/           # Shared TypeScript SDK
├── docker/                 # Dockerfiles
├── docs/                   # Architecture & design docs
├── docker-compose.zaro.yml       # Production-like compose
├── docker-compose.zaro.dev.yml   # Development overrides
├── package.json            # Root package.json (Turborepo)
├── pnpm-workspace.yaml     # pnpm workspace config
├── turbo.json              # Turborepo config
└── .gitignore
```

## Documentation

See `docs/` for detailed architecture and design documents:

- `ZARO_SYSTEM_ARCHITECTURE.md` - Overall system design
- `ZARO_API_DESIGN.md` - API design principles
- `ZARO_DATABASE_DESIGN.md` - Database schema & conventions
- `ZARO_SECURITY_ARCHITECTURE.md` - Security model
- `ZARO_THREAT_MODEL.md` - Threat analysis
- `ZARO_PHASE_1_4_SECURITY_REVIEW.md` - Security review findings

## License

Private - All rights reserved.
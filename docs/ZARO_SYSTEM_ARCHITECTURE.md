# ZARO System Architecture

**Version:** 1.1
**Status:** Phase 2.5 - Production Baseline
**Last Updated:** 2026-08-22

> **Separation note (2026-08-22):** ZARO now lives in its own independent repository.
> Section 2 ("Current Repository State") describes the *pre-separation* context and is
> preserved for historical accuracy only; commands referencing a shared base
> `docker-compose.yml` are superseded by the standalone `docker-compose.zaro.yml`.

---

## 1. System Overview

ZARO is a production-grade commerce and business management platform for a modern furniture and metalwork workshop. It consists of two tightly coupled systems:

- **ZARO Commerce** — public customer-facing platform (browse, buy, custom requests)
- **ZARO OS** — private business management system (products, orders, payments, production, inventory, accounting)

---

## 2. Current Repository State

### 2.1 Existing Project: AUSTRO Studio

The repository currently contains **AUSTRO Studio** — an AI workflow automation platform. This is a **different product** from ZARO. It was built as a visual workflow builder with:

- Workflow execution engine with versioning, replay, run logs
- LangGraph / LLM provider integration
- Celery worker for async execution
- WebSocket live updates
- File storage (local + S3/MinIO)
- Plugin system
- Multi-workspace with RBAC

**Key decision:** ZARO will be built as a **new application** (`apps/zaro-api`, `apps/zaro-web`) within the existing monorepo, reusing shared infrastructure but owning its own domain models. AUSTRO Studio code will NOT be modified or deleted.

### 2.2 Existing Infrastructure (Reusable)

| Component                               | Status  | Reusable          |
| --------------------------------------- | ------- | ----------------- |
| Docker Compose (Postgres, Redis, MinIO) | Working | Yes               |
| Dockerfiles                             | Working | Adapt for ZARO    |
| CI/CD workflows                         | Working | Extend for ZARO   |
| Git hooks (husky, lint-staged)          | Working | Yes               |
| Turborepo + pnpm monorepo               | Working | Yes               |
| Python venv + uv                        | Working | Parallel for ZARO |
| Shared TS packages (types, ui, sdk)     | Working | Extend            |

### 2.3 Existing Backend (AUSTRO API)

- **Location:** `apps/api/`
- **Stack:** FastAPI + SQLAlchemy + Alembic + Celery + Redis
- **Python:** 3.12+
- **Models:** User, Workspace, WorkspaceMember, Workflow, WorkflowRun, WorkflowVersion, Provider, Environment, FileAsset, Plugin
- **Auth:** JWT (access + refresh tokens), bcrypt password hashing
- **RBAC:** 4 roles (Owner, Admin, Editor, Viewer) — workspace-scoped
- **Security:** Fernet encryption at rest, CORS, request context middleware
- **Tests:** 195 unit tests, integration test suite (partially infra-gated)
- **Migrations:** 3 Alembic migrations

### 2.4 Existing Frontend (AUSTRO Web)

- **Location:** `apps/web/`
- **Stack:** Next.js 15, React 19, TypeScript, App Router
- **UI:** Custom component library (`@austro/ui`) — Button, Input, Card, Badge, etc.
- **SDK:** `@austro/sdk` — typed API client
- **Tests:** 31 tests (vitest)
- **Build:** Compiles successfully

---

## 3. Target Architecture

### 3.1 Monorepo Structure

```
/
├── apps/
│   ├── api/              # AUSTRO Studio API (existing, untouched)
│   ├── web/              # AUSTRO Studio Web (existing, untouched)
│   ├── zaro-api/         # ZARO Backend API (NEW)
│   └── zaro-web/         # ZARO Frontend (NEW)
├── packages/
│   ├── types/            # Shared TypeScript types (extend for ZARO)
│   ├── ui/               # Shared UI components (extend for ZARO)
│   ├── sdk/              # AUSTRO SDK (existing)
│   ├── zaro-sdk/         # ZARO typed API client (NEW)
│   ├── shared/           # Shared utilities (existing)
│   ├── workflow-core/    # AUSTRO workflow engine (existing)
│   └── tsconfig/         # Shared TS configs (existing)
├── docker/               # Dockerfiles (extend for ZARO)
├── docs/                 # Architecture docs (NEW)
├── docker-compose.yml    # Base compose (extend for ZARO)
├── docker-compose.dev.yml # Dev overrides (extend for ZARO)
└── ...config files
```

### 3.2 ZARO Backend (`apps/zaro-api/`)

```
apps/zaro-api/
├── app/
│   ├── main.py                    # FastAPI app factory
│   ├── core/
│   │   ├── config.py              # Environment-based settings
│   │   ├── security.py            # Auth, JWT, password hashing, encryption
│   │   ├── events.py              # Lifespan, startup/shutdown
│   │   ├── exceptions.py          # Typed exception handlers
│   │   └── logging.py             # Structured logging (structlog)
│   ├── db/
│   │   ├── base.py                # SQLAlchemy declarative base
│   │   ├── session.py             # Async session factory
│   │   └── redis.py               # Redis connection pool
│   ├── models/                    # SQLAlchemy models
│   │   ├── mixins.py              # UUID PK, Timestamp mixins
│   │   ├── enums.py               # All enums (roles, statuses, etc.)
│   │   ├── user.py                # User accounts
│   │   ├── customer.py            # Customer records
│   │   ├── product.py             # Products + variants
│   │   ├── category.py            # Product categories
│   │   ├── material.py            # Materials + pricing
│   │   ├── inventory.py           # Stock levels + movements
│   │   ├── custom_request.py      # Custom order requests
│   │   ├── quote.py               # Quotations
│   │   ├── design_revision.py     # Versioned design specs
│   │   ├── order.py               # Orders + state machine
│   │   ├── order_item.py          # Order line items
│   │   ├── payment.py             # Manual CCP payments
│   │   ├── production_order.py    # Production tracking
│   │   ├── production_stage.py    # Stage-level tracking
│   │   ├── delivery.py            # Delivery tracking
│   │   ├── expense.py             # Business expenses
│   │   ├── file_asset.py          # Uploaded files
│   │   ├── audit_log.py           # Append-only audit trail
│   │   └── setting.py             # System settings
│   ├── schemas/                   # Pydantic request/response
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── customer.py
│   │   ├── product.py
│   │   ├── material.py
│   │   ├── inventory.py
│   │   ├── custom_request.py
│   │   ├── quote.py
│   │   ├── order.py
│   │   ├── payment.py
│   │   ├── production.py
│   │   ├── delivery.py
│   │   ├── expense.py
│   │   ├── audit.py
│   │   └── common.py              # Pagination, filters, etc.
│   ├── services/                  # Business logic
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── customer_service.py
│   │   ├── product_service.py
│   │   ├── material_service.py
│   │   ├── inventory_service.py
│   │   ├── custom_request_service.py
│   │   ├── quote_service.py
│   │   ├── design_service.py
│   │   ├── order_service.py
│   │   ├── payment_service.py
│   │   ├── production_service.py
│   │   ├── delivery_service.py
│   │   ├── expense_service.py
│   │   ├── file_service.py
│   │   ├── audit_service.py
│   │   ├── pricing_engine.py      # Cost + margin calculation
│   │   └── rbac_service.py        # Role-permission matrix
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py          # Aggregate router
│   │   │   ├── deps.py            # Dependency injection
│   │   │   └── endpoints/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── products.py
│   │   │       ├── categories.py
│   │   │       ├── materials.py
│   │   │       ├── inventory.py
│   │   │       ├── custom_requests.py
│   │   │       ├── quotes.py
│   │   │       ├── orders.py
│   │   │       ├── payments.py
│   │   │       ├── production.py
│   │   │       ├── deliveries.py
│   │   │       ├── expenses.py
│   │   │       ├── customers.py
│   │   │       ├── files.py
│   │   │       ├── audit.py
│   │   │       ├── settings.py
│   │   │       └── health.py
│   │   └── middleware.py          # Request context, rate limiting
│   └── storage/                   # File storage abstraction
│       ├── base.py
│       ├── local.py
│       └── s3.py
├── alembic/                       # Database migrations
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── alembic.ini
├── pyproject.toml
└── README.md
```

### 3.3 ZARO Frontend (`apps/zaro-web/`)

```
apps/zaro-web/
├── src/
│   ├── app/
│   │   ├── layout.tsx                     # Root layout (brand, fonts)
│   │   ├── page.tsx                       # Homepage
│   │   ├── globals.css                    # Design tokens
│   │   ├── shop/
│   │   │   └── page.tsx                   # Product listing
│   │   ├── products/
│   │   │   └── [slug]/
│   │   │       └── page.tsx               # Product detail
│   │   ├── custom/
│   │   │   └── page.tsx                   # Custom request form
│   │   ├── cart/
│   │   │   └── page.tsx                   # Shopping cart
│   │   ├── checkout/
│   │   │   └── page.tsx                   # Checkout flow
│   │   ├── order/
│   │   │   └── [reference]/
│   │   │       └── page.tsx               # Order tracking
│   │   ├── about/
│   │   │   └── page.tsx                   # About page
│   │   ├── contact/
│   │   │   └── page.tsx                   # Contact page
│   │   └── admin/
│   │       ├── layout.tsx                 # Admin layout (auth guard)
│   │       ├── page.tsx                   # Dashboard
│   │       ├── products/
│   │       ├── materials/
│   │       ├── customers/
│   │       ├── leads/
│   │       ├── quotes/
│   │       ├── orders/
│   │       ├── payments/
│   │       ├── production/
│   │       ├── inventory/
│   │       ├── expenses/
│   │       ├── settings/
│   │       └── audit/
│   ├── components/
│   │   ├── ui/                            # ZARO-specific UI components
│   │   ├── layout/                        # Header, Footer, Sidebar
│   │   ├── product/                       # Product cards, galleries
│   │   ├── cart/                          # Cart components
│   │   ├── checkout/                      # Checkout forms
│   │   ├── admin/                         # Admin dashboard widgets
│   │   └── shared/                        # Reusable components
│   ├── lib/
│   │   ├── api.ts                         # API client
│   │   ├── auth.ts                        # Auth utilities
│   │   ├── format.ts                      # Currency, date formatting
│   │   └── constants.ts                   # Brand constants
│   ├── hooks/                             # Custom React hooks
│   └── types/                             # Frontend types
├── public/
│   └── images/                            # Static assets
├── package.json
├── next.config.ts
├── tsconfig.json
└── tailwind.config.ts
```

### 3.4 Technology Stack

| Layer                      | Technology            | Version |
| -------------------------- | --------------------- | ------- |
| **Frontend**               | Next.js (App Router)  | 15.x    |
| **UI Framework**           | React                 | 19.x    |
| **Styling**                | Tailwind CSS          | 4.x     |
| **Language**               | TypeScript            | 5.8.x   |
| **Backend**                | FastAPI               | 0.115+  |
| **ORM**                    | SQLAlchemy (async)    | 2.0+    |
| **Migrations**             | Alembic               | 1.13+   |
| **Validation**             | Pydantic v2           | 2.9+    |
| **Database**               | PostgreSQL            | 16+     |
| **Cache**                  | Redis                 | 7+      |
| **File Storage**           | MinIO (S3-compatible) | latest  |
| **Package Manager**        | pnpm                  | 11.x    |
| **Monorepo Tool**          | Turborepo             | 2.3+    |
| **Python Tooling**         | uv                    | latest  |
| **Linting (Python)**       | Ruff                  | 0.7+    |
| **Type Checking (Python)** | mypy                  | 1.11+   |
| **Testing (Python)**       | pytest                | 8.3+    |
| **Testing (TS)**           | Vitest                | 2.1+    |
| **Containerization**       | Docker + Compose      | latest  |
| **CI/CD**                  | GitHub Actions        | —       |

---

## 4. Data Flow Architecture

### 4.1 Customer Journey — Ready-Made Product

```
Customer → ZARO Commerce Web → GET /api/v1/products
  → Product listing / detail page
  → Add to cart (client-side or server session)
  → POST /api/v1/orders (checkout)
  → Order created (DRAFT)
  → Customer submits payment proof
  → POST /api/v1/payments (submit)
  → Payment status: SUBMITTED
  → Owner reviews in ZARO OS Admin
  → PATCH /api/v1/payments/{id}/confirm
  → Payment status: CONFIRMED
  → Order state: CONFIRMED → PRODUCTION
  → Production team tracks progress
  → Delivery scheduled
  → Customer tracks at /order/{reference}
```

### 4.2 Customer Journey — Custom Order

```
Customer → ZARO Commerce Web → /custom
  → POST /api/v1/custom-requests (with images, specs)
  → Custom Request created
  → Owner reviews in ZARO OS Admin
  → Owner creates quote
  → POST /api/v1/quotes (line items, pricing)
  → Customer receives quote notification
  → Customer approves quote
  → POST /api/v1/quotes/{id}/approve
  → Deposit requested
  → Customer submits deposit payment
  → POST /api/v1/payments (deposit)
  → Owner confirms payment
  → Design revision workflow begins
  → Customer approves final design
  → POST /api/v1/design-revisions/{id}/approve
  → Production begins
  → Quality control
  → Delivery
```

### 4.3 Internal Business Flow

```
ZARO OS Admin Dashboard
  → View pending orders
  → View production queue
  → Manage inventory levels
  → Track expenses
  → View financial summary
  → Manage product catalog
  → Process custom requests
  → Generate quotes
  → Verify payments
  → Track deliveries
```

---

## 5. Security Boundaries

### 5.1 Trust Boundaries

```
┌─────────────────────────────────────────────────┐
│                  INTERNET                        │
├─────────────────────────────────────────────────┤
│  Public Commerce Pages (no auth required)        │
│  - Product browsing                              │
│  - Custom request submission                     │
│  - Order tracking (by reference)                 │
├─────────────────────────────────────────────────┤
│  Customer Auth Required                          │
│  - Checkout                                      │
│  - Order history                                 │
│  - Payment submission                            │
│  - Quote approval                                │
│  - Design approval                               │
├─────────────────────────────────────────────────┤
│  Admin Auth + RBAC Required                      │
│  - Product management                            │
│  - Order management                              │
│  - Payment confirmation                          │
│  - Production management                         │
│  - Financial data                                │
│  - Customer data                                 │
│  - Audit logs                                    │
│  - Settings                                      │
├─────────────────────────────────────────────────┤
│  Owner-Only Actions                              │
│  - Payment confirmation                          │
│  - Price changes                                 │
│  - Permission management                         │
│  - System settings                               │
│  - Financial reports                             │
│  - Secret management                             │
├─────────────────────────────────────────────────┤
│  Backend (API + DB + Redis)                      │
│  - All business logic enforced server-side       │
│  - Database transactions for critical ops        │
│  - Audit logging for sensitive actions           │
└─────────────────────────────────────────────────┘
```

### 5.2 Authorization Matrix (V1)

| Action                | OWNER | ADMIN | WORKER       | CUSTOMER |
| --------------------- | ----- | ----- | ------------ | -------- |
| Browse products       | Yes   | Yes   | Yes          | Yes      |
| Submit custom request | Yes   | Yes   | Yes          | Yes      |
| View own orders       | Yes   | Yes   | —            | Yes      |
| Confirm payment       | Yes   | No    | No           | No       |
| Change prices         | Yes   | No    | No           | No       |
| Manage products       | Yes   | Yes   | View only    | No       |
| Manage production     | Yes   | Yes   | Update stage | No       |
| View expenses/revenue | Yes   | Yes   | No           | No       |
| Manage permissions    | Yes   | No    | No           | No       |
| Delete records        | Yes   | No    | No           | No       |
| Access audit logs     | Yes   | No    | No           | No       |

---

## 6. Scalability Considerations

### 6.1 V1 Scope (Two-Person Workshop)

- Single server deployment
- PostgreSQL on same machine or Docker
- Redis for caching and sessions
- MinIO for file storage
- Single worker process
- No horizontal scaling needed

### 6.2 Growth Path

```
Phase 1: Workshop (V1)
  - 2 users, ~50 products, ~200 orders/year
  - Single server, Docker Compose

Phase 2: Small Company (V2)
  - 5-10 users, ~200 products, ~1000 orders/year
  - Separate DB server
  - CDN for static assets
  - Background job queue

Phase 3: Growing Company (V3)
  - 10-30 users, ~500 products, ~5000 orders/year
  - Load balancer
  - Read replicas
  - Dedicated worker servers
  - Monitoring stack (Grafana/Prometheus)

Phase 4: Scale (V4)
  - Multi-warehouse
  - Advanced analytics
  - AI-powered pricing/design
  - Mobile apps
  - API integrations (payment gateways, shipping)
```

---

## 7. Observability

### 7.1 Logging

- Structured JSON logs via `structlog`
- Request context propagation (request ID, user ID)
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Sensitive data excluded (passwords, tokens, secrets)

### 7.2 Health Checks

- `GET /healthz` — liveness (is the process running?)
- `GET /readyz` — readiness (can it serve traffic?)
  - PostgreSQL connection
  - Redis connection
  - S3/MinIO connection
  - Disk space (if local storage)

### 7.3 Audit Trail

- Append-only `audit_logs` table
- Records: actor, action, target, timestamp, IP, details
- Covers: auth events, payment events, order state changes, price changes, permission changes

---

## 8. Deployment Architecture

### 8.1 Development

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### 8.2 Production (Single Server)

```
┌──────────────────────────────────────┐
│           Production Server           │
│                                        │
│  ┌─────────┐  ┌─────────┐            │
│  │  Nginx   │  │  Caddy  │  (TLS)    │
│  │ (reverse │  │         │            │
│  │  proxy)  │  │         │            │
│  └────┬─────┘  └────┬────┘           │
│       │              │                │
│  ┌────┴──────────────┴────┐          │
│  │    Docker Compose       │          │
│  │  ┌────────┐ ┌────────┐ │          │
│  │  │  API   │ │  Web   │ │          │
│  │  │ :8000  │ │ :3000  │ │          │
│  │  └────────┘ └────────┘ │          │
│  │  ┌────────┐ ┌────────┐ │          │
│  │  │ Postgres│ │ Redis  │ │          │
│  │  │ :5432  │ │ :6379  │ │          │
│  │  └────────┘ └────────┘ │          │
│  │  ┌────────┐             │          │
│  │  │ MinIO  │             │          │
│  │  │ :9000  │             │          │
│  │  └────────┘             │          │
│  └─────────────────────────┘          │
│                                        │
│  Automated daily backups              │
│  TLS via Let's Encrypt                │
└──────────────────────────────────────┘
```

---

## 9. Migration Strategy from Existing Codebase

### 9.1 What to Reuse

- Docker Compose infrastructure (Postgres, Redis, MinIO)
- Package manager setup (pnpm + Turborepo)
- Git hooks and lint-staged config
- CI workflow structure
- `.env.example` pattern
- Shared tsconfig packages
- Shared UI component patterns (adapt for ZARO brand)
- Python project structure patterns (adapt for ZARO domain)
- Security patterns (JWT, bcrypt, Fernet, RBAC)

### 9.2 What to Build Fresh

- All ZARO domain models
- All ZARO business logic
- All ZARO API endpoints
- All ZARO frontend pages
- ZARO-specific design system
- ZARO payment workflow (manual CCP)
- ZARO order state machine
- ZARO production workflow
- ZARO cost calculation engine
- ZARO audit logging

### 9.3 What NOT to Touch

- `apps/api/` (AUSTRO Studio API)
- `apps/web/` (AUSTRO Studio Web)
- `packages/sdk/` (AUSTRO SDK)
- `packages/workflow-core/` (AUSTRO workflow engine)

---

## 10. Key Design Decisions

| Decision                         | Choice                           | Rationale                                                        |
| -------------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| Separate app vs extending AUSTRO | Separate `zaro-api` + `zaro-web` | Different domain, different models, clean separation             |
| UUID vs sequential IDs           | UUIDs                            | Security (no enumeration), suitable for public APIs              |
| Manual vs automated payments     | Manual CCP (V1)                  | Business requirement; architecture supports adding gateway later |
| Session vs JWT                   | JWT (access + refresh)           | Stateless, scalable, already proven in AUSTRO                    |
| Monolith vs microservices        | Modular monolith                 | Appropriate for scale, simpler deployment, easier debugging      |
| File storage                     | S3-compatible (MinIO)            | Already in infrastructure, private by default                    |
| Background jobs                  | Minimal in V1                    | Celery available but used only where real value exists           |
| State management                 | Server-side state machines       | Prevents client-side manipulation of critical states             |

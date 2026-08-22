# ZARO Development Rules

**Version:** 1.0
**Status:** Active
**Last Updated:** 2026-08-18

---

## 1. Code Quality Rules

### 1.1 Zero Tolerance

- No duplicate code
- No placeholder implementation disguised as production code
- No TODO-driven architecture
- No hardcoded secrets
- No hardcoded business prices
- No insecure shortcuts
- No silent exception swallowing
- No broad catch blocks without handling
- No unnecessary dependencies
- No unnecessary microservices
- No direct database access from frontend
- No business authorization logic in the frontend
- No trust in client-provided prices
- No trust in client-provided payment status
- No trust in client-provided order status
- No sensitive information in logs
- No destructive migration without explicit safety consideration

### 1.2 Code Style

**Python:**

- Line length: 120 characters
- Formatter: Ruff
- Linter: Ruff (E, F, W, I, UP, B, SIM, C4, RUF)
- Type checker: mypy with pydantic plugin
- Python version: 3.12+

**TypeScript:**

- Formatter: Prettier
- Linter: ESLint
- Type checker: TypeScript strict mode
- Next.js App Router conventions

### 1.3 Naming Conventions

**Python:**

- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- API routes: `kebab-case` (rare, usually `snake_case` with FastAPI)

**TypeScript:**

- Files: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- Components: `PascalCase`
- Functions/variables: `camelCase`
- Constants: `UPPER_SNAKE_CASE`
- Types/Interfaces: `PascalCase`

### 1.4 File Organization

- One class/function per file when file exceeds 300 lines
- Related files grouped by domain (not by type)
- Tests mirror source structure
- No circular imports

---

## 2. Architecture Rules

### 2.1 Separation of Concerns

```
Endpoint (route handler)
  → Schema validation (Pydantic)
  → Service layer (business logic)
  → Repository layer (database access via SQLAlchemy)
  → Database (PostgreSQL)
```

- Endpoints handle HTTP concerns (request parsing, response formatting, status codes)
- Services handle business logic (rules, calculations, state machines)
- Models handle data structure and relationships
- No business logic in endpoints
- No HTTP concerns in services

### 2.2 Authorization Pattern

Every protected endpoint MUST:

1. Authenticate the user (get_current_user dependency)
2. Authorize the action (require_permission dependency or explicit check)
3. Log the action (audit service for sensitive operations)

```python
@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(
    payment_id: UUID,
    current_user: User = Depends(require_owner),  # Owner only
    db: AsyncSession = Depends(get_db),
):
    # Business logic in service
    payment = await payment_service.confirm(db, payment_id, current_user.id)
    return payment
```

### 2.3 State Machine Pattern

State transitions MUST be:

1. Defined as a dictionary of valid transitions
2. Validated before applying
3. Atomic (database transaction)
4. Audited (logged)

```python
VALID_ORDER_TRANSITIONS = {
    "DRAFT": ["QUOTED", "CANCELLED"],
    "QUOTED": ["CUSTOMER_APPROVED", "CANCELLED"],
    # ...
}

def transition_order(order: Order, new_status: str):
    if new_status not in VALID_ORDER_TRANSITIONS.get(order.status, []):
        raise InvalidStateTransition(order.status, new_status)
    order.status = new_status
```

### 2.4 Error Handling Pattern

```python
# Typed exceptions mapped to HTTP status codes
class NotFoundError(Exception): ...
class ForbiddenError(Exception): ...
class ConflictError(Exception): ...

# Exception handlers in main.py
register_exception_handlers(app)  # Maps exceptions to HTTP responses

# In services/ endpoints
raise NotFoundError("Order not found")  # → 404
raise ForbiddenError("Cannot confirm payments")  # → 403
raise ConflictError("Payment already confirmed")  # → 409
```

---

## 3. Security Rules

### 3.1 Authentication

- Passwords hashed with bcrypt (never stored plaintext)
- JWT with 30-minute access token expiry
- Refresh token rotation on every use
- Token blacklist in Redis
- No sensitive data in JWT payload

### 3.2 Authorization

- Server-side enforcement only
- Never rely on hiding UI elements
- Every endpoint checks permissions
- Customer data isolation enforced
- Worker permissions limited by design

### 3.3 Input Validation

- Pydantic schemas on every endpoint
- Server-side validation is the source of truth
- Client-side validation is UX only, never security
- Reject unexpected fields (no mass assignment)

### 3.4 Payment Security

- Customer can NEVER confirm payment
- Payment status transitions enforced server-side
- Financial operations require owner role
- All payment events audited

### 3.5 File Upload

- Validate MIME type (magic bytes, not extension alone)
- Enforce size limits
- UUID-based filenames
- Private storage
- Signed URL access
- No executable uploads

### 3.6 Secrets

- Environment variables only
- `.env` in `.gitignore`
- Never log secrets
- Never commit secrets
- `.env.example` with placeholders

---

## 4. Database Rules

### 4.1 Migrations

- Every schema change through Alembic migration
- Migrations must be reversible where possible
- Test migrations offline (`--sql`) before applying
- Never modify existing migrations in shared branches
- One migration per logical change

### 4.2 Queries

- Use SQLAlchemy ORM (no raw SQL in business logic)
- Eager loading to prevent N+1
- Pagination on all list queries
- Use `with_for_update()` for critical reads
- Transactions for multi-step operations

### 4.3 Data Integrity

- Foreign keys with appropriate cascade rules
- Unique constraints where needed
- NOT NULL on required fields
- Default values for optional fields
- CHECK constraints for complex rules (V2)

---

## 5. Testing Rules

### 5.1 Test Coverage Requirements

Every major module MUST have:

- Unit tests for business logic
- API tests for endpoints
- Authorization tests (RBAC)
- Input validation tests
- Error handling tests

### 5.2 Mandatory Security Tests

- Customer attempts to confirm payment → 403
- Customer attempts to change order status → 403
- Customer accesses another customer's order → 403
- Worker attempts to change prices → 403
- Invalid state transition → 400
- SQL injection attempt → 422
- Malicious file upload → 415
- Expired token → 401
- Missing authorization → 401

### 5.3 Test Organization

```
tests/
  conftest.py          # Shared fixtures
  unit/
    test_auth.py       # Authentication logic
    test_rbac.py       # Authorization
    test_products.py   # Product business logic
    test_orders.py     # Order state machine
    test_payments.py   # Payment state machine
    test_pricing.py    # Cost calculation
    test_inventory.py  # Stock management
  integration/
    test_auth_api.py   # Auth API endpoints
    test_products_api.py
    test_orders_api.py
    test_payments_api.py
```

### 5.4 Test Commands

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_payments.py

# Run only security tests
uv run pytest -k "forbidden or unauthorized or injection"
```

---

## 6. Git Rules

### 6.1 Branch Strategy

- `main` — production-ready code
- `develop` — integration branch
- `feature/*` — feature branches
- `fix/*` — bug fix branches
- `security/*` — security fixes

### 6.2 Commit Messages

```
type(scope): description

Examples:
feat(products): add product variant management
fix(payments): prevent status skip in payment flow
security(auth): rate limit login attempts
docs(api): update payment endpoint documentation
test(orders): add state machine transition tests
```

### 6.3 Pre-commit Checks

- Linting (Ruff for Python, ESLint for TypeScript)
- Formatting (Prettier for TypeScript, Ruff for Python)
- Type checking (mypy, tsc)
- All tests pass

### 6.4 Never Commit

- `.env` files
- Secrets, API keys, tokens
- `node_modules/`, `.venv/`
- Build artifacts
- Database dumps with sensitive data
- Production credentials

---

## 7. API Rules

### 7.1 RESTful Conventions

- `GET` — read (never modifies state)
- `POST` — create
- `PATCH` — partial update
- `DELETE` — delete (soft delete preferred)
- `PUT` — full replace (rare, prefer PATCH)

### 7.2 Response Format

- Success: resource object or list with pagination
- Error: `{ "error": { "code": "...", "message": "...", "details": [...] } }`
- Consistent field naming (camelCase in JSON)
- UUIDs as strings in JSON
- ISO 8601 timestamps

### 7.3 Versioning

- All endpoints under `/api/v1/`
- Breaking changes require new version
- Non-breaking additions within current version
- Deprecated endpoints documented with sunset date

### 7.4 Pagination

- Default page size: 20
- Maximum page size: 100
- Return total count
- Return `has_next` / `has_previous`

---

## 8. Deployment Rules

### 8.1 Development

- Docker Compose for local development
- Hot reload for both API and frontend
- Separate database for tests
- No shared state between developers

### 8.2 Production

- Docker images built from multi-stage Dockerfiles
- Non-root containers
- Health checks required
- Graceful shutdown handling
- Environment-based configuration
- No debug mode in production
- HTTPS required

### 8.3 Secrets

- Injected via environment variables
- Never in Docker images
- Never in source code
- Rotated periodically
- Documented in `.env.example`

---

## 9. Documentation Rules

### 9.1 Code Documentation

- Docstrings on all public functions and classes
- Type hints on all function signatures
- Complex algorithms documented inline
- API endpoints documented with OpenAPI

### 9.2 Architecture Documentation

- Keep docs/ updated with code changes
- Document WHY, not just WHAT
- Include security assumptions
- Include data flow diagrams
- Include deployment instructions

### 9.3 Operational Documentation

- Runbook for common issues
- Backup and restore procedures
- Incident response plan
- Monitoring and alerting setup

---

## 10. Performance Rules

### 10.1 Database

- No N+1 queries (use eager loading)
- Pagination on all list queries
- Index foreign keys and common filters
- Use `EXPLAIN ANALYZE` for slow queries
- Connection pooling via asyncpg

### 10.2 API

- Response time target: < 200ms for single resource, < 500ms for lists
- Pagination limits prevent unbounded queries
- File upload size limits prevent abuse
- Rate limiting prevents abuse

### 10.3 Frontend

- Image optimization (next/image)
- Lazy loading for below-fold content
- Static generation where possible
- Code splitting per route

---

## 11. Future AI Integration Rules

When AI is added in the future:

1. AI NEVER has unrestricted database access
2. AI uses controlled tools with authorization
3. Sensitive actions require human approval
4. All AI actions are audited
5. Prompt injection protection required
6. Output validation required
7. Rate limiting on AI operations
8. Cost tracking for AI operations

---

## 12. Code Review Rules

### 12.1 Review Checklist

- [ ] No hardcoded secrets
- [ ] Input validation present
- [ ] Authorization checks present
- [ ] Error handling appropriate
- [ ] Tests included
- [ ] No duplicate code
- [ ] Follows naming conventions
- [ ] Documentation updated
- [ ] No unnecessary dependencies
- [ ] Security implications considered

### 12.2 Merge Requirements

- All CI checks pass
- At least one reviewer approval (for critical paths)
- No unresolved conversations
- Tests pass locally
- Branch up to date with main

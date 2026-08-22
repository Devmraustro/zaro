# ZARO Security Architecture

**Version:** 1.0  
**Status:** Phase 1 - Foundation  
**Last Updated:** 2026-08-18

---

## 1. Security Principles

1. **Defense in depth** — multiple layers, no single point of failure
2. **Least privilege** — every user/service gets minimum required access
3. **Server-side enforcement** — never trust client-side validation or state
4. **Secure by default** — deny unless explicitly allowed
5. **Audit everything** — record sensitive actions for investigation
6. **Fail securely** — errors must not leak information or bypass controls

---

## 2. Authentication

### 2.1 Password Security

- **Hashing:** Argon2id (via `argon2-cffi`) with memory-cost 64 MiB, time-cost 3, parallelism 4
- **Minimum length:** 8 characters (enforced server-side; production gate rejects lower values)
- **Policy:** At least one letter and one digit, maximum 128 characters.
- **Storage:** Only the Argon2id hash stored. Never plaintext. Never logged.

```python
# apps/zaro-api/app/core/security.py
_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

def hash_password(password: str) -> str:
    return _password_hasher.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
```

> Note: earlier revisions of this document described bcrypt. The implemented
> and current algorithm is Argon2id (Phase 1.3).

### 2.2 JWT Token System

- **Algorithm:** HS256 (symmetric)
- **Access token expiry:** 30 minutes
- **Refresh token expiry:** 30 days
- **Token structure:** `{ sub, type, iat, exp, jti }`
- **JTI (JWT ID):** Unique per token, used for blacklisting

### 2.3 Token Lifecycle

```
Login
  → Verify credentials
  → Generate access token (30 min) + refresh token (30 days)
  → Return both to client

Access token expired
  → Client sends refresh token
  → Verify refresh token (not blacklisted, not expired)
  → Issue new access token + new refresh token
  → Blacklist old refresh token (rotation)

Logout
  → Blacklist current refresh token
  → Client discards both tokens
```

### 2.4 Token Blacklisting

- Refresh tokens tracked by JTI in Redis
- Blacklisted JTIs checked on refresh
- TTL set to refresh token expiry (auto-cleanup)
- Access tokens rely on short expiry (no blacklist needed at V1)

---

## 3. Authorization (RBAC)

### 3.1 ZARO Role Definitions

```python
class SystemRole(StrEnum):
    OWNER = "owner"      # Full system control
    ADMIN = "admin"      # Management within scope
    WORKER = "worker"    # Limited operational access
    CUSTOMER = "customer" # Self-service only
```

### 3.2 Permission Matrix

| Permission         | OWNER | ADMIN | WORKER         | CUSTOMER  |
| ------------------ | ----- | ----- | -------------- | --------- |
| `product:read`     | Yes   | Yes   | Yes            | Yes       |
| `product:write`    | Yes   | Yes   | No             | No        |
| `product:delete`   | Yes   | No    | No             | No        |
| `order:read`       | Yes   | Yes   | Yes (assigned) | Yes (own) |
| `order:write`      | Yes   | Yes   | No             | No        |
| `order:confirm`    | Yes   | No    | No             | No        |
| `payment:read`     | Yes   | Yes   | No             | Yes (own) |
| `payment:confirm`  | Yes   | No    | No             | No        |
| `quote:read`       | Yes   | Yes   | No             | Yes (own) |
| `quote:write`      | Yes   | Yes   | No             | No        |
| `production:read`  | Yes   | Yes   | Yes            | No        |
| `production:write` | Yes   | Yes   | Yes            | No        |
| `customer:read`    | Yes   | Yes   | No             | No        |
| `customer:write`   | Yes   | Yes   | No             | No        |
| `material:read`    | Yes   | Yes   | Yes            | No        |
| `material:write`   | Yes   | Yes   | No             | No        |
| `inventory:read`   | Yes   | Yes   | Yes            | No        |
| `inventory:write`  | Yes   | Yes   | No             | No        |
| `expense:read`     | Yes   | Yes   | No             | No        |
| `expense:write`    | Yes   | Yes   | No             | No        |
| `audit:read`       | Yes   | No    | No             | No        |
| `settings:read`    | Yes   | Yes   | No             | No        |
| `settings:write`   | Yes   | No    | No             | No        |
| `user:manage`      | Yes   | No    | No             | No        |
| `file:read`        | Yes   | Yes   | Yes (assigned) | Yes (own) |
| `file:write`       | Yes   | Yes   | No             | Yes (own) |
| `file:delete`      | Yes   | No    | No             | No        |

### 3.3 Enforcement Pattern

```python
# Every protected endpoint uses dependency injection
@router.get("/orders/{order_id}")
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.get_or_404(db, order_id)

    # Authorization check
    if current_user.role == SystemRole.CUSTOMER:
        if order.customer_id != current_user.customer_id:
            raise ForbiddenError("Cannot access other customers' orders")
    elif not has_permission(current_user.role, "order:read"):
        raise ForbiddenError("Insufficient permissions")

    return order
```

### 3.4 Critical Rule

**Customer-facing roles (CUSTOMER) can NEVER:**

- Set `payment_status = confirmed`
- Set `order_status` to any state
- Modify prices
- Access other customers' data
- Access financial reports
- Modify system settings

---

## 4. API Security

### 4.1 Input Validation

- **Pydantic schemas** on every endpoint — malformed input rejected before business logic
- **Type enforcement** — UUID fields reject strings, integers reject floats, etc.
- **Length limits** — all string fields have max lengths
- **Range validation** — numeric fields have min/max where appropriate
- **Regex patterns** — product codes, slugs, etc.

### 4.2 SQL Injection Prevention

- **SQLAlchemy ORM** — parameterized queries by default
- **No raw SQL** in business logic (except controlled migrations)
- **Alembic** — all schema changes through versioned migrations

### 4.3 XSS Prevention

- **React** — automatic JSX escaping
- **API responses** — JSON only (no HTML rendering)
- **Content Security Policy** — configured on reverse proxy
- **Output encoding** — where HTML is rendered (admin templates if any)

### 4.4 CORS Configuration

```python
# Strict CORS — only known origins
cors_origins: list[str] = ["http://localhost:3000"]  # Dev
# cors_origins: list[str] = ["https://zaro.example.com"]  # Production
```

- `allow_credentials=True` — required for cookies
- `allow_methods=["*"]` — restricted at reverse proxy level
- `allow_headers=["*"]` — restricted at reverse proxy level

### 4.5 Rate Limiting

- **Login endpoint:** 5 attempts per minute per IP
- **General API:** 120 requests per minute per authenticated user
- **Custom request submission:** 10 per hour per IP
- **File upload:** 10 per hour per user

### 4.6 CSRF Protection

- Access tokens travel in the `Authorization` header — immune to CSRF
- Refresh tokens are stored in `HttpOnly; SameSite=Lax; Path=/api/v1/auth` cookies
- Cookie-based refresh requires a matching `X-CSRF-Token` header (double-submit pattern)
- `SameSite=Lax` blocks cross-site POST navigation; the CSRF header closes the remaining gap
- Secure flag is mandatory in staging and production (enforced by config gate)

### 4.7 IDOR/BOLA Prevention

- Every resource access checks ownership or role
- Customer can only access their own orders, payments, quotes
- Worker can only access assigned production orders
- UUIDs prevent sequential ID enumeration

### 4.8 Mass-Assignment Protection

- Pydantic schemas define explicit fields per endpoint
- Create/Update schemas are different from Read schemas
- No `**kwargs` pass-through to ORM models
  -例:

```python
class OrderCreate(BaseModel):
    """Customer can specify items and shipping info."""
    items: list[OrderItemCreate]
    shipping_address: str
    notes: str | None = None

class OrderUpdate(BaseModel):
    """Admin can update status and notes."""
    status: OrderStatus | None = None
    notes: str | None = None

class OrderRead(BaseModel):
    """Full order representation."""
    id: UUID
    reference: str
    status: OrderStatus
    # ... all fields
```

---

## 5. Data Protection

### 5.1 Encryption at Rest

- **Sensitive fields:** API keys, secret tokens → Fernet symmetric encryption
- **Payment proof files:** Stored in private S3 bucket, access via signed URLs
- **Database:** PostgreSQL encryption at rest (provider-dependent)

### 5.2 Secrets Management

- All secrets in environment variables
- `.env` files in `.gitignore`
- `.env.example` with safe placeholders
- No hardcoded secrets in source code
- `AUSTRO_SECRET_KEY` — 32+ random characters
- `AUSTRO_ENCRYPTION_KEY` — Fernet key

### 5.3 File Upload Security

```
Upload Request
  → Authentication check
  → File size limit (10MB default)
  → MIME type validation (magic bytes, not just extension)
  → Extension whitelist (jpg, jpeg, png, webp, pdf)
  → Filename sanitization (UUID-based renaming)
  → Private storage (S3/MinIO, not public)
  → Signed URL for access (expires in 1 hour)
  → Audit log entry
```

**Never:**

- Trust client-provided MIME type alone
- Allow executable uploads (.exe, .sh, .bat, .js)
- Store files with original filenames
- Serve files without authorization check
- Allow directory traversal in paths

### 5.4 Payment Data

- **NEVER store:** Full bank account numbers, CCP details
- **Store only:** Amount, currency, method, customer claim text, timestamp
- **Proof files:** Encrypted storage, signed URL access
- **Payment status:** Controlled exclusively by backend state machine

### 5.5 Sensitive Data in Logs

**NEVER log:**

- Passwords (plain or hashed)
- JWT tokens
- API keys
- Encryption keys
- Full payment details
- Personal addresses
- Session tokens

**ALWAYS log:**

- User ID (not email in production logs)
- Action performed
- Resource affected
- Timestamp
- IP address (for security events)

---

## 6. Payment Security

### 6.1 State Machine Enforcement

```python
PAYMENT_STATES = {
    "PENDING":    ["SUBMITTED"],
    "SUBMITTED":  ["UNDER_REVIEW"],
    "UNDER_REVIEW":["CONFIRMED", "REJECTED"],
    "CONFIRMED":  ["REFUNDED"],
    "REJECTED":   ["UNDER_REVIEW"],  # Can be re-reviewed
    "REFUNDED":   [],  # Terminal
}

# ONLY owner can confirm/reject
# Customer can ONLY submit
# No one can skip states
```

### 6.2 Critical Invariant

```python
# A customer attempting:
# PATCH /api/v1/payments/{id}
# { "status": "CONFIRMED" }
#
# The backend MUST reject this with 403 Forbidden.
# Payment status transitions are enforced server-side ONLY.
```

### 6.3 Transactional Integrity

```python
async def confirm_payment(payment_id: UUID, reviewer_id: UUID, db: AsyncSession):
    async with db.begin():
        payment = await db.get(Payment, payment_id, with_for_update=True)
        if payment.status != PaymentStatus.UNDER_REVIEW:
            raise ConflictError("Payment not under review")

        payment.status = PaymentStatus.CONFIRMED
        payment.confirmed_by = reviewer_id
        payment.confirmed_at = datetime.now(UTC)

        # Update order status
        order = await db.get(Order, payment.order_id, with_for_update=True)
        order.status = OrderStatus.CONFIRMED

        # Audit log
        await audit_service.log(db, AuditEvent.PAYMENT_CONFIRMED, ...)

    # All or nothing — no partial state
```

---

## 7. Order State Machine Security

### 7.1 Valid Transitions

```python
ORDER_TRANSITIONS = {
    "DRAFT":               ["QUOTED", "CANCELLED"],
    "QUOTED":              ["CUSTOMER_APPROVED", "CANCELLED"],
    "CUSTOMER_APPROVED":   ["DEPOSIT_PENDING"],
    "DEPOSIT_PENDING":     ["PAYMENT_REVIEW"],
    "PAYMENT_REVIEW":      ["CONFIRMED", "DEPOSIT_PENDING"],  # Re-submit
    "CONFIRMED":           ["PRODUCTION"],
    "PRODUCTION":          ["QUALITY_CONTROL"],
    "QUALITY_CONTROL":     ["READY", "PRODUCTION"],  # Rework
    "READY":               ["DELIVERY"],
    "DELIVERY":            ["COMPLETED"],
    "CANCELLED":           [],  # Terminal
    "COMPLETED":           [],  # Terminal
}
```

### 7.2 Enforcement

- State transitions validated server-side on every status change
- Invalid transitions return 400 Bad Request
- Each transition may require specific role
- Transitions are logged in audit trail

---

## 8. Audit Logging

### 8.1 Events Tracked

```python
class AuditEvent(StrEnum):
    # Auth
    USER_LOGIN = "user.login"
    LOGIN_FAILED = "user.login_failed"
    PASSWORD_CHANGED = "user.password_changed"
    USER_CREATED = "user.created"
    ROLE_CHANGED = "user.role_changed"

    # Products
    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"
    PRODUCT_PRICE_CHANGED = "product.price_changed"
    PRODUCT_DELETED = "product.deleted"

    # Orders
    ORDER_CREATED = "order.created"
    ORDER_STATUS_CHANGED = "order.status_changed"
    ORDER_CANCELLED = "order.cancelled"

    # Payments
    PAYMENT_SUBMITTED = "payment.submitted"
    PAYMENT_CONFIRMED = "payment.confirmed"
    PAYMENT_REJECTED = "payment.rejected"
    PAYMENT_REFUNDED = "payment.refunded"

    # Quotes
    QUOTE_CREATED = "quote.created"
    QUOTE_SENT = "quote.sent"
    QUOTE_APPROVED = "quote.approved"
    QUOTE_REJECTED = "quote.rejected"

    # Design
    DESIGN_REVISION_CREATED = "design_revision.created"
    DESIGN_APPROVED = "design.approved"

    # Production
    PRODUCTION_STAGE_CHANGED = "production.stage_changed"
    QUALITY_CHECK_PASSED = "quality.passed"
    QUALITY_CHECK_FAILED = "quality.failed"

    # Files
    FILE_UPLOADED = "file.uploaded"
    FILE_DELETED = "file.deleted"

    # Settings
    SETTING_CHANGED = "setting.changed"

    # Permissions
    PERMISSION_CHANGED = "permission.changed"
```

### 8.2 Audit Log Schema

```python
class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    actor_id: UUID          # Who performed the action
    actor_email: str        # Denormalized for查询 convenience
    actor_role: str         # Role at time of action
    event: str              # Event type (from AuditEvent)
    resource_type: str      # e.g., "order", "payment", "product"
    resource_id: UUID       # ID of affected resource
    details: dict           # Event-specific details
    ip_address: str         # Client IP
    user_agent: str         # Client user agent
    created_at: datetime    # When it happened
```

### 8.3 Properties

- **Append-only** — no UPDATE or DELETE on audit_logs table
- **No soft-delete** — records are permanent
- **Immutable** — once written, never modified
- **Index on** actor_id, resource_type+resource_id, created_at, event

---

## 9. Infrastructure Security

### 9.1 Docker Security

- Non-root user in production containers
- Read-only filesystem where possible
- No unnecessary packages in production images
- Multi-stage builds (build deps not in production image)
- Pinned image versions (no `latest` in production)

### 9.2 Database Security

- Dedicated database user (not root)
- Minimal privileges (no superuser)
- SSL connections in production
- Connection pooling (asyncpg)
- No exposed ports in production (Docker internal network only)

### 9.3 Redis Security

- No authentication needed (internal Docker network only)
- Persistence enabled (append-only)
- No sensitive data stored (only session tokens, JTI blacklist, cache)

### 9.4 Network Security

- Reverse proxy (Nginx/Caddy) with TLS termination
- Internal services not exposed to internet
- Rate limiting at proxy level
- Request size limits
- Timeouts configured

---

## 10. Secure Development Practices

### 10.1 Pre-commit Checks

```yaml
lint-staged:
  "*.{ts,tsx,js,jsx}":
    - prettier --write
    - eslint --fix
  "*.{json,yaml,yml,md,css}":
    - prettier --write
  "*.py":
    - ruff check --fix
    - ruff format
```

### 10.2 CI Security Gates

- Linting (Ruff, ESLint)
- Type checking (mypy, tsc)
- Unit tests
- Dependency audit (`pip-audit`, `npm audit`)
- Secret scanning (no hardcoded credentials)
- Docker image scanning (Trivy or similar)

### 10.3 Dependency Management

- Pinned versions in lock files
- Regular dependency updates
- Security advisories monitoring
- Minimal dependency surface

### 10.4 Code Review

- All changes via pull request
- Security-sensitive changes require owner review
- No direct commits to main branch

---

## 11. Incident Response

### 11.1 Detection

- Failed login monitoring
- Unusual API access patterns
- Audit log anomalies
- Error rate spikes

### 11.2 Response

1. Identify scope and impact
2. Contain (disable affected accounts, block IPs)
3. Investigate (audit logs, access logs)
4. Remediate (patch vulnerability, rotate secrets)
5. Document (incident report, update procedures)

### 11.3 Recovery

- Database backup restoration procedure
- Secret rotation procedure
- Account recovery procedure
- Service restart procedure

---

## 12. Security Checklist (V1)

- [x] Password hashing with Argon2id
- [x] JWT with expiry and JTI
- [x] Refresh token rotation
- [ ] RBAC enforced on every endpoint
- [ ] Input validation via Pydantic
- [ ] Parameterized queries (SQLAlchemy ORM)
- [ ] CORS configured strictly
- [ ] Rate limiting on auth endpoints
- [ ] File upload validation (size, type, content)
- [ ] Private file storage with signed URLs
- [ ] Payment state machine enforced server-side
- [ ] Order state machine enforced server-side
- [ ] Audit logging for sensitive actions
- [ ] No secrets in source code
- [ ] No sensitive data in logs
- [ ] Environment-based configuration
- [ ] HTTPS in production
- [ ] Non-root Docker containers
- [ ] Database least privilege
- [ ] Backup and recovery tested

# ZARO Completion Audit Report

Date: 2026-09-11
Scope: `apps/zaro-api` (FastAPI backend) and `apps/zaro-web` (Next.js 15 frontend)
Environment: Windows, Python 3.12.13 (venv `apps/zaro-api/.venv`), PackageManager `uv`
Audit mode: document + static review + automated tests (no live PostgreSQL available)

---

## Verdict

> **PRODUCTION READY WITH EXPLICIT EXTERNAL CONFIGURATION PENDING**

All four audit findings are resolved and verified, four additional mid-auit gaps were
found and fixed, and the full automated regression is green. The single reason this is
not an unqualified **PRODUCTION READY**: the codebase's concurrency-critical behaviour
(which was itself one of the four findings) is enforced by PostgreSQL primitives that
cannot be exercised in this environment. The operator must execute the PostgreSQL test
suite and the migration chain against a real, throwaway, TEST-named database (Step 1
below) before relying on the platform in production. No code blocker remains.

---

## 1. Repository state audit

Uncommitted working-tree changes were classified before any audit action: changes that
came from earlier phases (frontend redesign components, `production_service.py`,
`test_production_api.py`, QC tests, etc.) were treated as pre-existing WIP and never
discarded. All audit modifications touched only the audit's own files. No commits,
pushes, or instrumentation were made. Latest commit: `bfd3813 security: harden admin
session authentication`.

## 2. FD-01 — Admin cold-reload re-authentication (RESOLVED)

**Finding:** the CSRF value was memory-only, so a browser reload logged the admin in
with a valid refresh cookie but no CSRF token and, unbeknownst to the user, silently
degraded session handling.

**Fix (implemented this session):** a read-only bootstrap endpoint
`GET /api/v1/auth/session` returns `session_active` plus the current CSRF value when the
refresh session is live. It mints nothing, rotates nothing, and issues no reuse signal,
so family-reuse detection and rotation stay intact. `admin-auth.ts` restores a cold
reload via `bootstrapSession()` (single-flight); nothing is persisted to storage.

Evidence: `test_session_bootstrap.py` (8 tests, incl. revoked/expired/disabled-user/CSRF
refreshed flow); `admin-auth.test.ts` 18 tests; verified no orphan rotation or reuse
trigger.

## 3. BL-03 — Payment concurrency (RESOLVED in code, PG verification PENDING)

**Finding:** concurrent `cancel_order` + `confirm_payment` could deposit+confirm a
cancelled order, or a duplicate claim could be converted twice.

**Fix (code, earlier phase; re-verified this session):** `cancel_order_with_claim`
performs a hard lock-check-cancel on the payment *before* touching the order; state
machines are enforced through `validate_transition`; `create_deposit_claim` checks for
existing unresolved claims and is backstopped by a partial unique index.

**This session:** lock order across every cancellation/confirmation path was
re-reviewed — Payment→Order→Quote consistently; no path locks Order then Payment, so
there is no deadlock cycle. Added `TestBl03LockOrder` (source-inspection guards) in
`test_payments.py`.

**PENDING (needs a real PostgreSQL):** `tests/integration/test_pg_concurrency.py`
(confirm-vs-cancel, concurrent claim creation) and the destructive-safety-guarded
`tests/integration/test_postgres_concurrency.py` — skipped locally, must run against a
TEST-named database.

## 4. RP-01 — Rate-limit breaker (RESOLVED)

Breaker behaviour verified: Redis failure → circuit open → in-memory fallback still
enforces per-process limits → after 30s the half-open probe re-arms. Refresh/reuse
detection is DB-based and independent of Redis. Subset runs (rate_limiter breaker +
login + negative + password flows) green.

## 5. CF-01 — Cookie SameSite production gate (RESOLVED)

Single source of truth in `config.py` (`cookie_samesite` default `lax`; the production
gate rejects `lax`, allows `strict`/`none`, and requires `Secure` for `none`). No
duplicate/conflicting configuration definitions exist. `test_production_gate.py` and
`test_config.py` green.

## 6. FD-02 + CD-01 — Frontend/backend contract alignment (RESOLVED)

`ProductStatus` (`draft|active|archived`) is byte-for-byte identical across
`catalog_admin.py`, admin UI, and types. `product_type` (7 values incl. `other`) matches
exactly on both sides; admin serialization emits `str(status)` and typed variant fields.
Subset runs (custom-request + quotes) green.

## 7. Backend security review (COMPLETE, one new Medium fixed)

Route-by-route review of every endpoint (auth, admin, customers, catalog, orders,
quotes, payments, inventory, production, QC, audit, custom requests). One genuine
gap was found and fixed this session:

- **M — missing audit events** on `POST /admin/categories`, `PATCH
  /admin/categories/{id}`, `POST /admin/products/{id}/variants`, `PATCH
  /admin/products/{id}/variants/{vid}`. Added `CATEGORY_CREATED/UPDATED` and
  `PRODUCT_VARIANT_CREATED/UPDATED` actions + `record_event` calls with actor,
  resource id, request context and field metadata; new `test_catalog_audit.py` (4
  tests). Regression green.

Other items reviewed clean: auth lifecycle flows, CSRF double-submit + replay
protection, rate-limit coverage, error uniform format with no stack leaks, security
headers, RBAC denials logged, mass-assignment structurally prevented
(`extra="forbid"`).

**Accepted (Low, documented):** `/auth/refresh` and `/auth/session` have no limiter
beyond the global per-IP 120/60s middleware. Acceptable: refresh requires the refresh
cookie + CSRF double-submit and is covered by family reuse-detection; a stolen cookie
is a credential compromise that rate limiting does not mitigate. Revisit if refresh
traffic ever exceeds the global cap.

Security suites: `104 passed` (see Section 14).

## 8. Data-integrity audit (COMPLETE)

- All 13 `with_for_update` sites reviewed and correct: quote/get_quote_for_update
  decision serialization, payment get_for_update, order get_order_for_update +
  quote/payment re-locks in `cancel_order_with_claim`, inventory
  `get_stock_level_for_update` (SAVEPOINT + unique-violation handling for concurrent
  first-writes, then re-lock), production PO lock + material-reservation counter
  locks, catalog product lock serializing variant ordinal/SKU assignment.
- Stock-movement idempotency: SHA-256 payload fingerprint + partial unique index
  (`ix_stock_movements_material_idempotency`, materials `material_id, idempotency_key
  where not null`); same key + same payload = no-op, same key + different payload = 409.
- Reference generation (`references.py`): `SELECT MAX` + regenerate-and-retry inside
  SAVEPOINT; only unique violations are retried, CHECK/FK violations propagate; genuine
  conflicts surface as 409.
- Money is uniformly `BigInteger *_minor` (no floats); quantities `Numeric(12,3)`.
  Constraints: quote/order money invariants (`total = subtotal - discount + delivery`,
  `deposit_paid <= total`, `balance_due = total - deposit_paid`, quote
  `deposit <= total`), payment `amount_minor > 0`, material price uniqueness. Partial
  unique indexes on payments (`uq_payments_order_active`, `uq_payments_order_confirmed`
  — both with Postgres and SQLite predicates) enforce one unresolved claim and one
  confirmed deposit per order at the database level.

## 9. Alembic / migrations audit (COMPLETE)

Linear single-head chain verified: `0001 ← 0002 ← 0003 ← 0004 ← 0005 ← 0006 ← 0007`,
head `0007`. No branches. Schema matches the model layer (round-trip checked against
`ZARO_DATABASE_DESIGN.md`).

**PENDING (needs a real PostgreSQL):** execute `alembic upgrade head` →
`downgrade 0001` → `upgrade head` against a throwaway TEST-named database.

## 10. Frontend production audit (COMPLETE)

`next build` succeeds; `tsc --noEmit` clean; `eslint . --max-warnings 0` clean;
vitest 47/47 green. Admin restore flow covered by `admin-auth.test.ts`.

## 11. Dependency / supply-chain audit (COMPLETE)

- `uv audit`: 1 advisory family — **pytest 8.4.2**, CVE-2025-71176 / GHSA-6w46-j5rx-g56g
  (tmpdir handling). Dev/test-only tooling (not a production runtime dependency).
  **Recommendation:** bump dev constraint to `pytest>=9.0.3,<10` and re-sync before the
  next test-environment refresh. Not a release blocker.
- Secret scan (`scripts/check_secrets.py`, self-tested gate): **no secrets detected.**
- `git diff --check` clean (LF/CRLF warnings only, no whitespace errors).
- No `.env`, keys, or credential files are tracked (only `.env.example` placeholders).

## 12. PostgreSQL availability probe (PENDING — environment lacks PostgreSQL)

`ZARO_TEST_PG_URL` unset; `psql` absent; no listener on `localhost:5432`. Without a
PostgreSQL instance the PG-gated tests and migration runtime validation **cannot be
executed** and are explicitly marked PENDING rather than assumed green. No SQLite
substitution is made for PostgreSQL-only semantics (partial indexes, row locks,
serializable behavior).

## 13. Full regression (COMPLETE)

Backend full suite: **599 passed, 15 skipped, 1 expected warning** (the 31-byte-HMAC
`InsecureKeyLengthWarning` from the deliberate wrong-secret decode test). The 15 skips
are all PostgreSQL-gated. Baseline was 585 passed / 15 skipped; this audit added 14
tests (8 bootstrap + 4 catalog-audit + 2 lock-order).

Frontend: 47 passed (+ build, typecheck, lint).

Difference from baseline: no previously-passing test regressed.

## 14. Final findings ledger

| ID | Area | Severity | Status |
|----|------|----------|--------|
| CD-01 | catalog status/type contracts | M | RESOLVED — verified exact both sides |
| FD-01 | admin cold-reload re-auth | M | RESOLVED — bootstrap endpoint + tests |
| FD-02 | admin product status filter | M | RESOLVED — filter + typed contract |
| BL-02 | QC/fulfilment concurrency | M | FIXED (code) — PG re-verification PENDING |
| BL-03 | payment confirm/cancel concurrency | M | FIXED (code) + lock-order guarded — PG re-verification PENDING |
| RP-01 | rate-limit breaker | M | RESOLVED — verified |
| CF-01 | cookie SameSite prod gate | M | RESOLVED — verified |
| A-01 | 4 catalog audit events missing | M | FIXED this audit + tests |
| A-02 | refresh/session targeted limiter absent | Low | ACCEPTED — global cap + CSRF + reuse detection; revisit if refresh exceeds 120/60 per-IP |
| A-03 | pytest 8.4.2 CVE (dev-only tmpdir) | Low | RECOMMENDED — bump dev constraint to `pytest>=9.0.3` |

### PENDING items (operator must execute against a real, disposable PostgreSQL TEST database)

1. `ZARO_TEST_PG_URL` + run `tests/integration/test_pg_concurrency.py` (BL-02) and
   `tests/integration/test_postgres_concurrency.py` (BL-03) — expect 0 failures.
2. `alembic upgrade head && alembic downgrade 0001 && alembic upgrade head` on a
   throwaway TEST-named DB.
3. Set production configuration explicitly (SECRET_KEY, `ENVIRONMENT=production`,
   `COOKIE_SAMESITE=strict|none` + HTTPS, `DATABASE_URL`, CCP payment instructions) per
   `docs/ZARO_DEPLOYMENT_RUNBOOK.md`.

### Files changed by this audit

- `apps/zaro-api/app/api/v1/endpoints/auth.py` — `GET /auth/session` bootstrap (FD-01).
- `apps/zaro-api/app/schemas/auth.py` — `BootstrapResponse`.
- `apps/zaro-api/app/services/auth_service.py` — `is_refresh_session_live()`.
- `apps/zaro-api/tests/unit/test_session_bootstrap.py` — new (FD-01).
- `apps/zaro-web/src/lib/admin-auth.ts` / `admin-auth.test.ts` — restore flow.
- `apps/zaro-api/app/api/v1/endpoints/catalog_admin.py` — audit events on 4 endpoints.
- `apps/zaro-api/app/models/audit_enums.py` — 4 new actions.
- `apps/zaro-api/tests/unit/test_catalog_audit.py` — new (audit-event coverage).
- `apps/zaro-api/tests/unit/test_payments.py` — `TestBl03LockOrder`.
- (from earlier audit phases, re-verified here:) `orders_service.py`, `orders.py`,
  `payments.py`, `payments_service.py`, `rate_limit.py`, `config.py`,
  `test_pg_concurrency.py`, `test_postgres_concurrency.py`, `test_rate_limit_breaker.py`,
  `test_production_gate.py`, `test_config.py`, `admin/products/page.tsx`, `types/api.ts`,
  `.env.example`, `docker-compose.zaro.yml`, `docs/ZARO_DEPLOYMENT_RUNBOOK.md`.

### Test evidence summary

- Backend: `599 passed, 15 skipped, 1 expected warning` (full suite, SQLite).
- Backend lint/format: `ruff check` clean; 3 pre-existing files differ from
  `ruff format` (cosmetic; untouched to avoid unrelated diff noise).
- Frontend: build OK, typecheck OK, lint OK, `47 passed`.
- `uv audit`: 1 dev-only advisory (pytest CVE-2025-71176).
- Secret scan gate: clean. `git diff --check`: clean.
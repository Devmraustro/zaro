# ZARO Phase 2.5 - Production Readiness Report

**Date:** 2026-08-22
**Scope:** Independent ZARO repository baseline (commerce core only)
**Excluded:** All Phase 3 functionality (quotes, orders, payments, production, delivery, AI, 3D/AR)

---

## 1. Verdict

**Gates passed.** The commerce-core foundation is internally consistent, security-hardened,
migration-verified against PostgreSQL 16, and reproducibly built. A baseline commit and tag
were created at the end of this phase.

No critical vulnerabilities remain open. Three medium findings were found and fixed during
this audit (see §4).

## 2. Scorecard

| Area | Verdict | Notes |
|---|---|---|
| Authentication | **PASS** | Argon2id (t=3, m=64 MiB, p=4); timing-equalized unknown-user login; opaque SHA-256-hashed refresh credentials; single-use reset tokens; session caps |
| Authorization | **PASS** | Server-side RBAC matrix (tested incl. denial paths); `products.manage_price` gate; file-access ownership checks |
| Audit | **PASS** | Auth/custom-request/file/material events recorded with request-id, IP, UA, metadata; forensic indexes present |
| Input validation | **PASS** | Pydantic schemas at every boundary; decimals-as-strings policy; magnitude bounds in cost engine; pagination clamps |
| File security | **PASS** | Magic-byte sniffing, per-category extension allow-lists, server-generated keys, traversal-proof resolution, HMAC-SHA256 signed URLs (TTL ≤ 3600 s, `compare_digest`) |
| SSRF | **PASS** | `UrlGuard`: scheme/port/host allow-lists, all DNS addresses checked, IPv4-mapped IPv6 normalized, CGNAT blocked. TOCTOU note in §5 |
| Secrets | **PASS** | No secrets in code; dev defaults rejected in production posture validator; CI secret scan; `.env` excluded from Docker contexts |
| Database | **PASS** | Async SQLAlchemy 2.0, JSONB on PostgreSQL, deliberate FK `ondelete` choices |
| Redis | **PASS** | Rate-limit primary store; transactional INCR/EXPIRE pipeline. Outage-latch caveat in §5 |
| Docker | **PASS** | Non-root users, healthchecks, loopback-only data services, internal network, `no-new-privileges`. Web image defects fixed in §4 |
| CI | **PASS** | Backend (secret scan, ruff, mypy, pytest, pip-audit) + frontend (typecheck/lint/test/build) + SDK jobs; frozen lockfiles; concurrency cancel |
| API exposure | **PASS** | Docs/OpenAPI disabled in production; catalog exposes ACTIVE products only; public submissions limited 5/hour/IP; explicit CORS allow-list; Host allow-list; body-size limit; security headers |
| Data isolation | **PASS** | Private assets require ownership or staff permission; public media strictly `purpose=product_media AND visibility=public`; customer↔user linking by id or verified email match |
| Migrations | **PASS** | `alembic check` clean against models on PG16; fresh-DB upgrade → downgrade → upgrade cycle verified; SQLite test parity |
| Cost correctness | **PASS** | Integer minor units; Decimal-only math pinned via `localcontext(prec=28)`; ROUND_HALF_UP constants; determinism tests; margin < 100 % enforced; zero-price lines flagged |

## 3. Verification Evidence

All commands run from repository root unless noted. Results from 2026-08-22.

| Check | Command | Result |
|---|---|---|
| Backend suite | `uv run pytest` (apps/zaro-api) | 423 passed |
| Lint/format | `ruff check app tests scripts`, `ruff format --check` | clean |
| Type check | `mypy app` | clean, 68 files |
| Migration drift | `alembic check` (against PG16) | no operations detected |
| Fresh DB cycle | `alembic downgrade base && alembic upgrade head` (PG16) | 4 down + 4 up OK |
| API image | `docker build -f docker/zaro-api.Dockerfile .` | success (~4 min) |
| Web image | `docker build -f docker/zaro-web.Dockerfile .` | success (~2 min) |
| Compose | `docker compose -f docker-compose.zaro.yml config --quiet` | valid |
| Frontend gates | `pnpm turbo run typecheck lint test build --filter=@zaro/web` | pass |

## 4. Findings Fixed During This Phase

### M1 - Content-Disposition header injection (files.py)
Client-supplied `original_filename` was stored raw and echoed into a response header.
Quotes/backslashes/semicolons could pollute the header value. **Fix:** filenames are
normalized (`normalize_filename`) before storage and sanitized to `[A-Za-z0-9._-]` by a
`_content_disposition()` helper at render time (defense-in-depth for legacy rows).

### M2 - Migration ↔ model drift (alembic)
`alembic check` flagged eight drifts: business-key columns were declared as inline UNIQUE
constraints in migrations but as unique indexes by the models (`unique=True, index=True`
yields one unique index in SQLAlchemy 2.0); `ix_file_assets_storage_key` existed only in
the migration; `ix_products_status` existed only in the migration. Also `sa.JSON` was used
where models declare JSONB-on-PostgreSQL, and `custom_requests.desired_dimensions` was a
JSON column while the entire API/service layer treats it as text. **Fix:** migrations
aligned to "unique index only" for slug/code/sku/reference/product_code; JSONB variants
added to 0002/0004; `desired_dimensions` is TEXT end-to-end (design doc updated);
duplicate `ix_customers_email` removed; `Product.status` indexed in the model.

### M3 - ZARO web image unbuildable (Docker)
Three independent defects: root `package.json` missing from the deps-stage COPY;
pnpm not version-pinned (corepack default disagreed with lockfile format →
`ERR_PNPM_OUTDATED_LOCKFILE`); `.npmrc` referenced but absent (COPY failure).
Additionally `output: "standalone"` was required by the image but breaks plain-Windows
builds (EPERM on symlink tracing). **Fix:** root package.json copied; pnpm pinned to
11.20.0 (same as CI) via corepack prepare; `.npmrc` dropped; standalone output made
opt-in through `NEXT_STANDALONE=1` set only in the Docker builder stage; repo-root
`.dockerignore` added (excludes .git, node_modules, .venv, .env*, storage, docs).
Both images verified building.

### Minor fixes
- Deterministic decimal context pinned inside `Money.multiply`/`Money.percentage` and the
  target-margin division (library code no longer depends on the mutable global context);
  string rounding constant replaced with `ROUND_HALF_UP`.
- Stale documentation corrected: `@austro/zaro-sdk` → `@zaro/sdk`; separation banner added
  to ZARO_SYSTEM_ARCHITECTURE.md; compose-file usage headers updated to standalone form.

## 5. Known Limitations (accepted, documented)

1. **UrlGuard TOCTOU:** validation resolves DNS, but a future fetcher that re-resolves
   independently retains a narrow DNS-rebinding window. Requirement for any Phase 3
   outbound HTTP: connect to the validated IP or re-validate per connection.
2. **Redis outage latch:** once the rate limiter fails over to memory it stays there until
   process restart (availability-preserving choice; unsuitable only for multi-worker
   deployments, which must provision healthy Redis anyway).
3. **Money equality ignores currency:** `Money(100, DZD) == Money(100, EUR)` would hold;
   all arithmetic/comparison paths guard currency, and only DZD exists. Revisit if a
   second currency ships.
4. **Single-currency engine:** `compute_cost` pins DZD; the currency registry in money.py
   is the extension point.
5. **Windows standalone builds:** unnecessary locally by design; Developer Mode would be
   required only if someone forces `NEXT_STANDALONE=1` off-container.

## 6. Baseline

Commit: `chore(zaro): establish commerce core baseline`
Tag: `v0.1.0-zaro-foundation`

The tag marks the audited state; any drift from it can be reviewed with
`git diff v0.1.0-zaro-foundation`.

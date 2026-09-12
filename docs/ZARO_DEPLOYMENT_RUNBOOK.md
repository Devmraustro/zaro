# ZARO Deployment Runbook

Production deployment path for the verified ZARO system. No product changes here —
this document records architecture decisions, required settings, and procedures.

Target architecture:

```
Browser → Vercel (apps/zaro-web, Next.js) → API base URL → FastAPI container
                                                              ↓
                                              PostgreSQL + Redis + S3 storage
```

## 1. Hosting decisions (do not improvise)

- **Frontend → Vercel.** The web app is a standard Next.js 15 build (`next build`,
  output `.next`). Root Directory must resolve `apps/zaro-web` with the pnpm
  workspace intact (the `@zaro/sdk` dependency is `workspace:*` and the lockfile
  lives at the repo root). If the dashboard Root Directory is `apps/zaro-web`,
  install must still run from the repo root so workspace links resolve; if it is
  the repo root, the build must target `@zaro/web` (e.g. `turbo run build
  --filter=@zaro/web` or a Vercel “Root Directory + framework preset” equivalent).
  The current production project already builds and serves pages, so keep the
  working directory scheme — only redeploy from a commit that contains
  `apps/zaro-web/postcss.config.mjs` (otherwise pages render unstyled).
- **Backend → persistent container host (NOT Vercel serverless).** The FastAPI app
  is designed around long-lived processes: lifespan-managed async DB engine and
  Redis client (`app/core/events.py`), transactional inventory/production flows
  with row locks, local-disk file storage by default, and a rate limiter whose
  in-memory fallback is explicitly unsuitable for multi-worker serverless
  (`app/core/rate_limit.py`). There is no ASGI-to-serverless adapter in the repo.
  Deploy `docker/zaro-api.Dockerfile` (uvicorn, unprivileged user, HEALTHCHECK on
  `/health/live`) to any container host (VPS, Render, Railway, Fly, ECS, …).
- **PostgreSQL → managed provider or the compose stack.** Never SQLite in
  production. Serverless-style hosts need a pooled connection (PgBouncer /
  Supavisor-style) because each instance opens its own async engine pool.
- **Redis → managed provider or the compose stack** (`redis:7`). Required for
  correct shared rate limiting; the app degrades to per-process memory only as
  a documented fallback.
- **File storage → S3-compatible object storage in production**
  (`ZARO_STORAGE_BACKEND=s3`). Local disk is ephemeral on hosted platforms and
  must only be used for development / single-node compose.

## 2. Required settings (names only — values live in platform secret stores)

### Vercel project (frontend)
- `NEXT_PUBLIC_API_BASE_URL` — public backend URL incl. `/api/v1`
  (e.g. `https://api.<domain>/api/v1`). Never `localhost` in production.
  Never put secrets in `NEXT_PUBLIC_*` variables.
- Node.js 22 (matches CI). Framework preset: Next.js.

### Backend environment (`ZARO_*` prefix)
- `ZARO_ENVIRONMENT=production`, `ZARO_DEBUG=false`
- `ZARO_DATABASE_URL` (asyncpg URL, credentials in secret store only)
- `ZARO_REDIS_URL`
- `ZARO_SECRET_KEY` (≥32 random chars; dev values are rejected at startup)
- `ZARO_ENCRYPTION_KEY` (Fernet key; required at startup)
- `ZARO_CORS_ORIGINS` — JSON array with exactly the production frontend
  origin(s), e.g. `["https://zaro-zaro-web.vercel.app"]`. Wildcards are
  rejected in production by config validation.
- `ZARO_COOKIE_SAMESITE` — REQUIRED in production (the posture gate rejects
  `lax`). Cross-site web/API (e.g. Vercel + Railway) **must** use `none`;
  single-domain deployments may use `strict`. `none` uses `Secure` cookies,
  which the production gate already enforces.
- `ZARO_ALLOWED_HOSTS` — backend host(s); rejects other Host headers (421).
- `ZARO_STORAGE_BACKEND=s3` + `ZARO_S3_ENDPOINT_URL`, `ZARO_S3_BUCKET`,
  `ZARO_S3_ACCESS_KEY`, `ZARO_S3_SECRET_KEY`, `ZARO_S3_REGION`.
- `ZARO_MAX_REQUEST_BYTES` — keep ≥ 6 MiB (above the 5 MiB upload ceiling).
- Rate limit: `ZARO_RATE_LIMIT_ENABLED=true`, `ZARO_RATE_LIMIT_REQUESTS`,
  `ZARO_RATE_LIMIT_WINDOW_SECONDS`.

Auth notes: refresh cookies are `Secure` in staging/production; JWT + RBAC are
unchanged by deployment. CORS must never be `["*"]` for these authenticated APIs.

## 3. Database migrations (controlled job, never app startup)

The API image does NOT migrate on boot. Run migrations as a separate one-shot
job against the target database with the same `ZARO_DATABASE_URL`:

```bash
cd apps/zaro-api
alembic current        # confirm starting revision
alembic upgrade head   # expected head: 0007
alembic current        # confirm head reached
```

Rules: verify the target is the intended database first; never drop/destroy;
never `docker compose down -v`; never recreate a database that holds data.
Downgrades are for disaster recovery only and must be explicit per revision.

## 4. Deploy sequence

1. Merge the verified Arena branch into the branch Vercel tracks (normally
   `main`) via pull request — normal merge, never force-push, never rewrite.
2. Vercel redeploys the frontend automatically from the merge commit. Confirm the
   deployment commit contains `apps/zaro-web/postcss.config.mjs`.
3. Deploy the backend container from the same merge commit; run the migration
   job (§3) before routing traffic if the schema changed.
4. Set/verify all §2 secrets on each platform before marking production live.

## 5. Post-deploy verification (minimum)

- Frontend: homepage / Shop / Custom Order render **styled** (compiled Tailwind
  utilities present in `/_next/static/css/*.css`); no console errors.
- Backend: `/health/live` (liveness) and `/api/v1/health` (readiness: DB + Redis
  both `up`); unknown routes 404 as JSON; validation errors 422 as JSON.
- Auth: login → access + Secure refresh cookie → RBAC denial for under-
  privileged roles → request IDs on responses → audit rows attributed.
- Smoke (non-destructive, dedicated test records only): catalog read, quote →
  order → deposit claim → proof upload → confirm/reject, stock read/reserve/
  release, production plan → reserve → start → consume → QC start/submit.
- Never run destructive financial/inventory operations against real data.

## 6. Observability

- Correlate via response `X-Request-ID`; JSON logs carry request IDs.
- `/api/v1/health` reports `degraded` with per-service `database`/`redis`
  status instead of crashing when a dependency is down.
- Logs must never contain passwords, tokens, payment secrets, or private keys
  (verified by audit; keep the secret scanner green in CI).

# ZARO — Phase 1.4 Security Review

**Date:** 2026-08-21
**Scope:** ZARO API (`apps/zaro-api`), ZARO Web (`apps/zaro-web`), Docker/Compose configuration, CI pipelines, environment templates, documentation.
**Method:** Manual inspection of every security-relevant component against the actual attack surface, followed by remediation and regression testing. No generic controls were added without a corresponding finding.

Severity scale:

| Severity      | Meaning                                                                    |
| ------------- | -------------------------------------------------------------------------- |
| CRITICAL      | Exploitable now; direct compromise of credentials, data, or infrastructure |
| HIGH          | Exploitable under realistic conditions; weakens a primary control          |
| MEDIUM        | Defense-in-depth gap or hardening opportunity with a concrete scenario     |
| LOW           | Minor weakness, hygiene issue, or documentation drift                      |
| INFORMATIONAL | Observation; no action required now                                        |

---

## Findings

### C1 — Reset tokens written to application logs — CRITICAL

- **Component:** `app/services/email.py` (`ConsoleEmailSender`)
- **Vulnerability:** The console email sender logs the full email body. Password-reset emails contain the raw single-use reset token, so every reset request writes a live credential to stdout/log aggregation.
- **Attack scenario:** Anyone with read access to container logs (ops tooling, log forwarding pipeline, shared dev machine) obtains a valid reset token before the user uses it and takes over the account.
- **Impact:** Account takeover.
- **Current mitigation:** None. Logs are structured but unrestricted.
- **Remediation:** Log delivery metadata only (recipient, subject); never the body. Enforced by a regression test that captures log output during a reset flow.
- **Status:** FIXED in Phase 1.4.

### H1 — Production configuration not validated at startup — HIGH

- **Component:** `app/core/config.py`
- **Vulnerability:** Only `secret_key=change-me-in-production` is rejected in production. Every other unsafe default (debug mode, wildcard CORS, non-Secure cookies, weak password policy, permissive limits) silently ships if misconfigured.
- **Attack scenario:** Operator deploys with `ZARO_DEBUG=true` or a wildcard CORS list copied from a dev template; verbose errors and cross-origin credentialed requests become possible.
- **Impact:** Multiple concurrent control failures from one misconfiguration.
- **Remediation:** A production gate validator that fails startup unless: debug off, explicit CORS origins (no `*`), strong secret key length, explicit encryption key, secure cookie posture, sane password minimums. Documented in the phase report.
- **Status:** FIXED.

### H2 — No request body size limit — HIGH

- **Component:** ASGI stack (`app/main.py`)
- **Vulnerability:** JSON bodies of unbounded size are parsed by Pydantic before any rejection. `PayloadTooLargeError` exists but nothing raises it.
- **Attack scenario:** A single multi-hundred-MB JSON POST exhausts memory/CPU on the single-container deployment.
- **Impact:** Denial of service; cost amplification.
- **Remediation:** Body-size middleware enforcing `ZARO_MAX_REQUEST_BYTES` (default 1 MiB, far above any legitimate auth/commerce JSON) returning 413 before parsing; oversized headers rejected by the server layer (documented).
- **Status:** FIXED.

### H3 — API container runs as root — HIGH

- **Component:** `docker/zaro-api.Dockerfile`
- **Vulnerability:** No `USER` directive; uvicorn runs as root inside the container. (`zaro-web.Dockerfile` already drops to `nextjs`.)
- **Attack scenario:** Any future RCE in the API yields root in the container, simplifying escape and tampering.
- **Impact:** Container privilege escalation path.
- **Remediation:** Dedicated non-root user, ownership of `/app`, `HEALTHCHECK`, documented tmpfs/volume needs for storage dir.
- **Status:** FIXED.

### H4 — ZARO has no CI coverage — HIGH

- **Component:** `.github/workflows/ci.yml`
- **Vulnerability:** The backend job runs `apps/api` (AUSTRO). No job runs ZARO ruff/mypy/pytest, builds ZARO images, or performs any security scanning. All Phase 1.3 gates were local-only.
- **Attack scenario:** A vulnerable or broken change merges because no automated gate exists.
- **Impact:** Silent regression of all security controls.
- **Remediation:** Add `zaro-backend` and `zaro-frontend` jobs plus secret-scanning, dependency-audit, and static-analysis steps as blocking gates.
- **Status:** FIXED.

### H5 — Datastore ports published publicly in Compose; Redis unauthenticated — HIGH

- **Component:** `docker-compose.zaro.yml`
- **Vulnerability:** Postgres (`5433`) and Redis (`6380`) are published on all host interfaces; Redis has no password; no network segmentation. The file reads as a production-ready template.
- **Attack scenario:** Deployment on a cloud VM with default security group exposes an unauthenticated Redis and a password-in-env Postgres to the internet.
- **Impact:** Full datastore compromise.
- **Remediation:** Loopback-only publishing for dev, dedicated Docker networks with only the API attached to datastores, optional Redis authentication wired through settings, production posture documented (datastores never leave the private network).
- **Status:** FIXED.

### H6 — Global rate limiting configured but not enforced — HIGH

- **Component:** `app/core/config.py` (`rate_limit_requests` unused), `app/main.py`
- **Vulnerability:** Only auth endpoints are limited. Every other endpoint (health, audit listing, future commerce) has no per-IP ceiling despite config keys existing since Phase 1.1.
- **Attack scenario:** Scripted hammering of expensive authenticated endpoints (audit search) starves legitimate users.
- **Impact:** Resource exhaustion; audit-log noise.
- **Remediation:** Global fixed-window IP limiter middleware reusing the existing RateLimiter (Redis-backed, memory fallback), exempting health endpoints and CORS preflight; disabled-by-default override available for tests.
- **Status:** FIXED.

### M1 — Security headers incomplete — MEDIUM

- **Component:** `app/api/middleware.py`, `apps/zaro-web`
- **Vulnerability:** API sends `nosniff`, `X-Frame-Options: DENY`, Referrer-Policy, Permissions-Policy but no HSTS and no CSP/frame-ancestors pair. Web sends none (only X-Powered-By removal).
- **Remediation:** HSTS in staging/production; CSP `default-src 'none'; frame-ancestors 'none'` on the JSON API; full nonce-based CSP + headers on Next.js via middleware and `next.config.ts`.
- **Status:** FIXED.

### M2 — CORS allows arbitrary request headers with credentials — MEDIUM

- **Component:** `app/main.py`
- **Vulnerability:** `allow_headers=["*"]` combined with `allow_credentials=True` reflects any requested header. Impact is limited (browser same-origin policy still applies to responses) but violates least privilege.
- **Remediation:** Explicit allow-list (`Content-Type`, `Authorization`, `X-Request-ID`, `X-CSRF-Token`).
- **Status:** FIXED.

### M3 — Client-supplied X-Request-ID trusted verbatim — MEDIUM

- **Component:** `app/api/middleware.py`
- **Vulnerability:** Arbitrary header content (length, control characters, spoofed correlation ids) is bound into every log line and echoed to responses.
- **Remediation:** Accept client ids only when they match a strict format (UUID or 8–64 URL-safe chars); otherwise generate a fresh id.
- **Status:** FIXED.

### M4 — Cookies not Secure outside production — MEDIUM

- **Component:** `app/core/config.py`, `endpoints/auth.py`
- **Vulnerability:** `cookie_secure_in_production_only=True` means staging deployments emit non-Secure refresh cookies over HTTPS.
- **Remediation:** Refresh/CSRF cookies are Secure in staging and production; only explicit opt-out (local HTTP development) disables it.
- **Status:** FIXED.

### M5 — Encryption key silently derived from JWT secret — MEDIUM

- **Component:** `app/core/security.py` (`_fernet`)
- **Vulnerability:** When `encryption_key` is empty, a Fernet key is derived from `secret_key`. Rotating the JWT secret then breaks encrypted-at-rest data, and one secret protects two domains.
- **Remediation:** Development convenience retained; production validation requires an explicit independent key. Documented in the secret inventory.
- **Status:** FIXED (validation + docs).

### M6 — No secret scanning, dependency audit, or static security analysis — MEDIUM

- **Component:** Repository tooling
- **Vulnerability:** Nothing detects committed credentials, known-vulnerable dependencies, or common Python security anti-patterns.
- **Remediation:** `scripts/check_secrets.py` (curated patterns, self-test, CI-blocking), `pip-audit` in CI, `bandit` high-severity gate. Small maintainable toolchain; documented false-positive handling.
- **Status:** FIXED.

### M7 — File security foundation absent — MEDIUM

- **Component:** Storage settings exist; no service
- **Vulnerability:** Future upload features would be built ad hoc; path traversal, MIME confusion, and public-bucket mistakes are likely without a vetted foundation.
- **Remediation:** `app/services/file_storage.py` foundation delivered now: random object keys, filename normalization, extension/content-signature validation, size limits, traversal-proof path resolution, HMAC-signed expiring access URLs, safe delete. No public feature yet, by design.
- **Status:** FIXED (foundation only).

### M8 — No SSRF guard for future outbound fetches — MEDIUM

- **Component:** New `app/core/url_guard.py`
- **Vulnerability:** ZARO will accept external URLs (inspiration links, webhooks). No utility existed to validate destinations.
- **Remediation:** Scheme allow-list, localhost/private/link-local/metadata-range blocking, resolution-aware checks, documented DNS-rebinding limits. No URL-fetching feature exists yet; module ships with tests only.
- **Status:** FIXED (foundation only).

### M9 — Host header not validated — MEDIUM

- **Component:** ASGI stack
- **Vulnerability:** The JSON API does not construct absolute URLs from Host today, so impact is low, but password-reset emails and future callbacks will.
- **Remediation:** Optional `allowed_hosts` enforcement middleware (empty = allow-all for dev; set in production template).
- **Status:** FIXED.

### M10 — Redis connection pool unbounded — MEDIUM

- **Component:** `app/db/redis.py`
- **Vulnerability:** Default pool grows without cap; combined with slow Redis this can pin API workers.
- **Remediation:** Bounded pool (`max_connections`), connect/retry timeouts, health-check interval; failure path already degrades to the in-memory limiter (Phase 1.3 fix retained and regression-tested).
- **Status:** FIXED.

### L1 — Error handler logs exception strings — LOW

- **Component:** `app/core/exceptions.py`
- **Risk:** `str(exc)` may contain internal detail in _logs_. Responses are already generic (`Internal server error`). Accepted: logs are the intended place for diagnostics. Verified no secrets pass through known paths.
- **Status:** ACCEPTED / monitored.

### L2 — Dev-only credentials in env templates — LOW

- **Component:** `.env.example`, compose defaults
- **Risk:** Placeholder passwords could be mistaken for real ones. They are clearly labelled development defaults and the secret scanner allowlists `*.example` files deliberately.
- **Status:** ACCEPTED / documented.

### L3 — python-magic requires system libmagic — LOW

- **Component:** `pyproject.toml`, Docker image
- **Risk:** Importing `magic` at runtime would fail in the slim image (no libmagic). The file foundation therefore uses explicit signature sniffing instead; dependency kept for future S3 work where libmagic will be installed explicitly.
- **Status:** DOCUMENTED.

### I1 — Git history clean — INFORMATIONAL

Single commit predates ZARO; all ZARO code is untracked working tree. No secrets in history. Secret scanning added to keep it that way.

### I2 — Documentation drift — INFORMATIONAL

Security architecture claimed bcrypt and "CSRF not applicable"; implementation is Argon2id with a cookie+CSRF double-submit flow. Both docs updated in this phase.

---

## Remediation summary

| ID     | Severity | Fix                                        | Regression test                                                   |
| ------ | -------- | ------------------------------------------ | ----------------------------------------------------------------- |
| C1     | CRITICAL | Email sender logs metadata only            | `tests/security/test_error_leaks.py::test_reset_token_not_logged` |
| H1     | HIGH     | Production settings gate                   | `tests/security/test_env_separation.py`                           |
| H2     | HIGH     | Body-size middleware                       | `tests/security/test_request_limits.py`                           |
| H3     | HIGH     | Non-root runtime user                      | Docker build validation step in CI                                |
| H4     | HIGH     | ZARO CI jobs + security gates              | Workflow itself                                                   |
| H5     | HIGH     | Network segmentation + loopback publishing | Compose review checklist in report                                |
| H6     | HIGH     | Global IP rate limiter                     | `tests/security/test_rate_limits.py`                              |
| M1–M10 | MEDIUM   | See above                                  | `tests/security/*`                                                |

## Explicitly reviewed and found sound (no change)

- Login failure genericity and timing equalization (Phase 1.3).
- Refresh rotation + reuse detection + family revocation.
- CSRF double-submit binding on cookie-sourced refreshes.
- Audit metadata sanitization incl. nested structures (adversarial tests extended).
- Trusted-proxy handling: `X-Forwarded-For` ignored unless peer is in `trusted_proxies`; spoofing tests added.
- Open redirect: API issues no redirects; negative test asserts no user-controlled `Location` ever emitted.
- SQL injection: SQLAlchemy-bound parameters only; like-input tests added.
- Mass assignment: `extra="forbid"` across schemas; protected-field tests added.

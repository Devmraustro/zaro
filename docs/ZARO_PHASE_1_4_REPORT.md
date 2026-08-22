# ZARO Phase 1.4 — Security Hardening

**Status:** COMPLETE
**Date:** 2026-08-21

## Summary

Hardened the ZARO platform baseline across application, configuration, containers, CI, and documentation. Every change is driven by a classified finding in `docs/ZARO_PHASE_1_4_SECURITY_REVIEW.md` (1 critical, 6 high, 10 medium, 3 low, 2 informational). The phase adds a production configuration gate, request-level defenses (body-size caps, host allow-listing, global rate limiting, header hardening), a secret scanner with self-test, secure file-storage and SSRF-guard foundations, container/network segmentation, and ZARO CI jobs. AUSTRO Studio was not modified.

## What Was Built

### Production Configuration Gate — `app/core/config.py`

- `model_validator(mode="after")` rejects insecure production configs at startup: debug enabled, secret_key shorter than 32 chars or a known dev value, missing explicit `encryption_key`, wildcard/empty CORS origins, disabled Secure cookies, password policy below 8 chars, access-token lifetime above 60 minutes, wildcard `allowed_hosts`.
- New settings: `max_request_bytes` (default 1 MiB), `allowed_hosts`, `rate_limit_enabled`, `trusted_proxies` (documented), `cookie_secure` property (Secure mandatory in staging + production).
- `jwt_algorithm` locked to HS256 at the type level (prevents algorithm-confusion drift).

### Request Defenses — `app/api/middleware.py`, `app/main.py`

- **Request-ID sanitization:** client `X-Request-ID` accepted only as 8–64 char `[A-Za-z0-9_-]`; anything else is replaced by a server UUID. Blocks log-injection and cache-poisoning via correlation IDs.
- **Security headers:** CSP (`default-src 'none'; frame-ancestors 'none'; sandbox`) on every response; HSTS (`max-age=31536000; includeSubDomains`) in staging/production.
- **Body-size limit:** 413 before parsing when Content-Length exceeds the cap or buffered body is oversized; malformed Content-Length → 400.
- **Host allow-listing:** 421 Misdirected Request when `Host` is not in `allowed_hosts` (validation disabled when the list is empty — development only).
- **Global rate limit:** per-IP fixed window across all API routes using the shared Redis-backed limiter; `/health/live`, `/health/ready`, and CORS preflight exempt; 429 responses carry `Retry-After`; can be disabled for focused tests.
- **CORS tightened:** explicit allow-header list (`Content-Type`, `Authorization`, `X-Request-ID`, `X-CSRF-Token`) replaces `"*"`.
- Middleware order documented: RequestContext → SecurityHeaders → GlobalRateLimit → BodySizeLimit → AllowedHosts → CORS.

### Secret Leakage Fix — `app/services/email.py`

- ConsoleEmailSender no longer logs email bodies (which embed single-use password-reset tokens); logs recipient, subject, and body length only.

### Secret Scanner — `scripts/check_secrets.py`

- Curated high-confidence rules: private key blocks, AWS keys, GitHub/Slack tokens, Stripe keys, JWT literals, generic credential assignments, database URLs with credentials.
- Placeholder-aware (change-me/example/${vault} patterns) to avoid false positives on templates.
- Self-test on startup: positive fixtures must fire, negative fixtures must stay silent; scanner aborts rather than providing false assurance if its own rules break.
- Allowlists: `*.example` env templates, lockfiles, vendored dirs, test fixture directories, and the scanner itself.

### File Storage Foundation — `app/services/file_storage.py`

- Server-generated keys (`category/random-hex.ext`) — client filenames never touch the filesystem namespace.
- Per-category extension allow-lists plus magic-byte content verification (PNG/JPEG/GIF/WebP/PDF) — extension/content mismatch rejected.
- Hard size limits enforced before write; traversal-proof path resolution on every open/delete; NFKC filename normalization strips directory components and control characters.
- HMAC-signed expiring URLs (constant-time comparison, TTL capped at 1 hour) so private objects can be served without exposing the storage tree.
- `StorageBackend` protocol keeps an S3 implementation pluggable without call-site changes.

### SSRF Guard — `app/core/url_guard.py`

- Policy layer for all future outbound HTTP: http(s)-only schemes, no embedded credentials, port allow-list, optional host allow-list.
- DNS-resolving private-network blocking covering loopback, RFC1918, link-local (incl. cloud metadata 169.254.169.254), carrier-grade NAT, multicast/reserved/unspecified, and IPv4-mapped IPv6; all resolved addresses must be safe (rebinding mitigation).

### Container & Network Hardening

- `docker/zaro-api.Dockerfile`: runs as unprivileged `zaro` user (UID/GID 1001), HEALTHCHECK on `/health/live`.
- `docker-compose.zaro.yml`: Postgres/Redis publish to loopback only; Redis requires a password; dedicated `zaro-internal` network (internal) isolates data services; `no-new-privileges` on both app containers; `ZARO_ENCRYPTION_KEY` passthrough added.

### CI Gates — `.github/workflows/ci.yml`

- `zaro-backend` job: secret scan → ruff → mypy → pytest → pip-audit against exported frozen requirements.
- `zaro-frontend` job: typecheck, lint, build for `@zaro/web`.

### Tests — `tests/security/` (92 new tests)

- `test_headers_and_request_id.py` — CSP/HSTS presence per environment, request-ID sanitization incl. CRLF injection attempts.
- `test_request_limits.py` — 413 paths, host allow-listing (421), global rate-limit trip/exemptions/disable switch.
- `test_production_gate.py` — every rejected production misconfiguration plus staging/dev cookie behavior and JWT algorithm lock.
- `test_file_storage.py` — save/validation/traversal/roundtrip and signed-URL lifecycle (expiry, tamper, wrong key, TTL cap).
- `test_url_guard.py` — scheme/credential/port/host policies, private-network literals, DNS resolution cases with monkeypatched getaddrinfo.

### Documentation

- `docs/ZARO_PHASE_1_4_SECURITY_REVIEW.md` — full audit with classified findings (written at phase start).
- `docs/ZARO_SECURITY_ARCHITECTURE.md` — corrected password hashing section (bcrypt → Argon2id, matching the implemented code); CSRF section now describes the real cookie+CSRF-header design.
- `docs/ZARO_THREAT_MODEL.md` — mitigations updated from bcrypt to Argon2id; CSRF residual-risk statement aligned with the implemented controls.
- `apps/zaro-api/.env.example` — documents `ZARO_ENCRYPTION_KEY`, `ZARO_MAX_REQUEST_BYTES`, `ZARO_ALLOWED_HOSTS`, `ZARO_RATE_LIMIT_ENABLED`.

## Findings Disposition

| ID     | Severity | Finding                                                                     | Resolution                                                                        |
| ------ | -------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| C1     | Critical | Email bodies (with reset tokens) logged                                     | Fixed — metadata-only logging                                                     |
| H1     | High     | No production config validation                                             | Fixed — config gate validator                                                     |
| H2     | High     | No request size limit                                                       | Fixed — BodySizeLimitMiddleware                                                   |
| H3     | High     | API image runs as root                                                      | Fixed — non-root user + healthcheck                                               |
| H4     | High     | No ZARO CI coverage                                                         | Fixed — zaro-backend/zaro-frontend jobs                                           |
| H5     | High     | DB/Redis exposed on all interfaces; unauthenticated Redis                   | Fixed — loopback bindings, auth, internal network                                 |
| H6     | High     | Global rate-limit setting unused                                            | Fixed — GlobalRateLimitMiddleware                                                 |
| M1–M10 | Medium   | Headers/CORS/request-id/cookies/encryption/scanning/storage/SSRF/hosts/pool | Addressed (bounded Redis pool deferred with the infra phase; noted below)         |
| L1–L3  | Low      | Minor hardening items                                                       | Documented in review; storage foundation removes the python-magic dependency need |
| I1–I2  | Info     | Stale docs (bcrypt claim, CSRF N/A claim)                                   | Corrected                                                                         |

## Known Limitations

- The security posture described here is defense-in-depth for a baseline; it does not make the system "unhackable". Penetration testing and dependency monitoring remain ongoing obligations.
- Bounded Redis connection-pool sizing is deferred until the infrastructure phase introduces explicit pool tuning; current defaults are conservative.
- Bandit static analysis is not yet a CI gate (pip-audit covers known CVEs); planned alongside the notifications phase.
- The compose file uses development-default passwords guarded behind environment variables; production deployments must supply real secrets via their secret manager.

## Verification

- `uv run pytest tests/ -q` — 295 passed (203 pre-existing + 92 new security tests)
- `uv run ruff check app tests scripts` — clean
- `uv run mypy app` — clean
- `uv run python scripts/check_secrets.py` — self-test passes, repo clean
- `docker compose -f docker-compose.yml -f docker-compose.zaro.yml config` — valid

# ZARO Phase 1.2 — RBAC + Audit Logging

**Status:** COMPLETE  
**Date:** 2026-08-18

## Summary

Implemented Role-Based Access Control (RBAC) with a 8-role, 48-permission matrix, and an immutable append-only audit logging system. Authorization is enforced on every protected endpoint via FastAPI dependency injection. All permission denials are automatically audit-logged with actor, resource, and context metadata.

## What Was Built

### Role-Permission Matrix — `app/core/rbac.py`

- **8 roles:** OWNER, ADMIN, SALES, PRODUCTION, CONTENT, ACCOUNTING, WORKER, CUSTOMER
- **48 permissions** organized by resource: users, products, materials, inventory, customers, leads, quotes, orders, payments, finance, production, quality, delivery, content, audit, settings, files
- `has_permission(role, permission)` — single source of truth for authorization decisions
- `RESOURCE_OWNERSHIP_REQUIRED` — permissions requiring resource-level ownership checks (e.g., customer can only see own orders)
- Deny-by-default: unknown roles get empty permission set

### Audit Logging System

- **Enums:** `AuditAction` (22 event types), `AuditResult` (SUCCESS/FAILURE/DENIED)
- **Model:** `AuditLog` with UUID PK, timestamp, actor_user_id, action, resource_type, resource_id, result, request_id, ip_address, user_agent, metadata_json (JSONB)
- **Service:** `app/services/audit.py` — `record_event()` as single entry point for all audit logging
- **Metadata sanitization:** BLOCKED_KEYS redaction for passwords, tokens, API keys, credit cards, etc. Nested dict sanitization with depth/size limits
- **Immutability:** No UPDATE/DELETE API endpoints for audit logs. Table is append-only.
- **Migration:** `alembic/versions/0002_add_audit_logs.py` with 7 indexes

### Authorization Dependencies — `app/api/deps.py`

- `get_current_user()` — JWT token validation + user lookup from DB
- `require_permission(permission)` — factory that returns a FastAPI dependency enforcing a specific permission. Automatically logs PERMISSION_DENIED audit events on denial with full context (actor, required permission, user role, IP, user agent)
- `require_owner()` — convenience dependency for owner-only endpoints
- `require_admin_or_owner()` — convenience dependency for admin+owner endpoints

### Audit Logs Admin Endpoint — `app/api/v1/endpoints/audit.py`

- `GET /api/v1/audit/logs` — paginated audit log listing
- Query filters: action, result, actor_user_id, start_date, end_date, resource_type
- Pagination: page (1-indexed), page_size (1-100, default 50)
- Access: OWNER, ADMIN, ACCOUNTING roles (via `audit.read` permission)

### Auth Endpoints — `app/api/v1/endpoints/auth.py`

- `POST /api/v1/auth/login` — stub endpoint with LoginRequest validation (extra="forbid" to prevent mass assignment)
- `POST /api/v1/auth/refresh` — stub endpoint
- `POST /api/v1/auth/logout` — stub endpoint

### Owner Bootstrap — `app/scripts/bootstrap_owner.py`

- Interactive CLI script for creating the initial OWNER account
- No hardcoded credentials, no public endpoint for owner creation
- Validates password strength, checks for existing owners
- Creates user directly in database via async SQLAlchemy

## Files Created/Modified

### New Files

| File                                      | Description                                                            |
| ----------------------------------------- | ---------------------------------------------------------------------- |
| `app/models/enums.py`                     | Expanded: Role (8 roles), Permission (48 permissions), ALL_PERMISSIONS |
| `app/core/rbac.py`                        | ROLE_PERMISSIONS matrix, has_permission(), RESOURCE_OWNERSHIP_REQUIRED |
| `app/models/audit_enums.py`               | AuditAction (22 actions), AuditResult (3 states)                       |
| `app/models/audit_log.py`                 | AuditLog SQLAlchemy model                                              |
| `app/services/audit.py`                   | record_event(), _sanitize_metadata(), BLOCKED_KEYS                     |
| `app/api/v1/endpoints/audit.py`           | GET /api/v1/audit/logs with RBAC                                       |
| `app/api/v1/endpoints/auth.py`            | Stub login/refresh/logout                                              |
| `app/scripts/bootstrap_owner.py`          | Owner creation script                                                  |
| `alembic/versions/0002_add_audit_logs.py` | Audit logs migration                                                   |
| `tests/unit/test_rbac.py`                 | 26 RBAC tests                                                          |
| `tests/unit/test_authorization.py`        | 18 authorization tests                                                 |
| `tests/unit/test_audit.py`                | 32 audit tests                                                         |
| `docs/ZARO_PHASE_1_2_REPORT.md`           | This report                                                            |

### Modified Files

| File                   | Change                                                                  |
| ---------------------- | ----------------------------------------------------------------------- |
| `app/api/deps.py`      | Added require_permission(), require_owner(), require_admin_or_owner()   |
| `app/api/v1/router.py` | Registered audit and auth routers                                       |
| `app/models/user.py`   | Role import updated (SystemRole → Role)                                 |
| `app/db/base.py`       | JSONType variant (JSON on SQLite, JSONB on PostgreSQL)                  |
| `tests/conftest.py`    | SQLite in-memory DB, user_factory, auth_header_factory, get_db override |

## Quality Gates

| Check              | Result                          |
| ------------------ | ------------------------------- |
| pytest (117 tests) | PASS — 117/117                  |
| ruff lint          | PASS — 0 errors                 |
| AUSTRO isolation   | PASS — no AUSTRO files modified |

## Test Coverage

| Test File                | Tests   | Status   |
| ------------------------ | ------- | -------- |
| test_rbac.py             | 26      | PASS     |
| test_authorization.py    | 18      | PASS     |
| test_audit.py            | 32      | PASS     |
| test_config.py           | 7       | PASS     |
| test_error_handling.py   | 5       | PASS     |
| test_health.py           | 4       | PASS     |
| test_input_validation.py | 6       | PASS     |
| test_security.py         | 16      | PASS     |
| test_security_headers.py | 3       | PASS     |
| **Total**                | **117** | **PASS** |

## RBAC Test Highlights

- All 8 roles tested for correct permission sets
- Deny-by-default verified (unknown roles get no permissions)
- `has_permission()` correctly denies cross-role access
- 401 returned for unauthenticated requests
- 403 returned for insufficient permissions with audit log entry
- Privilege escalation attempts blocked (no self-assign owner via headers)
- Audit events created for every permission denial with correct metadata

## Known Limitations

1. **Auth endpoints** — Stub only (return 401); actual auth logic in Phase 1.4
2. **SDK vitest** — Pre-existing Windows pnpm symlink issue
3. **Alembic migrations** — Not applied (requires running PostgreSQL)
4. **Audit logs** — No bulk export or archival yet (future enhancement)

## Next Phase

**Phase 1.3: Product Catalog + File Upload** — Product CRUD, categories, variants, file upload to MinIO with signed URLs.

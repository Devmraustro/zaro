# ZARO Threat Model

**Version:** 1.0  
**Status:** Phase 1 - Foundation  
**Last Updated:** 2026-08-18

---

## 1. Methodology

This threat model follows a **STRIDE-inspired** approach adapted for the ZARO platform. For each threat, we define:

- **Threat** — what could go wrong
- **Attack Surface** — where it can happen
- **Impact** — business consequence
- **Mitigation** — how we prevent it
- **Detection** — how we know it happened
- **Recovery** — how we respond

---

## 2. System Assets

| Asset            | Sensitivity | Description                         |
| ---------------- | ----------- | ----------------------------------- |
| User credentials | Critical    | Passwords, JWT tokens               |
| Payment data     | Critical    | Transaction claims, proof files     |
| Financial data   | High        | Prices, costs, revenue, expenses    |
| Customer PII     | High        | Names, emails, phones, addresses    |
| Business secrets | High        | Encryption keys, API keys, CCP info |
| Order data       | Medium      | Order details, status, history      |
| Product catalog  | Low         | Public product information          |
| Audit logs       | High        | Security event trail                |
| System config    | Medium      | Settings, business rules            |

---

## 3. Threat Analysis

### 3.1 Customer Account Compromise

| Field              | Value                                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Threat**         | Attacker gains access to customer account                                                                                                        |
| **Attack Surface** | Login endpoint, password reset, session management                                                                                               |
| **Impact**         | View other customer's orders (IDOR), submit fake payments, view sensitive order details                                                          |
| **Mitigation**     | Strong password hashing (Argon2id), JWT with expiry, refresh token rotation, server-side authorization on every request, customer data isolation |
| **Detection**      | Failed login monitoring, unusual access patterns, IP tracking in audit logs                                                                      |
| **Recovery**       | Account lockout, token blacklist, forced password reset, audit review                                                                            |

**Attack scenarios:**

1. Brute force login → Rate limit (5/min), account lockout after 10 failures
2. Credential stuffing → Rate limit, anomaly detection on login patterns
3. Token theft → Short expiry (30 min), refresh rotation, IP binding (V2)
4. Password reset exploit → If implemented, require email verification, time-limited tokens

### 3.2 Admin Account Compromise

| Field              | Value                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| **Threat**         | Attacker gains access to admin/owner account                                                                             |
| **Attack Surface** | Login, stolen credentials, social engineering                                                                            |
| **Impact**         | Full system access: confirm payments, change prices, access all data, delete records, modify permissions                 |
| **Mitigation**     | Strong unique passwords, 2FA (V2), IP allowlisting (V2), sensitive actions require re-authentication (V2), audit logging |
| **Detection**      | Login from unusual IP/location, sensitive action alerts, audit log anomalies                                             |
| **Recovery**       | Emergency account lockout, secret key rotation, audit review, incident response                                          |

**Priority: CRITICAL** — Owner account compromise is the highest-impact threat.

### 3.3 Brute Force Attack

| Field              | Value                                                                                                                                                                 |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Automated password guessing                                                                                                                                           |
| **Attack Surface** | `/api/v1/auth/login` endpoint                                                                                                                                         |
| **Impact**         | Account compromise, credential enumeration                                                                                                                            |
| **Mitigation**     | Rate limiting (5 requests/min per IP + 10 failures/15min per email), Argon2id (slow hashing), generic error messages ("Invalid credentials"), progressive delays (V2) |
| **Detection**      | High login failure rate, multiple IPs targeting same account                                                                                                          |
| **Recovery**       | IP blocking, account lockout, CAPTCHA (V2)                                                                                                                            |

### 3.4 Credential Stuffing

| Field              | Value                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| **Threat**         | Automated login with leaked credential databases                                                       |
| **Attack Surface** | `/api/v1/auth/login` endpoint                                                                          |
| **Impact**         | Mass account compromise                                                                                |
| **Mitigation**     | Rate limiting, Argon2id password hashing, breach detection services (V2), unique passwords per service |
| **Detection**      | Login attempts with known-breached passwords (V2), unusual login patterns                              |
| **Recovery**       | Forced password resets, account notifications                                                          |

### 3.5 SQL Injection

| Field              | Value                                                                                                                                           |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Malicious SQL in input fields                                                                                                                   |
| **Attack Surface** | Any API endpoint accepting user input                                                                                                           |
| **Impact**         | Data exfiltration, data modification, authentication bypass                                                                                     |
| **Mitigation**     | SQLAlchemy ORM (parameterized queries by default), Pydantic input validation, no raw SQL in business logic, parameterized queries in migrations |
| **Detection**      | WAF rules, database query monitoring, error pattern analysis                                                                                    |
| **Recovery**       | Database backup restoration, incident investigation                                                                                             |

**Residual risk:** LOW — SQLAlchemy ORM eliminates SQL injection by design.

### 3.6 Cross-Site Scripting (XSS)

| Field              | Value                                                                                                                  |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Malicious script injection via user input                                                                              |
| **Attack Surface** | Product descriptions, custom request descriptions, customer notes, any user-provided text                              |
| **Impact**         | Session hijacking, defacement, phishing                                                                                |
| **Mitigation**     | React automatic JSX escaping, JSON API responses (no HTML rendering), Content Security Policy headers, output encoding |
| **Detection**      | CSP violation reports, content scanning                                                                                |
| **Recovery**       | Content sanitization, CSP update                                                                                       |

**Residual risk:** LOW — React + JSON API eliminates most XSS vectors.

### 3.7 CSRF

| Field              | Value                                                                                                                                                                              |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Cross-site request forgery                                                                                                                                                         |
| **Attack Surface** | Any state-changing endpoint                                                                                                                                                        |
| **Impact**         | Unauthorized actions if user is authenticated                                                                                                                                      |
| **Mitigation**     | Access tokens in Authorization header (CSRF-immune); refresh cookie HttpOnly + SameSite=Lax + Path-scoped + X-CSRF-Token double-submit; Secure flag enforced in staging/production |
| **Detection**      | Unusual request origins, Referer/Origin header analysis                                                                                                                            |
| **Recovery**       | Token invalidation, session termination                                                                                                                                            |

**Residual risk:** LOW — header-based access tokens make CSRF non-applicable; the cookie refresh path is protected by SameSite=Lax plus a double-submit CSRF header.

### 3.8 IDOR/BOLA (Insecure Direct Object Reference)

| Field              | Value                                                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Accessing other users' resources by guessing IDs                                                                           |
| **Attack Surface** | Any endpoint with resource ID parameter                                                                                    |
| **Impact**         | Customer views other customer's orders/payments, worker accesses unauthorized data                                         |
| **Mitigation**     | UUID primary keys (non-guessable), server-side ownership check on every request, customer data isolation, RBAC enforcement |
| **Detection**      | Access pattern anomalies, cross-customer access attempts                                                                   |
| **Recovery**       | Access revocation, audit review                                                                                            |

**Critical test case:**

```
Customer A (uuid-a) tries to access:
GET /api/v1/orders/{order-of-customer-b}

Expected: 403 Forbidden
Enforcement: Backend checks order.customer_id == current_user.customer_id
```

### 3.9 SSRF (Server-Side Request Forgery)

| Field              | Value                                                                                                                 |
| ------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Malicious URLs causing server to make internal requests                                                               |
| **Attack Surface** | File upload URLs, webhook URLs, any URL input (V2)                                                                    |
| **Impact**         | Internal network scanning, cloud metadata access, internal service exploitation                                       |
| **Mitigation**     | No user-provided URLs in V1 (file uploads only, no URL fetching), URL validation whitelist (V2), network segmentation |
| **Detection**      | Internal network request logging, DNS rebinding detection                                                             |
| **Recovery**       | Network isolation, service restart                                                                                    |

**Residual risk:** LOW in V1 — no URL fetching from user input.

### 3.10 Malicious File Uploads

| Field              | Value                                                                                                                                                                   |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Uploading malicious files disguised as images/documents                                                                                                                 |
| **Attack Surface** | File upload endpoints                                                                                                                                                   |
| **Impact**         | Server compromise, stored XSS, path traversal                                                                                                                           |
| **Mitigation**     | File size limit (10MB), MIME type validation (magic bytes), extension whitelist, UUID-based filename storage, private storage, no execution path, content scanning (V2) |
| **Detection**      | File content analysis, upload pattern monitoring                                                                                                                        |
| **Recovery**       | File quarantine, storage cleanup, access review                                                                                                                         |

**Allowed types:** image/jpeg, image/png, image/webp, application/pdf
**Blocked:** .exe, .sh, .bat, .js, .html, .php, .py — any executable

### 3.11 Payment Manipulation

| Field              | Value                                                                                                                                                             |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Customer fakes payment confirmation or modifies payment details                                                                                                   |
| **Attack Surface** | Payment submission endpoint, payment status                                                                                                                       |
| **Impact**         | Financial loss, fake orders fulfilled                                                                                                                             |
| **Mitigation**     | Customer CANNOT set `status = confirmed`, server-side state machine, owner-only confirmation, manual verification workflow, proof file requirement, audit logging |
| **Detection**      | Payment verification process, amount mismatch detection, duplicate payment detection                                                                              |
| **Recovery**       | Payment reversal, order cancellation, blacklisting                                                                                                                |

**Critical invariant:**

```python
# Customer can ONLY:
# POST /api/v1/payments (submit)
# Result: status = "pending"

# Owner ONLY can:
# POST /api/v1/payments/{id}/confirm
# Result: status = "confirmed"
```

**Attack test:**

```json
// Customer sends:
PATCH /api/v1/payments/{id}
{ "status": "confirmed" }

// Expected: 403 Forbidden or 422 (field not allowed)
```

### 3.12 Privilege Escalation

| Field              | Value                                                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Low-privilege user gains higher privileges                                                                                    |
| **Attack Surface** | Role assignment, permission checking, user management                                                                         |
| **Impact**         | Worker gains admin access, customer gains worker access                                                                       |
| **Mitigation**     | RBAC enforced server-side, role changes require owner permission, no self-role-assignment, permission check on every endpoint |
| **Detection**      | Role change audit events, permission change alerts                                                                            |
| **Recovery**       | Role rollback, account review, access audit                                                                                   |

### 3.13 API Abuse

| Field              | Value                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| **Threat**         | Excessive or malicious API usage                                                                  |
| **Attack Surface** | All API endpoints                                                                                 |
| **Impact**         | Service degradation, resource exhaustion, data harvesting                                         |
| **Mitigation**     | Rate limiting, pagination limits, request size limits, input validation, API key requirement (V2) |
| **Detection**      | Request rate monitoring, unusual access patterns                                                  |
| **Recovery**       | IP blocking, account suspension, rate limit adjustment                                            |

### 3.14 Scraping

| Field              | Value                                                                |
| ------------------ | -------------------------------------------------------------------- |
| **Threat**         | Automated product catalog scraping                                   |
| **Attack Surface** | Public product listing endpoints                                     |
| **Impact**         | Competitive intelligence, price undercutting                         |
| **Mitigation**     | Rate limiting, pagination, response time limits, robots.txt (V2)     |
| **Detection**      | High request rate from single IP, sequential ID enumeration attempts |
| **Recovery**       | IP blocking, CAPTCHA (V2)                                            |

### 3.15 DDoS

| Field              | Value                                                                                                       |
| ------------------ | ----------------------------------------------------------------------------------------------------------- |
| **Threat**         | Distributed denial of service                                                                               |
| **Attack Surface** | All public endpoints                                                                                        |
| **Impact**         | Service unavailability                                                                                      |
| **Mitigation**     | Reverse proxy with rate limiting, CDN (V2), cloud DDoS protection (V2), connection limits, request timeouts |
| **Detection**      | Traffic spike monitoring, resource utilization alerts                                                       |
| **Recovery**       | Cloud provider DDoS mitigation, traffic filtering, scaling                                                  |

### 3.16 Data Leakage

| Field              | Value                                                                                                                                        |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Sensitive data exposed through errors, logs, or API responses                                                                                |
| **Attack Surface** | Error messages, logs, API responses, debug mode                                                                                              |
| **Impact**         | Privacy violation, security information disclosure                                                                                           |
| **Mitigation**     | Generic error messages in production, no sensitive data in logs, debug mode disabled in production, API response filtering, CORS restriction |
| **Detection**      | Error monitoring, log review, data access auditing                                                                                           |
| **Recovery**       | Incident response, data breach notification (if required)                                                                                    |

### 3.17 Compromised Dependencies

| Field              | Value                                                                                                                                        |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Malicious code in third-party packages                                                                                                       |
| **Attack Surface** | npm/pip dependencies                                                                                                                         |
| **Impact**         | Code execution, data exfiltration, backdoor                                                                                                  |
| **Mitigation**     | Pinned dependency versions, lock files, minimal dependencies, dependency auditing (`pip-audit`, `npm audit`), known vulnerability monitoring |
| **Detection**      | Automated dependency scanning in CI, vulnerability advisories                                                                                |
| **Recovery**       | Dependency replacement, code audit, rebuild                                                                                                  |

### 3.18 Stolen Secrets

| Field              | Value                                                                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Threat**         | Environment variables, keys, or credentials exposed                                                                                        |
| **Attack Surface** | `.env` files, Docker configs, source code, logs                                                                                            |
| **Impact**         | Full system compromise, data breach                                                                                                        |
| **Mitigation**     | `.env` in `.gitignore`, secrets not in source code, environment variable injection, Docker secret management (V2), key rotation capability |
| **Detection**      | Secret scanning in CI, leaked credential monitoring                                                                                        |
| **Recovery**       | Key rotation, credential revocation, incident review                                                                                       |

### 3.19 Database Compromise

| Field              | Value                                                                                                                                  |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Direct database access by attacker                                                                                                     |
| **Attack Surface** | Database port exposure, weak credentials, SQL injection                                                                                |
| **Impact**         | Full data exposure, data modification, data destruction                                                                                |
| **Mitigation**     | Database not exposed to internet, strong credentials, least privilege user, encrypted connections (V2), encrypted backups, audit trail |
| **Detection**      | Database access monitoring, unusual query patterns, backup integrity checks                                                            |
| **Recovery**       | Backup restoration, credential rotation, forensic analysis                                                                             |

### 3.20 Container Escape

| Field              | Value                                                                                                           |
| ------------------ | --------------------------------------------------------------------------------------------------------------- |
| **Threat**         | Attacker escapes Docker container                                                                               |
| **Attack Surface** | Docker configuration, kernel vulnerabilities                                                                    |
| **Impact**         | Host system compromise                                                                                          |
| **Mitigation**     | Non-root containers, read-only filesystem, no privileged mode, minimal images, regular updates, resource limits |
| **Detection**      | Container runtime monitoring, syscall auditing (V2)                                                             |
| **Recovery**       | Container restart, host investigation                                                                           |

---

## 4. Trust Boundaries

```
BOUNDARY 1: Internet → Reverse Proxy
  - TLS termination
  - Rate limiting
  - Request validation
  - IP filtering (V2)

BOUNDARY 2: Reverse Proxy → Application
  - Authentication check
  - CORS validation
  - Request size limits
  - Content type validation

BOUNDARY 3: Application → Database
  - Parameterized queries only
  - Connection pooling
  - Least privilege user
  - Encrypted connection (V2)

BOUNDARY 4: Application → Redis
  - Internal network only
  - No sensitive data stored
  - Connection authentication (V2)

BOUNDARY 5: Application → File Storage
  - Private bucket
  - Signed URL access
  - No public endpoints
  - File type validation

BOUNDARY 6: Customer → System
  - Can only access own data
  - Cannot modify system state directly
  - Cannot confirm payments
  - Cannot change prices

BOUNDARY 7: Worker → System
  - Can update production stages
  - Cannot access financial data
  - Cannot confirm payments
  - Cannot modify permissions
```

---

## 5. Security Testing Checklist

### 5.1 Authentication Tests

- [ ] Login with correct credentials → 200
- [ ] Login with wrong password → 401
- [ ] Login with non-existent email → 401 (same error as wrong password)
- [ ] Login rate limiting → 429 after 5 attempts
- [ ] Access with expired token → 401
- [ ] Access with invalid token → 401
- [ ] Refresh token rotation works
- [ ] Blacklisted refresh token → 401

### 5.2 Authorization Tests

- [ ] Customer cannot access other customer's orders → 403
- [ ] Customer cannot confirm payment → 403
- [ ] Customer cannot change prices → 403
- [ ] Worker cannot access financial reports → 403
- [ ] Worker cannot modify permissions → 403
- [ ] Unauthenticated access to protected endpoint → 401
- [ ] Admin cannot access owner-only endpoints → 403

### 5.3 Payment State Tests

- [ ] Customer cannot set payment status to "confirmed"
- [ ] Payment cannot skip states (e.g., pending → confirmed)
- [ ] Only owner can confirm payments
- [ ] Confirmed payment cannot be re-confirmed
- [ ] Refunded payment cannot be re-confirmed

### 5.4 Order State Tests

- [ ] Invalid state transition → 400
- [ ] Customer cannot change order status
- [ ] Worker cannot change order status to "completed" (only production stages)
- [ ] Cancelled order cannot be reactivated

### 5.5 Input Validation Tests

- [ ] SQL injection in search field → 400/422
- [ ] XSS in product description → Stored safely (escaped)
- [ ] Oversized file upload → 413
- [ ] Invalid file type upload → 415
- [ ] Missing required fields → 422
- [ ] Invalid UUID format → 422
- [ ] Negative price → 422

### 5.6 File Upload Tests

- [ ] Upload valid image → 201
- [ ] Upload .exe disguised as .jpg → 415
- [ ] Upload file > 10MB → 413
- [ ] Upload HTML file → 415
- [ ] File stored with UUID name (not original)
- [ ] Uploaded file not publicly accessible

### 5.7 IDOR Tests

- [ ] Access order with UUID of another customer → 403
- [ ] Access payment with UUID of another customer → 403
- [ ] Access quote with UUID of another customer → 403
- [ ] Enumerate order references → No data leakage

---

## 6. Security Monitoring

### 6.1 Events to Monitor

| Event                      | Severity | Response                |
| -------------------------- | -------- | ----------------------- |
| 10+ failed logins in 5 min | High     | Block IP, alert owner   |
| Payment confirmation       | High     | Audit log, notify owner |
| Role change                | Critical | Audit log, notify owner |
| Permission change          | Critical | Audit log, notify owner |
| Admin login from new IP    | Medium   | Audit log               |
| Large file upload          | Low      | Audit log               |
| Price change               | Medium   | Audit log               |
| Order cancellation         | Medium   | Audit log               |
| Unusual API rate           | Medium   | Rate limit, alert       |

### 6.2 Alerting (V2)

- Email alerts for critical security events
- SMS alerts for payment confirmations (V3)
- Dashboard security summary
- Weekly security report

---

## 7. Incident Response Plan

### 7.1 Severity Levels

| Level         | Description                             | Response Time |
| ------------- | --------------------------------------- | ------------- |
| P0 - Critical | Admin account compromise, data breach   | Immediate     |
| P1 - High     | Payment fraud, unauthorized access      | 1 hour        |
| P2 - Medium   | Suspicious activity, failed attacks     | 4 hours       |
| P3 - Low      | Vulnerability discovered, minor anomaly | 24 hours      |

### 7.2 Response Steps

1. **Contain** — Disable affected accounts, block IPs, revoke tokens
2. **Investigate** — Review audit logs, access patterns, affected data
3. **Remediate** — Patch vulnerability, rotate secrets, update passwords
4. **Recover** — Restore from backup if needed, verify system integrity
5. **Document** — Write incident report, update procedures, notify affected parties

### 7.3 Backup Recovery

```
Daily: Automated PostgreSQL dump (encrypted)
Weekly: Full backup verification
Monthly: Restore test to verify backup integrity

Recovery procedure:
1. Stop application
2. Restore database from backup
3. Verify data integrity
4. Rotate all secrets
5. Restart application
6. Notify users if data breach occurred
```

---

## 8. Compliance Considerations

### 8.1 Data Protection

- Customer PII stored securely
- Right to deletion (soft delete + eventual hard delete)
- Data minimization (collect only what's needed)
- Purpose limitation (use only for stated purpose)

### 8.2 Financial Records

- Audit trail for all financial transactions
- Immutable payment records
- Tax record retention (7 years recommended)
- Expense documentation

### 8.3 Future Requirements

- GDPR compliance (if serving EU customers)
- PCI DSS (if processing cards directly — avoid, use gateway)
- Local business regulations

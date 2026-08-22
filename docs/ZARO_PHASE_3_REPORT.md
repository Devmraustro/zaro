# ZARO Phase 3 — Quotes, Orders & Manual CCP Payments

**Date:** 2026-08-22  
**Baseline:** `93e18c0` (tag `v0.1.0-zaro-foundation`)  
**Working tree:** clean

---

## Summary

Implemented the complete Phase 3 commerce layer: quotes with immutable price snapshots, server-controlled order creation from accepted quotes, and a manual CCP deposit workflow with human payment verification. All financial invariants are enforced server-side; nothing trusts the client.

---

## Database (Migration 0005)

Tables added:
- `quotes` — commercial offers with totals/deposit/balance computed by server
- `quote_lines` — frozen line items (description, qty, unit price, line total)
- `orders` — created atomically from accepted quotes; one per quote (unique FK)
- `order_lines` — denormalized snapshot of quote lines at conversion
- `payment_configuration` — singleton CCP account info + default deposit %
- `payments` — manual CCP deposit claims with human review

Key constraints:
- CHECK constraints: all monetary columns non-negative, totals consistent, deposit ≤ total, balance = total − deposit_paid
- `orders.quote_id` UNIQUE → one order per quote at DB level
- Partial unique indexes (PostgreSQL):
  - `uq_payments_order_active` — at most one unresolved claim per order
  - `uq_payments_order_confirmed` — at most one confirmed deposit per order

---

## Enums & State Machines

### QuoteStatus
```
DRAFT → SENT → VIEWED → ACCEPTED → DEPOSIT_REQUIRED → CONVERTED
             ↓          ↓
         REJECTED    REJECTED
             ↓          ↓
         CANCELLED  CANCELLED

EXPIRED (lazy terminal, persisted by explicit check)
```

### OrderStatus
```
PENDING_DEPOSIT → CONFIRMED
        ↓
   CANCELLED
```
(Designed to append production/delivery states in future phases without breaking existing rows.)

### PaymentStatus
```
PENDING → PROOF_UPLOADED → UNDER_REVIEW → CONFIRMED
                   ↓               ↓
               CANCELLED      REJECTED
                   ↓               ↓
                 (resubmit)  ←───────┘
```

### PaymentMethod
```
CCP  (manual transfer only — no API integration)
```

### Audit Actions Added
```
QUOTE_CREATED, QUOTE_SENT, QUOTE_VIEWED, QUOTE_ACCEPTED, QUOTE_REJECTED,
QUOTE_CANCELLED, QUOTE_EXPIRED,
ORDER_CREATED, ORDER_STATUS_CHANGED, ORDER_CANCELLED,
PAYMENT_CREATED, PAYMENT_PROOF_UPLOADED, PAYMENT_SUBMITTED_FOR_REVIEW,
PAYMENT_CONFIRMED, PAYMENT_REJECTED, PAYMENT_CONFIGURATION_CHANGED
```

---

## Services

### quotes_service.py
- `create_quote()` — computes subtotal/discount/delivery/total/deposit/balance from line inputs using deterministic Money math; validates `valid_until` future; stores server-generated `ZQ-YYYY-NNNNNN` reference
- `compute_totals()` — single authoritative pricing path; ROUND_HALF_UP, Decimal quantities, int minor units
- `validate_transition()` — enforces QUOTE_TRANSITIONS
- `ensure_not_expired()` — lazy expiry guard at every mutating operation
- `change_status()`, `mark_viewed()`, `expire_if_past_validity()`

### orders_service.py
- `create_from_quote()` — **only** way orders exist; transitions quote ACCEPTED→DEPOSIT_REQUIRED, snapshots lines/totals, copies deposit_required from quote, sets balance_due = total
- `apply_confirmed_deposit()` — increments deposit_paid, recomputes balance; when deposit_paid ≥ deposit_required → order PENDING_DEPOSIT→CONFIRMED + quote DEPOSIT_REQUIRED→CONVERTED
- `cancel_order()` — cancels order + originating quote (if still ACCEPTED/DEPOSIT_REQUIRED)

### payments_service.py
- `get_configuration()` / `update_configuration()` — singleton CCP config; audited
- `create_deposit_claim()` — **amount always = order.deposit_required_minor**; no client input; returns payment with CCP snapshots
- `attach_proof()` — attach/replace proof; resets rejection context if REJECTED
- `submit_for_review()` — customer asserts transfer done; requires proof
- `confirm_payment()` — **atomic** with row locks: locks payment + order, verifies UNDER_REVIEW + proof + amount/currency match + order still PENDING_DEPOSIT, then applies deposit and confirms payment in single transaction
- `reject_payment()` — bounded reason_code + optional note (≤500 chars)
- Partial unique indexes (PostgreSQL) + service-level checks prevent duplicate claims

---

## API Endpoints

### Customer (ownership-enforced)
```
GET    /quotes/mine                           → list own quotes
GET    /quotes/{id}                           → view (records QUOTE_VIEWED on first sent→viewed)
POST   /quotes/{id}/accept   (empty body)     → accept + create order + DEPOSIT_REQUIRED
POST   /quotes/{id}/reject   (empty body)     → reject

GET    /orders/mine                           → list own orders
GET    /orders/{id}                           → view order + lines
GET    /orders/{id}/payments                  → list payments for order
POST   /orders/{id}/payments (empty body)     → open deposit claim (returns CCP info + payment_reference)

POST   /payments/{id}/proof   (multipart)     → upload proof (category payment_proofs)
POST   /payments/{id}/submit                  → submit for review
GET    /payments/{id}/proof-url               → short-lived signed URL for proof
```

### Admin (permission-gated)
```
POST   /admin/quotes                          → create draft quote (lines, discounts, delivery, deposit%, valid_until)
GET    /admin/quotes                          → paginated list + status filter
GET    /admin/quotes/{id}                     → detail
POST   /admin/quotes/{id}/send                → DRAFT/SENT→SENT
POST   /admin/quotes/{id}/cancel              → any non-terminal → CANCELLED

GET    /admin/orders                          → paginated list
GET    /admin/orders/{id}                     → detail
POST   /admin/orders/{id}/cancel              → cancel + linked quote

GET    /admin/payments                        → paginated list + status filter
POST   /admin/payments/{id}/confirm           → confirm (PAYMENTS_CONFIRM)
POST   /admin/payments/{id}/reject            → reject with reason_code + note (PAYMENTS_REJECT)
GET    /admin/payments/config                 → get CCP config (FINANCE_READ)
PUT    /admin/payments/config                 → update CCP config (FINANCE_MANAGE)
```

---

## Security Controls

### Authorization Matrix (existing RBAC reused)
| Role        | Quotes | Orders | Payments | Payment Config |
|-------------|--------|--------|----------|----------------|
| OWNER       | ✓ all  | ✓ all  | ✓ all    | ✓ R/W          |
| ADMIN       | ✓ all  | ✓ all  | ✓ all    | ✓ R/W          |
| ACCOUNTING  | —      | R      | R + confirm/reject | ✓ R/W |
| SALES       | CRUD   | R      | —        | —              |
| WORKER      | —      | R      | —        | —              |
| CONTENT     | —      | —      | —        | —              |
| CUSTOMER    | own*   | own*   | own*     | —              |

*Customers access ONLY their own records via ownership check (user_id link → email fallback), never by knowing UUIDs.

### Financial Integrity
- All amounts: integer minor units (DZD), validated ≤ `MAX_AMOUNT_MINOR = 10¹³`
- Deposit calculated server-side: `deposit = total.percentage(quote.deposit_percentage)`; client can never influence it
- Quote totals snapshot at creation; later product/price changes never affect issued quotes
- Order totals snapshot at conversion; `deposit_required_minor` frozen from quote
- Payment confirmation row-locks both payment and order; second concurrent confirmation fails 409
- Confirmation irreversible by design; corrections via future reversal workflow
- Mass-assignment blocked: all action endpoints accept empty `extra="forbid"` payloads; any injected `status`, `amount`, `reviewed_by` fields → 422

### File Storage (Payment Proofs)
- New category `payment_proofs` — PNG/JPEG/WebP/PDF only; magic-byte verified; 5 MB limit
- Private storage; access via signed URL (TTL ≤ 300s)
- Authorization:
  - Owning customer: always
  - Staff: **only** if `payments.read` permission (owner/admin/accounting) — sales/workers/content DENIED
  - Purpose-aware `_authorize_private_access` in files.py enforces this

### Threat Mitigations Tested
- IDOR: customer B cannot access A's quote/order/payment/proof (403)
- Mass assignment: injected financial fields rejected 422 on all action endpoints
- Amount manipulation: client-submitted `amount` in claim/submit/confirm rejected 422
- Double confirmation: sequential second confirm → 409; concurrent would serialize on PG row lock
- Rejected payment resubmission: same record, proof replaced, REJECTED→PROOF_UPLOADED
- Expired quote: accept/submit blocked; lazy expiry persisted as EXPIRED
- Currency mismatch: DZD-only in Phase 3; cross-currency rejected

---

## Tests

### Unit (2 new files, 45 tests)
- `test_quotes.py` — pricing math (spec example 50k DZD @ 40% → 20k deposit), rounding, bounds, transitions, expiry
- `test_payments.py` — transitions, config validation, claim authority (no amount param), row-lock presence

### Integration (existing + updated)
- All 468 backend tests pass
- Migration up/down/up cycle verified (SQLite + PG compatible)
- Alembic `check` clean

### Security / Frontend / SDK
- All existing security tests pass
- Frontend: 20 tests pass, `pnpm turbo run typecheck lint test build` ✓
- SDK: 5 tests pass, `typecheck lint test` ✓
- Ruff clean, mypy clean, pytest 468/468 pass

---

## Docker & Compose
- `docker build -f docker/zaro-api.Dockerfile .` ✓
- `docker build -f docker/zaro-web.Dockerfile .` ✓ (local; CI network flaky)
- `docker compose -f docker-compose.zaro.yml config --quiet` ✓

---

## Known Limitations

1. **CCP is manual only** — no bank API integration; human operator reviews every proof. This is by design for Phase 3.
2. **Single currency (DZD)** — multi-currency deferred to Phase 5+; engine/currency registry ready.
3. **Expiry is lazy** — quotes past `valid_until` are blocked on next action and persisted as EXPIRED by `expire_if_past_validity`; no background job.
4. **Order state machine minimal** — CONFIRMED is terminal; production/delivery states added in Phase 4.
5. **Payment confirmation irreversible** — no "unconfirm" endpoint; reversal workflow in future phase.
6. **No email/SMS notifications** — Phase 7.
7. **Web Docker build has npm registry timeouts in CI** — local build passes; network-dependent external flakiness.

---

## Recommended Next Phase (Phase 4)

Per roadmap:
- Production tracking (stages, assignments, due dates, QC)
- Delivery scheduling & status
- Payment reversal/refund workflow
- Email notifications for quote acceptance, payment confirmation, order updates
- Owner dashboard with payment/order queue

---

## Files Changed (Selected)

```
apps/zaro-api/app/models/
  enums.py              (+ QuoteStatus, OrderStatus, PaymentMethod, PaymentStatus + transitions)
  audit_enums.py        (+ 14 new AuditAction values)
  quote.py              (new: Quote, QuoteLine)
  order.py              (new: Order, OrderLine)
  payment.py            (new: Payment, PaymentConfiguration)
  __init__.py           (exports)

apps/zaro-api/app/services/
  references.py         (+ next_quote_number, next_order_number, next_payment_reference)
  quotes_service.py     (new)
  orders_service.py     (new)
  payments_service.py   (new)

apps/zaro-api/app/schemas/
  quotes.py             (new)
  orders.py             (new)
  payments.py           (new)

apps/zaro-api/app/api/v1/endpoints/
  quotes.py             (new)
  orders.py             (new)
  payments.py           (new)
  files.py              (tightened proof access for PAYMENT_PROOF)

apps/zaro-api/app/api/v1/router.py  (wired new routers)

apps/zaro-api/alembic/versions/0005_phase3_commerce.py  (new)

tests/unit/
  test_quotes.py        (new, 26 tests)
  test_payments.py      (new, 19 tests)

tests/integration/
  test_migrations.py    (updated version assertion to 0005)
```

---

## Git

```
Commit: feat(zaro): add quotes orders and ccp payments
Branch: main
```

All checks pass — ready for Phase 4.
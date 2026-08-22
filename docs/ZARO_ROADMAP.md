# ZARO Roadmap

**Version:** 1.0
**Status:** Phase 1.1 Complete
**Last Updated:** 2026-08-18

---

## Overview

ZARO will be built incrementally. Each phase produces a working, deployable system. No phase depends on unimplemented future phases.

**Core principle:** The system must be useful at every phase, even if that usefulness is limited.

---

## Phase 0: Foundation and Audit

**Status:** COMPLETE
**Duration:** 1 day

### Deliverables

- Full repository audit
- Existing codebase documentation
- System architecture document
- Security architecture document
- Database design document
- API design document
- Threat model document
- Development rules document
- Roadmap document

---

## Phase 1: Core Backend Infrastructure

**Status:** IN PROGRESS (1.1 complete)
**Estimated Duration:** 2-3 weeks
**Goal:** ZARO API serves product data and accepts custom requests

### 1.1 Project Setup

**Status:** COMPLETE

- Create `apps/zaro-api/` directory structure
- Python project with `pyproject.toml` (uv)
- FastAPI app factory with settings
- Database connection (async SQLAlchemy + asyncpg)
- Redis connection pool
- Alembic migration infrastructure
- Structured logging (structlog)
- Exception handlers
- Request context middleware
- Health check endpoint (`/healthz`, `/readyz`)
- Security headers middleware (CSP, HSTS, X-Frame-Options)
- CORS configuration
- User model with UUID PK, timestamps, soft delete
- Argon2id password hashing
- JWT access + refresh token system (JTI, expiry)
- Fernet encryption for secrets
- Production secret key validation
- Auth stub endpoints (login, refresh, logout)
- 41 foundation tests (config, security, health, validation, headers, error handling)
- Docker Compose with isolated ports (API 8001, PG 5433, Redis 6380, MinIO 9001)
- ZARO Web foundation (Next.js 15, Tailwind v4, design tokens)
- ZARO SDK foundation (TypeScript client library)
- 7 architecture documents
- Full AUSTRO isolation verified

### 1.2 Authentication

- User model (id, email, hashed_password, full_name, role, is_active) âœ“ (done in 1.1)
- Password hashing (Argon2id) âœ“ (done in 1.1)
- JWT access + refresh token system âœ“ (done in 1.1)
- Login endpoint (stub exists, implement DB lookup)
- Token refresh endpoint (stub exists, implement JTI blacklist check)
- Logout endpoint (stub exists, implement token blacklist)
- Current user dependency

### 1.3 RBAC

- System role enum (OWNER, ADMIN, WORKER, CUSTOMER)
- Permission constants
- Role-permission matrix
- `require_permission` dependency
- Owner-only dependency

### 1.4 Product Catalog

- Category model and CRUD
- Product model and CRUD
- Product variant model and CRUD
- Product slug generation
- Product listing with pagination/filtering
- Product detail by slug
- Admin product management endpoints
- Image upload for products

### 1.5 File Storage

- Storage abstraction (local + S3/MinIO)
- File upload endpoint with validation
- MIME type validation (magic bytes)
- File size limits
- UUID-based filename storage
- Signed URL generation for access
- File deletion

### 1.6 Audit Logging

- Audit log model
- Audit service (append-only)
- Auth event logging (login, logout, failed login)
- Product change logging
- Middleware for IP/user-agent capture

### 1.7 Docker

- ZARO API Dockerfile
- Docker Compose integration
- Development hot-reload
- Database migration on startup

### 1.8 Testing

- Test infrastructure (pytest, fixtures, test DB)
- Authentication tests
- Authorization tests (RBAC)
- Product CRUD tests
- File upload tests
- Audit logging tests

### Phase 1 Success Criteria

- `docker compose up` runs ZARO API + PostgreSQL + Redis + MinIO
- Owner can login and manage products via API
- Public endpoints return product data
- File uploads work with validation
- Audit trail captures auth events
- All tests pass

---

## Phase 2: Frontend Foundation

**Status:** PENDING
**Estimated Duration:** 2-3 weeks
**Goal:** Public-facing product catalog and admin panel shell

### 2.1 ZARO Web Setup

- Next.js 15 app with App Router
- Tailwind CSS with ZARO design tokens
- Brand fonts, colors, typography
- Responsive layout components
- API client (`@zaro/sdk`)

### 2.2 Public Pages

- Homepage with featured products
- Product listing page (grid, filters, pagination)
- Product detail page (images, dimensions, materials, price)
- Custom request page (form with file upload)
- About page
- Contact page

### 2.3 Admin Shell

- Admin layout with sidebar navigation
- Login page
- Dashboard shell
- Product management pages (list, create, edit)
- Authentication flow (JWT storage, refresh)

### 2.4 Design System

- ZARO color palette (Black, Ivory, Bronze, Graphite, Steel)
- Typography scale
- Button components (primary, secondary, ghost)
- Form components (input, textarea, select, checkbox)
- Card components
- Badge/status components
- Modal/dialog components
- Toast/notification components

### Phase 2 Success Criteria

- Public product catalog browsable on mobile and desktop
- Admin can login and manage products via UI
- Design system matches ZARO brand identity
- Mobile-first responsive design

---

## Phase 3: Custom Orders and Quotes

**Status:** PENDING
**Estimated Duration:** 2-3 weeks
**Goal:** Full custom request and quotation workflow

### 3.1 Custom Requests

- Custom request model and API
- Customer submission form
- File upload for inspiration images
- Admin review interface
- Status tracking

### 3.2 Quotation System

- Quote model and API
- Quote creation (admin)
- Line items with pricing
- Quote PDF generation (V2)
- Customer quote view
- Quote approval/rejection workflow
- Quote expiry handling

### 3.3 Design Revision

- Design revision model and API
- Versioned specifications
- Customer approval workflow
- Approval state machine
- Immutability after approval

### 3.4 Order Management

- Order model and state machine
- Order creation from quotes
- Order status transitions
- Admin order management
- Customer order tracking
- Order reference generation

### Phase 3 Success Criteria

- Customer can submit custom request
- Owner can create and send quote
- Customer can approve quote
- Design revision workflow works
- Order state machine enforced

---

## Phase 4: Payments and Production

**Status:** PENDING
**Estimated Duration:** 2-3 weeks
**Goal:** Payment verification and production tracking

### 4.1 Manual Payment System

- Payment model and state machine
- CCP information display
- Payment submission form
- Proof file upload
- Owner review interface
- Payment confirmation/rejection
- Audit trail for all payment events

### 4.2 Production Tracking

- Production order model
- Production stage tracking (cutting, welding, grinding, painting, assembly, QC, packaging)
- Stage status updates
- Assignment to workers
- Priority management
- Due date tracking
- Quality check recording

### 4.3 Delivery

- Delivery model and API
- Delivery scheduling
- Status tracking
- Customer notification (V2: email/SMS)

### Phase 4 Success Criteria

- Full payment workflow from submission to confirmation
- Production tracking with stage updates
- Delivery scheduling works
- Financial audit trail complete

---

## Phase 5: Materials, Inventory, and Costing

**Status:** PENDING
**Estimated Duration:** 2 weeks
**Goal:** Material management and cost calculation

### 5.1 Materials

- Material model and CRUD
- Material price history
- Supplier tracking
- Price change audit

### 5.2 Inventory

- Stock level tracking
- Stock movement recording
- Low stock alerts
- Material usage tracking per production order

### 5.3 Cost Calculation

- Product cost calculation engine
- Material cost per product
- Labor cost configuration
- Overhead allocation
- Margin/markup calculation
- Profit per product
- Profit per order

### Phase 5 Success Criteria

- Materials managed with price history
- Inventory levels tracked
- Stock alerts working
- Product costs calculated automatically
- Profit margins visible in admin

---

## Phase 6: Dashboard, Expenses, and Reporting

**Status:** PENDING
**Estimated Duration:** 2 weeks
**Goal:** Business intelligence and financial overview

### 6.1 Admin Dashboard

- Revenue summary (daily, weekly, monthly, yearly)
- Order statistics
- Production queue overview
- Recent activity feed
- Low stock alerts
- Pending payments
- Pending quotes

### 6.2 Expense Tracking

- Expense model and CRUD
- Category-based tracking
- Receipt file upload
- Expense reports by period
- Expense vs revenue comparison

### 6.3 Audit Dashboard

- Audit log viewer (owner only)
- Filterable by event type, user, date
- Export capability (V2)

### Phase 6 Success Criteria

- Dashboard shows real business metrics
- Expenses tracked against revenue
- Audit log fully searchable
- Owner has business overview

---

## Phase 7: Email Notifications

**Status:** PENDING
**Estimated Duration:** 1 week
**Goal:** Automated email notifications for key events

### 7.1 Email System

- Email service abstraction
- Template system
- Order confirmation emails
- Payment confirmation emails
- Quote sent/approved emails
- Production stage update emails
- Delivery notification emails

### Phase 7 Success Criteria

- Customers receive order confirmations
- Payment confirmations sent automatically
- Quote notifications working

---

## Phase 8: Hardening and Launch

**Status:** PENDING
**Estimated Duration:** 2 weeks
**Goal:** Production-ready deployment

### 8.1 Security Hardening

- Security audit against threat model
- Penetration testing
- Rate limit tuning
- CORS verification
- HTTPS enforcement
- Security headers
- CSP configuration

### 8.2 Performance

- Database query optimization
- N+1 query elimination
- Pagination optimization
- Image optimization
- Caching strategy
- Static asset CDN (V2)

### 8.3 Operations

- Automated backups with verification
- Monitoring setup
- Error tracking (Sentry or similar)
- Log aggregation
- Uptime monitoring
- SSL certificate automation

### 8.4 Documentation

- API documentation review
- Deployment guide
- Operations runbook
- Backup/restore procedures
- User guide for admin panel

### Phase 8 Success Criteria

- All security tests pass
- Performance benchmarks met
- Backups verified with restore test
- Monitoring active
- Documentation complete
- Ready for production traffic

---

## Phase 9: Future Enhancements (V2+)

**Status:** FUTURE
**Not planned for immediate implementation**

### 9.1 Payment Gateway Integration

- Stripe/other gateway integration
- Online card payments
- Automated payment confirmation
- Refund processing

### 9.2 Email Marketing

- Customer email list
- Newsletter system
- Promotional campaigns
- Product launch announcements

### 9.3 Multi-Language

- Arabic support
- French support
- RTL layout support

### 9.4 Mobile App

- React Native or Flutter app
- Push notifications
- Order tracking
- Photo upload

### 9.5 Advanced Analytics

- Sales analytics
- Customer analytics
- Product performance
- Revenue forecasting
- Trend analysis

### 9.6 AI Features

- AI-powered pricing suggestions
- AI design assistance
- Automated content generation
- Chatbot customer support
- Inventory prediction

### 9.7 Social Media Integration

- Instagram product sync
- Facebook shop
- Content scheduling
- Social analytics

---

## Timeline Summary

| Phase   | Focus                    | Duration  | Cumulative  |
| ------- | ------------------------ | --------- | ----------- |
| Phase 0 | Audit and planning       | 1 day     | 1 day       |
| Phase 1 | Backend core             | 2-3 weeks | 3-4 weeks   |
| Phase 2 | Frontend foundation      | 2-3 weeks | 5-7 weeks   |
| Phase 3 | Custom orders and quotes | 2-3 weeks | 7-10 weeks  |
| Phase 4 | Payments and production  | 2-3 weeks | 9-13 weeks  |
| Phase 5 | Materials and inventory  | 2 weeks   | 11-15 weeks |
| Phase 6 | Dashboard and reporting  | 2 weeks   | 13-17 weeks |
| Phase 7 | Email notifications      | 1 week    | 14-18 weeks |
| Phase 8 | Hardening and launch     | 2 weeks   | 16-20 weeks |

**Estimated total to launch: 16-20 weeks (4-5 months)**

---

## Milestones

1. **M1:** Backend API running with auth and products (Phase 1)
2. **M2:** Public catalog browsable (Phase 2)
3. **M3:** First custom order processed end-to-end (Phase 3)
4. **M4:** First payment verified and production tracked (Phase 4)
5. **M5:** Inventory and costing functional (Phase 5)
6. **M6:** Dashboard and financial overview (Phase 6)
7. **M7:** Email notifications working (Phase 7)
8. **M8:** Production launch (Phase 8)

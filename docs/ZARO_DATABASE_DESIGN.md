# ZARO Database Design

**Version:** 1.0  
**Status:** Phase 1 - Foundation  
**Last Updated:** 2026-08-18

---

## 1. Design Principles

1. **Normalized relational design** — no giant "everything" tables
2. **UUID primary keys** — non-sequential, secure public identifiers
3. **Timestamps on everything** — `created_at`, `updated_at`
4. **Soft delete where appropriate** — never hard-delete customers, orders
5. **Audit trail** — append-only log of sensitive actions
6. **Referential integrity** — foreign keys with appropriate cascade rules
7. **JSONB for flexible data** — materials list, custom specifications
8. **Index strategy** — index all foreign keys, common query patterns
9. **No business logic in database** — state machines enforced in application code

---

## 2. Entity Relationship Overview

```
┌─────────┐    ┌──────────────┐    ┌───────────┐
│  users   │───│  customers   │───│   orders   │
└─────────┘    └──────────────┘    └───────────┘
     │                                    │
     │                               ┌────┴─────┐
     │                               │ order_items│
     │                               └──────────┘
     │                                    │
┌─────────┐    ┌──────────────┐    ┌────┴─────┐
│  roles   │    │  products    │───│  quotes   │
└─────────┘    └──────────────┘    └──────────┘
                    │                    │
               ┌────┴─────┐        ┌────┴──────────┐
               │ product_  │        │ design_revisions│
               │ variants  │        └───────────────┘
               └──────────┘

┌──────────┐    ┌──────────────┐    ┌───────────┐
│materials │───│  inventory   │───│ inventory_ │
└──────────┘    └──────────────┘    │ movements  │
                                   └───────────┘

┌──────────────┐    ┌───────────────┐
│custom_requests│───│custom_request_│
└──────────────┘    │   images      │
                    └───────────────┘

┌──────────────┐    ┌───────────────┐
│  payments    │    │ audit_logs    │
└──────────────┘    └───────────────┘

┌──────────────────┐    ┌─────────────────┐
│production_orders │───│production_stages │
└──────────────────┘    └─────────────────┘

┌──────────┐    ┌──────────┐    ┌──────────┐
│expenses  │    │ deliveries│    │settings  │
└──────────┘    └──────────┘    └──────────┘
```

---

## 3. Tables

### 3.1 users

Internal system users (owner, admin, worker).

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    role VARCHAR(20) NOT NULL DEFAULT 'worker',
    -- role: owner, admin, worker
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_email ON users(email);
```

**Notes:**

- `role` is system-wide (not per-workspace) because ZARO is single-workspace
- `hashed_password` — bcrypt, never plaintext
- Soft delete via `is_active = false`

### 3.2 customers

External customers (who browse and buy).

```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE,
    phone VARCHAR(20),
    full_name VARCHAR(200) NOT NULL,
    company_name VARCHAR(200),
    address TEXT,
    city VARCHAR(100),
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_customers_email ON customers(email);
CREATE INDEX ix_customers_phone ON customers(phone);
```

**Notes:**

- Customers may not have an account (phone orders, Instagram inquiries)
- `email` is nullable (some customers only provide phone)
- Customers can be linked to user accounts later (V2)

### 3.3 categories

Product categories.

```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(120) UNIQUE NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Examples:** Coffee Tables, Dining Tables, Chairs, Shelves, Custom Metalwork

### 3.4 products

Ready-made products.

```sql
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(220) UNIQUE NOT NULL,
    product_code VARCHAR(20) UNIQUE NOT NULL,  -- e.g., ZAR-ATL-001
    description TEXT,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,

    -- Physical specifications
    dimensions JSONB,  -- { width: 120, height: 45, depth: 60, unit: "cm" }
    materials JSONB,    -- [{ name: "Steel", grade: "Q235" }, { name: "Oak", finish: "natural" }]
    weight_kg DECIMAL(8,2),

    -- Pricing
    base_cost DECIMAL(12,2),      -- Calculated from cost engine
    selling_price DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'DZD',

    -- Media
    thumbnail_url TEXT,
    images JSONB,  -- [{ url: "...", alt: "...", sort: 0 }]
    videos JSONB,  -- [{ url: "...", type: "mp4", duration: 30 }]

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft, active, archived
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,

    -- Production
    production_time_days INTEGER,  -- Estimated days to produce
    stock_status VARCHAR(20) NOT NULL DEFAULT 'in_stock',  -- in_stock, made_to_order, out_of_stock

    -- Delivery
    delivery_info TEXT,
    delivery_available BOOLEAN NOT NULL DEFAULT TRUE,

    -- SEO
    meta_title VARCHAR(200),
    meta_description VARCHAR(500),

    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_products_category ON products(category_id);
CREATE INDEX ix_products_status ON products(status);
CREATE INDEX ix_products_slug ON products(slug);
CREATE INDEX ix_products_code ON products(product_code);
```

### 3.5 product_variants

Size/color/material variants of a product.

```sql
CREATE TABLE product_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    sku VARCHAR(50) UNIQUE,
    attributes JSONB NOT NULL,  -- { color: "matte black", size: "large", finish: "powder coated" }
    price_adjustment DECIMAL(12,2) NOT NULL DEFAULT 0,  -- Added to base price
    stock_status VARCHAR(20) NOT NULL DEFAULT 'in_stock',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_product_variants_product ON product_variants(product_id);
```

### 3.6 materials

Raw materials used in production.

```sql
CREATE TABLE materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,  -- steel, wood, paint, hardware, consumable, other
    unit VARCHAR(20) NOT NULL,       -- kg, m, m2, m3, liter, piece
    current_cost DECIMAL(12,4) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'DZD',
    supplier VARCHAR(200),
    supplier_contact TEXT,
    min_stock_level DECIMAL(10,2),  -- Minimum stock threshold
    current_stock DECIMAL(10,2) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_materials_category ON materials(category);
```

### 3.7 material_prices

Historical material prices (for cost tracking).

```sql
CREATE TABLE material_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id UUID NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    cost DECIMAL(12,4) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'DZD',
    effective_date DATE NOT NULL,
    notes TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_material_prices_material ON material_prices(material_id);
CREATE INDEX ix_material_prices_date ON material_prices(effective_date);
```

### 3.8 inventory_movements

Stock movement tracking.

```sql
CREATE TABLE inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id UUID NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    movement_type VARCHAR(20) NOT NULL,  -- purchase, usage, adjustment, waste, return
    quantity DECIMAL(10,2) NOT NULL,      -- Positive = in, Negative = out
    unit_cost DECIMAL(12,4),
    reference_type VARCHAR(50),           -- 'production_order', 'purchase', 'adjustment'
    reference_id UUID,
    notes TEXT,
    performed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_inventory_movements_material ON inventory_movements(material_id);
CREATE INDEX ix_inventory_movements_date ON inventory_movements(created_at);
```

### 3.9 custom_requests

Customer custom order requests.

```sql
CREATE TABLE custom_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference VARCHAR(20) UNIQUE NOT NULL,  -- e.g., CR-2026-0001

    -- Customer info (denormalized for snapshots)
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    customer_name VARCHAR(200) NOT NULL,
    customer_email VARCHAR(320),
    customer_phone VARCHAR(20),

    -- Request details
    category VARCHAR(50),              -- coffee_table, dining_table, chair, shelf, other
    description TEXT NOT NULL,
    desired_dimensions JSONB,          -- { width: 180, height: 75, depth: 90, unit: "cm" }
    materials TEXT,
    colors TEXT,
    finish TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    budget_min DECIMAL(12,2),
    budget_max DECIMAL(12,2),
    notes TEXT,

    -- Inspiration images
    images JSONB,  -- [{ url: "...", filename: "..." }]

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    -- new, reviewing, quoted, accepted, rejected, expired

    -- Source tracking
    source VARCHAR(50) DEFAULT 'website',  -- website, instagram, phone, walk_in

    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_custom_requests_status ON custom_requests(status);
CREATE INDEX ix_custom_requests_customer ON custom_requests(customer_id);
```

### 3.10 quotes

Quotations for custom requests.

```sql
CREATE TABLE quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference VARCHAR(20) UNIQUE NOT NULL,  -- e.g., QT-2026-0001
    custom_request_id UUID REFERENCES custom_requests(id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,

    -- Pricing
    subtotal DECIMAL(12,2) NOT NULL,
    discount DECIMAL(12,2) NOT NULL DEFAULT 0,
    tax_rate DECIMAL(5,2) NOT NULL DEFAULT 0,
    tax_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    total DECIMAL(12,2) NOT NULL,
    deposit_percentage DECIMAL(5,2) NOT NULL DEFAULT 50,
    deposit_amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'DZD',

    -- Terms
    validity_days INTEGER NOT NULL DEFAULT 14,
    payment_terms TEXT,
    delivery_estimate TEXT,
    notes TEXT,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft, sent, viewed, accepted, rejected, expired, cancelled

    -- Timestamps
    sent_at TIMESTAMPTZ,
    viewed_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_quotes_status ON quotes(status);
CREATE INDEX ix_quotes_customer ON quotes(customer_id);
CREATE INDEX ix_quotes_custom_request ON quotes(custom_request_id);
```

### 3.11 quote_items

Individual line items in a quote.

```sql
CREATE TABLE quote_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    description VARCHAR(500) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
    unit VARCHAR(20) NOT NULL DEFAULT 'piece',
    unit_price DECIMAL(12,2) NOT NULL,
    total_price DECIMAL(12,2) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_quote_items_quote ON quote_items(quote_id);
```

### 3.12 design_revisions

Versioned design specifications for custom orders.

```sql
CREATE TABLE design_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    custom_request_id UUID NOT NULL REFERENCES custom_requests(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL DEFAULT 1,

    -- Specifications
    title VARCHAR(200),
    dimensions JSONB,          -- { width: 180, height: 75, depth: 90, unit: "cm" }
    materials JSONB,           -- [{ name: "Steel Tube 30x30", finish: "matte black" }]
    colors TEXT,
    finish TEXT,
    production_notes TEXT,

    -- Pricing
    estimated_cost DECIMAL(12,2),
    quoted_price DECIMAL(12,2),

    -- Design files
    files JSONB,  -- [{ url: "...", type: "3d_model"|"drawing"|"render", version: 1 }]

    -- Approval
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft, submitted, approved, rejected

    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    customer_approved_at TIMESTAMPTZ,

    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(custom_request_id, revision_number)
);

CREATE INDEX ix_design_revisions_request ON design_revisions(custom_request_id);
```

### 3.13 orders

Customer orders (ready-made or custom).

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference VARCHAR(20) UNIQUE NOT NULL,  -- e.g., OR-2026-0001

    -- Customer
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    customer_name VARCHAR(200) NOT NULL,
    customer_email VARCHAR(320),
    customer_phone VARCHAR(20),

    -- Type
    order_type VARCHAR(20) NOT NULL,  -- ready_made, custom

    -- Custom order link
    custom_request_id UUID REFERENCES custom_requests(id) ON DELETE SET NULL,
    quote_id UUID REFERENCES quotes(id) ON DELETE SET NULL,
    design_revision_id UUID REFERENCES design_revisions(id) ON DELETE SET NULL,

    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    -- draft, quoted, customer_approved, deposit_pending, payment_review,
    -- confirmed, production, quality_control, ready, delivery, completed, cancelled

    -- Pricing
    subtotal DECIMAL(12,2) NOT NULL,
    discount DECIMAL(12,2) NOT NULL DEFAULT 0,
    tax_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    total DECIMAL(12,2) NOT NULL,
    deposit_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    amount_paid DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'DZD',

    -- Shipping
    shipping_address TEXT,
    shipping_city VARCHAR(100),
    shipping_notes TEXT,
    delivery_fee DECIMAL(12,2) NOT NULL DEFAULT 0,

    -- Notes
    customer_notes TEXT,
    internal_notes TEXT,

    -- Timestamps for state machine
    confirmed_at TIMESTAMPTZ,
    production_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,

    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_orders_status ON orders(status);
CREATE INDEX ix_orders_customer ON orders(customer_id);
CREATE INDEX ix_orders_type ON orders(order_type);
CREATE INDEX ix_orders_reference ON orders(reference);
```

### 3.14 order_items

Individual items in an order.

```sql
CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    product_variant_id UUID REFERENCES product_variants(id) ON DELETE SET NULL,

    -- Denormalized (snapshot at time of order)
    product_name VARCHAR(200) NOT NULL,
    variant_name VARCHAR(200),
    product_code VARCHAR(20),

    quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
    unit_price DECIMAL(12,2) NOT NULL,
    total_price DECIMAL(12,2) NOT NULL,

    -- Custom item details (if no product reference)
    custom_description TEXT,
    custom_specifications JSONB,

    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_order_items_order ON order_items(order_id);
CREATE INDEX ix_order_items_product ON order_items(product_id);
```

### 3.15 payments

Payment records (manual CCP verification).

```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference VARCHAR(20) UNIQUE NOT NULL,  -- e.g., PY-2026-0001

    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,

    -- Payment details
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'DZD',
    payment_method VARCHAR(20) NOT NULL DEFAULT 'ccp',  -- ccp, baridimob, cash, other

    -- Customer claim
    payer_name VARCHAR(200),
    payer_account VARCHAR(50),
    transaction_reference VARCHAR(100),
    claimed_at TIMESTAMPTZ,
    notes TEXT,

    -- Verification
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, submitted, under_review, confirmed, rejected, refunded

    proof_file_id UUID REFERENCES file_assets(id) ON DELETE SET NULL,

    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,

    confirmed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    confirmed_at TIMESTAMPTZ,

    refunded_at TIMESTAMPTZ,
    refunded_by UUID REFERENCES users(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_payments_order ON payments(order_id);
CREATE INDEX ix_payments_customer ON payments(customer_id);
CREATE INDEX ix_payments_status ON payments(status);
```

### 3.16 production_orders

Production tracking for confirmed orders.

```sql
CREATE TABLE production_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,

    priority VARCHAR(10) NOT NULL DEFAULT 'normal',  -- low, normal, high, urgent
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, in_progress, quality_control, completed, on_hold

    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,

    estimated_start DATE,
    estimated_end DATE,
    actual_start DATE,
    actual_end DATE,

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_production_orders_status ON production_orders(status);
CREATE INDEX ix_production_orders_order ON production_orders(order_id);
CREATE INDEX ix_production_orders_assigned ON production_orders(assigned_to);
```

### 3.17 production_stages

Individual production stages within a production order.

```sql
CREATE TABLE production_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    production_order_id UUID NOT NULL REFERENCES production_orders(id) ON DELETE CASCADE,

    stage VARCHAR(30) NOT NULL,
    -- cutting, welding, grinding, painting, assembly, quality_control, packaging, ready

    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, in_progress, completed, skipped

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,

    -- Quality control specific
    quality_notes TEXT,
    quality_passed BOOLEAN,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_production_stages_order ON production_stages(production_order_id);
CREATE INDEX ix_production_stages_stage ON production_stages(stage);
```

### 3.18 deliveries

Delivery tracking.

```sql
CREATE TABLE deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,

    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    -- scheduled, in_transit, delivered, failed

    delivery_address TEXT NOT NULL,
    delivery_city VARCHAR(100),

    scheduled_date DATE,
    actual_delivery_date DATE,

    delivery_notes TEXT,
    recipient_name VARCHAR(200),

    delivered_by UUID REFERENCES users(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_deliveries_order ON deliveries(order_id);
CREATE INDEX ix_deliveries_status ON deliveries(status);
```

### 3.19 expenses

Business expenses tracking.

```sql
CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(50) NOT NULL,
    -- materials, labor, utilities, rent, transport, equipment, marketing, other

    description VARCHAR(500) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'DZD',

    expense_date DATE NOT NULL,

    -- Optional links
    material_id UUID REFERENCES materials(id) ON DELETE SET NULL,
    production_order_id UUID REFERENCES production_orders(id) ON DELETE SET NULL,

    receipt_file_id UUID REFERENCES file_assets(id) ON DELETE SET NULL,
    notes TEXT,

    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_expenses_category ON expenses(category);
CREATE INDEX ix_expenses_date ON expenses(expense_date);
```

### 3.20 file_assets

Uploaded files (secure storage).

```sql
CREATE TABLE file_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    original_filename VARCHAR(500) NOT NULL,
    stored_path VARCHAR(1000) NOT NULL,  -- S3 key or local path
    mime_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,  -- bytes

    -- Access control
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    access_level VARCHAR(20) NOT NULL DEFAULT 'private',
    -- private, signed_url_only

    -- Context
    context_type VARCHAR(50),  -- 'product', 'custom_request', 'payment_proof', 'design', 'other'
    context_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ  -- Soft delete
);

CREATE INDEX ix_file_assets_context ON file_assets(context_type, context_id);
```

### 3.21 audit_logs

Append-only audit trail.

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_email VARCHAR(320) NOT NULL,  -- Denormalized
    actor_role VARCHAR(20) NOT NULL,

    event VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,

    details JSONB DEFAULT '{}',

    ip_address VARCHAR(45),  -- IPv6 compatible
    user_agent TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Note: NO UPDATE or DELETE should ever be performed on this table.
-- Application should enforce append-only.

CREATE INDEX ix_audit_logs_actor ON audit_logs(actor_id);
CREATE INDEX ix_audit_logs_event ON audit_logs(event);
CREATE INDEX ix_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX ix_audit_logs_created ON audit_logs(created_at);
```

### 3.22 settings

System-wide configuration.

```sql
CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    -- general, business, payment, delivery, notification

    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Examples:**

```json
{ "key": "business_name", "value": "ZARO", "category": "business" }
{ "key": "business_phone", "value": "+213 XXX XXX XXX", "category": "business" }
{ "key": "ccp_account_number", "value": "XXXXXXXX", "category": "payment" }
{ "key": "ccp_account_name", "value": "ZARO Workshop", "category": "payment" }
{ "key": "tax_rate", "value": 19.0, "category": "business" }
{ "key": "default_currency", "value": "DZD", "category": "business" }
{ "key": "delivery_fee_local", "value": 2000, "category": "delivery" }
{ "key": "free_delivery_threshold", "value": 50000, "category": "delivery" }
```

---

## 4. State Machines

### 4.1 Order Status Flow

```
DRAFT
  → QUOTED (owner creates quote)
  → CUSTOMER_APPROVED (customer accepts quote)
  → DEPOSIT_PENDING (deposit requested)
  → PAYMENT_REVIEW (deposit submitted)
  → CONFIRMED (payment confirmed)
  → PRODUCTION (production starts)
  → QUALITY_CONTROL (QC stage)
  → READY (passed QC)
  → DELIVERY (out for delivery)
  → COMPLETED (delivered)

CANCELLED (from any non-terminal state)
COMPLETED (terminal)
```

### 4.2 Payment Status Flow

```
PENDING (created)
  → SUBMITTED (customer submits proof)
  → UNDER_REVIEW (owner begins review)
  → CONFIRMED (owner confirms)
  → REFUNDED (if needed)

REJECTED (from UNDER_REVIEW)
  → UNDER_REVIEW (re-submitted)
```

### 4.3 Quote Status Flow

```
DRAFT (owner creating)
  → SENT (sent to customer)
  → VIEWED (customer opened)
  → ACCEPTED (customer approves)
  → REJECTED (customer declines)

EXPIRED (past validity date)
CANCELLED (owner cancels)
```

---

## 5. Migration Strategy

### 5.1 Approach

- **Alembic** for all migrations
- **One migration per feature** or logical group
- **Reversible** where possible
- **No destructive operations** without explicit safety review
- **Offline SQL verification** before applying

### 5.2 Initial Migration Plan

```
0001_initial_zaro_schema
  - users
  - customers
  - categories
  - products
  - product_variants
  - file_assets
  - settings

0002_materials_inventory
  - materials
  - material_prices
  - inventory_movements

0003_custom_orders
  - custom_requests
  - quotes
  - quote_items
  - design_revisions

0004_orders_payments
  - orders
  - order_items
  - payments

0005_production_delivery
  - production_orders
  - production_stages
  - deliveries

0006_expenses_audit
  - expenses
  - audit_logs
```

---

## 6. UUID Strategy

- All primary keys are UUIDs (v4 random)
- Generated by `gen_random_uuid()` in PostgreSQL
- Application uses `uuid.uuid4()` for Python-side generation
- Public-facing references use human-readable format (OR-2026-0001)
- Internal queries use UUIDs
- API responses always return UUIDs (never sequential integers)

---

## 7. Performance Considerations

### 7.1 Indexing Strategy

- All foreign keys indexed
- Status fields indexed (common filter)
- Reference fields indexed (lookup by reference)
- Date fields indexed (date range queries)
- Composite indexes for common query patterns

### 7.2 Query Optimization

- Use `selectinload` / `joinedload` for related data
- Avoid N+1 queries with eager loading
- Pagination on all list endpoints
- Use `count()` efficiently with `select(func.count())`
- JSONB indexes for frequently queried JSON fields (V2 if needed)

### 7.3 Connection Pooling

- asyncpg connection pool
- Configurable pool size via environment
- Connection recycling on errors

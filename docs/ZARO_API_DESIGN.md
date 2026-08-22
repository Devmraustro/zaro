# ZARO API Design

**Version:** 1.0  
**Status:** Phase 1 - Foundation  
**Last Updated:** 2026-08-18

---

## 1. API Principles

1. **RESTful** — resource-oriented URLs, standard HTTP methods
2. **Versioned** — all endpoints under `/api/v1/`
3. **Typed** — Pydantic request/response schemas with OpenAPI documentation
4. **Consistent** — uniform response format, error structure, pagination
5. **Secure** — authentication + authorization on every protected endpoint
6. **Idempotent** — safe retries for sensitive operations
7. **Paginated** — all list endpoints support cursor/offset pagination
8. **Filterable** — query parameters for filtering and sorting

---

## 2. Base URL

```
Development: http://localhost:8000/api/v1
Production:  https://api.zaro.example.com/api/v1
```

---

## 3. Authentication

### 3.1 Login

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "owner@zaro.dz",
  "password": "secure_password"
}

Response 200:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "owner@zaro.dz",
    "full_name": "Owner Name",
    "role": "owner"
  }
}
```

### 3.2 Token Refresh

```
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}

Response 200:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 3.3 Logout

```
POST /api/v1/auth/logout
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}

Response 204: No Content
```

### 3.4 Authenticated Requests

```
Authorization: Bearer {access_token}
```

---

## 4. Response Format

### 4.1 Success (Single Resource)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "ATLAS Coffee Table",
  "slug": "atlas-coffee-table",
  "product_code": "ZAR-ATL-001",
  "selling_price": 45000,
  "currency": "DZD",
  "status": "active",
  "created_at": "2026-08-18T10:00:00Z",
  "updated_at": "2026-08-18T10:00:00Z"
}
```

### 4.2 Success (List with Pagination)

```json
{
  "items": [
    { "id": "...", "name": "ATLAS", "...": "..." },
    { "id": "...", "name": "NEXUS", "...": "..." }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "has_next": true,
  "has_previous": false
}
```

### 4.3 Error

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

### 4.4 Error Codes

| HTTP Status | Code                     | Description                               |
| ----------- | ------------------------ | ----------------------------------------- |
| 400         | VALIDATION_ERROR         | Invalid request data                      |
| 400         | INVALID_STATE_TRANSITION | Status machine violation                  |
| 401         | UNAUTHORIZED             | Missing or invalid authentication         |
| 401         | TOKEN_EXPIRED            | Access token expired                      |
| 403         | FORBIDDEN                | Insufficient permissions                  |
| 404         | NOT_FOUND                | Resource not found                        |
| 409         | CONFLICT                 | Resource already exists or state conflict |
| 413         | PAYLOAD_TOO_LARGE        | Upload exceeds size limit                 |
| 415         | UNSUPPORTED_MEDIA_TYPE   | Invalid file type                         |
| 422         | UNPROCESSABLE_ENTITY     | Semantically invalid request              |
| 429         | RATE_LIMITED             | Too many requests                         |
| 500         | INTERNAL_ERROR           | Server error                              |

---

## 5. Pagination

### Query Parameters

| Parameter    | Default    | Description                        |
| ------------ | ---------- | ---------------------------------- |
| `page`       | 1          | Page number (1-indexed)            |
| `page_size`  | 20         | Items per page (max 100)           |
| `sort_by`    | created_at | Field to sort by                   |
| `sort_order` | desc       | asc or desc                        |
| `search`     | —          | Full-text search (where supported) |
| `status`     | —          | Filter by status                   |
| `category`   | —          | Filter by category                 |

---

## 6. Endpoints

### 6.1 Public Endpoints (No Auth)

#### Products

```
GET    /api/v1/products                    List products (paginated, filterable)
GET    /api/v1/products/{slug}             Get product by slug
GET    /api/v1/categories                  List categories
GET    /api/v1/categories/{slug}           Get category with products
```

#### Custom Requests

```
POST   /api/v1/custom-requests             Submit custom request (public form)
```

#### Order Tracking

```
GET    /api/v1/orders/track/{reference}    Track order by reference (limited info)
```

#### Contact

```
POST   /api/v1/contact                     Submit contact form
```

### 6.2 Customer Endpoints (Auth Required)

```
GET    /api/v1/customers/me                Get current customer profile
PATCH  /api/v1/customers/me                Update profile
GET    /api/v1/orders/me                   List my orders
GET    /api/v1/orders/{reference}          Get my order details
GET    /api/v1/quotes/{reference}          View my quote
POST   /api/v1/quotes/{id}/approve         Approve quote
POST   /api/v1/quotes/{id}/reject          Reject quote
POST   /api/v1/payments                    Submit payment proof
GET    /api/v1/payments/me                 List my payments
POST   /api/v1/design-revisions/{id}/approve   Approve design
POST   /api/v1/design-revisions/{id}/reject    Reject design
```

### 6.3 Admin Endpoints (Auth + RBAC Required)

#### Dashboard

```
GET    /api/v1/admin/dashboard             Dashboard summary stats
GET    /api/v1/admin/dashboard/revenue     Revenue summary
GET    /api/v1/admin/dashboard/orders      Order statistics
GET    /api/v1/admin/dashboard/production  Production queue
```

#### Products

```
GET    /api/v1/products                    List all products (admin view)
POST   /api/v1/products                    Create product
GET    /api/v1/products/{id}               Get product by ID
PATCH  /api/v1/products/{id}               Update product
DELETE /api/v1/products/{id}               Soft-delete product
POST   /api/v1/products/{id}/images        Upload product images
DELETE /api/v1/products/{id}/images/{key}  Remove product image

GET    /api/v1/products/{id}/variants      List variants
POST   /api/v1/products/{id}/variants      Create variant
PATCH  /api/v1/products/{id}/variants/{vid} Update variant
DELETE /api/v1/products/{id}/variants/{vid} Delete variant
```

#### Categories

```
GET    /api/v1/categories                  List categories
POST   /api/v1/categories                  Create category
PATCH  /api/v1/categories/{id}             Update category
DELETE /api/v1/categories/{id}             Delete category
```

#### Custom Requests

```
GET    /api/v1/custom-requests             List all custom requests
GET    /api/v1/custom-requests/{id}        Get custom request details
PATCH  /api/v1/custom-requests/{id}        Update status/assignment
```

#### Quotes

```
GET    /api/v1/quotes                      List all quotes
POST   /api/v1/quotes                      Create quote
GET    /api/v1/quotes/{id}                 Get quote details
PATCH  /api/v1/quotes/{id}                 Update quote
POST   /api/v1/quotes/{id}/send            Send quote to customer
POST   /api/v1/quotes/{id}/cancel          Cancel quote
```

#### Orders

```
GET    /api/v1/orders                      List all orders
POST   /api/v1/orders                      Create order (admin)
GET    /api/v1/orders/{id}                 Get order details
PATCH  /api/v1/orders/{id}                 Update order status
POST   /api/v1/orders/{id}/cancel          Cancel order
```

#### Payments

```
GET    /api/v1/payments                    List all payments
GET    /api/v1/payments/{id}               Get payment details
PATCH  /api/v1/payments/{id}/review        Move to under review
POST   /api/v1/payments/{id}/confirm       Confirm payment (OWNER ONLY)
POST   /api/v1/payments/{id}/reject        Reject payment (OWNER ONLY)
```

#### Production

```
GET    /api/v1/production                  List production orders
POST   /api/v1/production                  Create production order
GET    /api/v1/production/{id}             Get production details
PATCH  /api/v1/production/{id}             Update production order
PATCH  /api/v1/production/{id}/stages/{sid} Update stage status
POST   /api/v1/production/{id}/stages/{sid}/quality  Submit quality check
```

#### Materials

```
GET    /api/v1/materials                   List materials
POST   /api/v1/materials                   Create material
GET    /api/v1/materials/{id}              Get material details
PATCH  /api/v1/materials/{id}              Update material
DELETE /api/v1/materials/{id}              Deactivate material
GET    /api/v1/materials/{id}/prices       Price history
POST   /api/v1/materials/{id}/prices       Record new price
```

#### Inventory

```
GET    /api/v1/inventory                   List inventory status
POST   /api/v1/inventory/movements         Record stock movement
GET    /api/v1/inventory/alerts            Low stock alerts
```

#### Customers

```
GET    /api/v1/customers                   List customers
POST   /api/v1/customers                   Create customer
GET    /api/v1/customers/{id}              Get customer details
PATCH  /api/v1/customers/{id}              Update customer
GET    /api/v1/customers/{id}/orders       Customer's orders
GET    /api/v1/customers/{id}/quotes       Customer's quotes
```

#### Expenses

```
GET    /api/v1/expenses                    List expenses
POST   /api/v1/expenses                    Record expense
GET    /api/v1/expenses/{id}               Get expense details
PATCH  /api/v1/expenses/{id}               Update expense
DELETE /api/v1/expenses/{id}               Delete expense
GET    /api/v1/expenses/summary            Expense summary by period
```

#### Deliveries

```
GET    /api/v1/deliveries                  List deliveries
POST   /api/v1/deliveries                  Schedule delivery
PATCH  /api/v1/deliveries/{id}             Update delivery status
```

#### Audit Log

```
GET    /api/v1/audit                       List audit logs (OWNER ONLY)
GET    /api/v1/audit/{id}                  Get audit log details
```

#### Settings

```
GET    /api/v1/settings                    List all settings
GET    /api/v1/settings/{key}              Get setting value
PATCH  /api/v1/settings/{key}              Update setting (OWNER ONLY)
```

#### Users (Admin)

```
GET    /api/v1/users                       List system users
POST   /api/v1/users                       Create user
GET    /api/v1/users/{id}                  Get user details
PATCH  /api/v1/users/{id}                  Update user
DELETE /api/v1/users/{id}                  Deactivate user
POST   /api/v1/users/{id}/reset-password   Reset user password
```

#### Files

```
POST   /api/v1/files                       Upload file
GET    /api/v1/files/{id}                  Get file info
DELETE /api/v1/files/{id}                  Delete file
GET    /api/v1/files/{id}/download         Get signed download URL
```

#### Health

```
GET    /api/v1/health                      Health check
GET    /api/v1/health/ready                Readiness check (DB, Redis, S3)
```

---

## 7. Request/Response Schemas

### 7.1 Product

**Create:**

```json
{
  "name": "ATLAS Coffee Table",
  "product_code": "ZAR-ATL-001",
  "description": "Minimalist coffee table with matte black steel frame and natural oak top.",
  "category_id": "uuid",
  "dimensions": {
    "width": 120,
    "height": 45,
    "depth": 60,
    "unit": "cm"
  },
  "materials": [
    { "name": "Steel Tube 30x30", "finish": "Matte Black Powder Coat" },
    { "name": "Natural Oak", "finish": "Clear Lacquer" }
  ],
  "weight_kg": 28.5,
  "selling_price": 45000,
  "currency": "DZD",
  "production_time_days": 14,
  "stock_status": "in_stock",
  "delivery_info": "Free delivery in Algiers. 2000 DZD elsewhere.",
  "status": "active",
  "is_featured": true
}
```

**Read (Public):**

```json
{
  "id": "uuid",
  "name": "ATLAS Coffee Table",
  "slug": "atlas-coffee-table",
  "product_code": "ZAR-ATL-001",
  "description": "...",
  "category": { "id": "uuid", "name": "Coffee Tables", "slug": "coffee-tables" },
  "dimensions": { "width": 120, "height": 45, "depth": 60, "unit": "cm" },
  "materials": [...],
  "weight_kg": 28.5,
  "selling_price": 45000,
  "currency": "DZD",
  "images": [...],
  "videos": [...],
  "variants": [...],
  "stock_status": "in_stock",
  "production_time_days": 14,
  "delivery_info": "...",
  "is_featured": true,
  "created_at": "2026-08-18T10:00:00Z"
}
```

### 7.2 Custom Request

**Submit:**

```json
{
  "customer_name": "Ahmed Benali",
  "customer_email": "ahmed@example.com",
  "customer_phone": "+213 555 123 456",
  "category": "dining_table",
  "description": "I want a 180cm dining table with a black steel frame and natural wood top.",
  "desired_dimensions": {
    "width": 180,
    "height": 75,
    "depth": 90,
    "unit": "cm"
  },
  "materials": "Steel frame, natural wood top",
  "colors": "Black frame, natural wood",
  "finish": "Matte black frame, clear lacquer top",
  "quantity": 1,
  "budget_min": 80000,
  "budget_max": 120000,
  "notes": "Must fit through standard door (90cm).",
  "source": "instagram"
}
```

### 7.3 Order

**Read:**

```json
{
  "id": "uuid",
  "reference": "OR-2026-0001",
  "order_type": "custom",
  "status": "confirmed",
  "customer": {
    "id": "uuid",
    "name": "Ahmed Benali",
    "email": "ahmed@example.com"
  },
  "items": [
    {
      "id": "uuid",
      "product_name": "Custom Dining Table",
      "quantity": 1,
      "unit_price": 95000,
      "total_price": 95000,
      "custom_description": "180cm dining table, black steel, natural wood top"
    }
  ],
  "subtotal": 95000,
  "discount": 0,
  "tax_amount": 0,
  "total": 95000,
  "deposit_amount": 47500,
  "amount_paid": 47500,
  "currency": "DZD",
  "shipping_address": "123 Rue Didouche Mourad, Algiers",
  "confirmed_at": "2026-08-18T14:00:00Z",
  "created_at": "2026-08-17T10:00:00Z"
}
```

### 7.4 Payment

**Submit (Customer):**

```json
{
  "order_id": "uuid",
  "amount": 47500,
  "payment_method": "ccp",
  "payer_name": "Ahmed Benali",
  "payer_account": "12345678",
  "transaction_reference": "TXN-20260818-001",
  "notes": "Deposit payment for OR-2026-0001"
}
```

**Confirm (Owner only):**

```json
{
  "reference_number": "VERIFIED-001",
  "notes": "Payment confirmed via CCP statement"
}
```

---

## 8. Rate Limits

| Endpoint Group            | Limit        | Window   |
| ------------------------- | ------------ | -------- |
| Auth (login/register)     | 5 requests   | 1 minute |
| General API               | 120 requests | 1 minute |
| Custom request submission | 10 requests  | 1 hour   |
| File upload               | 10 requests  | 1 hour   |
| Order tracking (public)   | 30 requests  | 1 minute |

Rate limit headers:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1692345678
```

---

## 9. API Versioning

- All endpoints under `/api/v1/`
- Breaking changes require new version (`/api/v2/`)
- Non-breaking additions (new fields, new endpoints) within current version
- Deprecated endpoints include `Sunset` header with removal date
- Minimum 6-month overlap for breaking changes

---

## 10. File Upload

```
POST /api/v1/files
Content-Type: multipart/form-data

file: (binary)
context_type: "product"
context_id: "uuid"

Response 201:
{
  "id": "uuid",
  "original_filename": "atlas-table-01.jpg",
  "mime_type": "image/jpeg",
  "file_size": 245760,
  "download_url": "/api/v1/files/uuid/download",
  "created_at": "2026-08-18T10:00:00Z"
}
```

**Constraints:**

- Max file size: 10MB
- Allowed types: image/jpeg, image/png, image/webp, application/pdf
- No executable files
- Private storage, signed URL access

---

## 11. WebSocket (Future)

At V1, WebSocket is not implemented. All updates use polling.

V2 will add WebSocket for:

- Real-time production status updates (admin)
- Order status change notifications (customer)

---

## 12. OpenAPI Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Disabled in production via settings.

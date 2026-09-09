from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    SALES = "sales"
    PRODUCTION = "production"
    CONTENT = "content"
    ACCOUNTING = "accounting"
    WORKER = "worker"
    CUSTOMER = "customer"


class Permission(StrEnum):
    # Users
    USERS_READ = "users.read"
    USERS_CREATE = "users.create"
    USERS_UPDATE = "users.update"
    USERS_DISABLE = "users.disable"
    USERS_ASSIGN_ROLE = "users.assign_role"

    # Products
    PRODUCTS_READ = "products.read"
    PRODUCTS_CREATE = "products.create"
    PRODUCTS_UPDATE = "products.update"
    PRODUCTS_DELETE = "products.delete"
    PRODUCTS_MANAGE_PRICE = "products.manage_price"

    # Materials
    MATERIALS_READ = "materials.read"
    MATERIALS_CREATE = "materials.create"
    MATERIALS_UPDATE = "materials.update"
    MATERIALS_DELETE = "materials.delete"

    # Inventory
    INVENTORY_READ = "inventory.read"
    INVENTORY_MANAGE = "inventory.manage"

    # Customers
    CUSTOMERS_READ = "customers.read"
    CUSTOMERS_CREATE = "customers.create"
    CUSTOMERS_UPDATE = "customers.update"
    CUSTOMERS_DELETE = "customers.delete"

    # Leads
    LEADS_READ = "leads.read"
    LEADS_MANAGE = "leads.manage"

    # Quotes
    QUOTES_READ = "quotes.read"
    QUOTES_CREATE = "quotes.create"
    QUOTES_UPDATE = "quotes.update"
    QUOTES_APPROVE = "quotes.approve"

    # Orders
    ORDERS_READ = "orders.read"
    ORDERS_CREATE = "orders.create"
    ORDERS_UPDATE = "orders.update"
    ORDERS_CANCEL = "orders.cancel"

    # Payments
    PAYMENTS_READ = "payments.read"
    PAYMENTS_SUBMIT = "payments.submit"
    PAYMENTS_REVIEW = "payments.review"
    PAYMENTS_CONFIRM = "payments.confirm"
    PAYMENTS_REJECT = "payments.reject"

    # Production
    PRODUCTION_READ = "production.read"
    PRODUCTION_MANAGE = "production.manage"

    # Quality
    QUALITY_READ = "quality.read"
    QUALITY_MANAGE = "quality.manage"

    # Delivery
    DELIVERY_READ = "delivery.read"
    DELIVERY_MANAGE = "delivery.manage"

    # Content
    CONTENT_READ = "content.read"
    CONTENT_MANAGE = "content.manage"

    # Finance
    FINANCE_READ = "finance.read"
    FINANCE_MANAGE = "finance.manage"

    # Audit
    AUDIT_READ = "audit.read"

    # Custom requests
    CUSTOM_REQUESTS_READ = "custom_requests.read"
    CUSTOM_REQUESTS_UPDATE = "custom_requests.update"


ALL_PERMISSIONS: frozenset[Permission] = frozenset(Permission)


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class StockStatus(StrEnum):
    IN_STOCK = "in_stock"
    MADE_TO_ORDER = "made_to_order"
    OUT_OF_STOCK = "out_of_stock"


class MaterialUnit(StrEnum):
    KG = "kg"
    METER = "meter"
    PIECE = "piece"
    LITER = "liter"
    SQUARE_METER = "square_meter"
    HOUR = "hour"


class MaterialCategory(StrEnum):
    STEEL = "steel"
    WOOD = "wood"
    PAINT = "paint"
    HARDWARE = "hardware"
    CONSUMABLE = "consumable"
    OTHER = "other"


class CustomRequestStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    NEEDS_INFORMATION = "needs_information"
    QUOTATION_PENDING = "quotation_pending"
    CANCELLED = "cancelled"
    CONVERTED = "converted"


# Allowed forward transitions of the custom-request lifecycle.
# Terminal states (CANCELLED, CONVERTED) map to an empty set.
CUSTOM_REQUEST_TRANSITIONS: dict[CustomRequestStatus, frozenset[CustomRequestStatus]] = {
    CustomRequestStatus.SUBMITTED: frozenset({CustomRequestStatus.UNDER_REVIEW, CustomRequestStatus.CANCELLED}),
    CustomRequestStatus.UNDER_REVIEW: frozenset(
        {
            CustomRequestStatus.NEEDS_INFORMATION,
            CustomRequestStatus.QUOTATION_PENDING,
            CustomRequestStatus.CANCELLED,
        }
    ),
    CustomRequestStatus.NEEDS_INFORMATION: frozenset({CustomRequestStatus.UNDER_REVIEW, CustomRequestStatus.CANCELLED}),
    CustomRequestStatus.QUOTATION_PENDING: frozenset({CustomRequestStatus.CONVERTED, CustomRequestStatus.CANCELLED}),
    CustomRequestStatus.CANCELLED: frozenset(),
    CustomRequestStatus.CONVERTED: frozenset(),
}


class CustomRequestSource(StrEnum):
    WEBSITE = "website"
    INSTAGRAM = "instagram"
    PHONE = "phone"
    WALK_IN = "walk_in"


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    DEPOSIT_REQUIRED = "deposit_required"
    CONVERTED = "converted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


# Allowed forward transitions of the quote lifecycle.
# Terminal states (EXPIRED, CANCELLED, REJECTED, CONVERTED) map to an empty set.
QUOTE_TRANSITIONS: dict[QuoteStatus, frozenset[QuoteStatus]] = {
    QuoteStatus.DRAFT: frozenset({QuoteStatus.SENT, QuoteStatus.CANCELLED}),
    QuoteStatus.SENT: frozenset(
        {QuoteStatus.VIEWED, QuoteStatus.ACCEPTED, QuoteStatus.REJECTED, QuoteStatus.CANCELLED}
    ),
    QuoteStatus.VIEWED: frozenset(
        {QuoteStatus.ACCEPTED, QuoteStatus.REJECTED, QuoteStatus.CANCELLED}
    ),
    QuoteStatus.ACCEPTED: frozenset({QuoteStatus.DEPOSIT_REQUIRED}),
    QuoteStatus.DEPOSIT_REQUIRED: frozenset({QuoteStatus.CONVERTED}),
    QuoteStatus.CONVERTED: frozenset(),
    QuoteStatus.EXPIRED: frozenset(),
    QuoteStatus.CANCELLED: frozenset(),
    QuoteStatus.REJECTED: frozenset(),
}


class OrderStatus(StrEnum):
    # Phase 3 states. Future phases extend this enum and the transition map
    # with production/delivery states; existing rows keep working because
    # unknown-to-old-code values are never produced by old code paths.
    PENDING_DEPOSIT = "pending_deposit"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING_DEPOSIT: frozenset(
        {OrderStatus.CONFIRMED, OrderStatus.CANCELLED}
    ),
    OrderStatus.CONFIRMED: frozenset(),  # future phases append production states here
    OrderStatus.CANCELLED: frozenset(),
}


class PaymentMethod(StrEnum):
    CCP = "ccp"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROOF_UPLOADED = "proof_uploaded"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


PAYMENT_STATUS_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {PaymentStatus.PROOF_UPLOADED, PaymentStatus.UNDER_REVIEW, PaymentStatus.CANCELLED}
    ),
    # PROOF_UPLOADED -> PROOF_UPLOADED is proof replacement: the customer may
    # swap the file before submitting for review (each upload is audited).
    PaymentStatus.PROOF_UPLOADED: frozenset(
        {PaymentStatus.PROOF_UPLOADED, PaymentStatus.UNDER_REVIEW, PaymentStatus.CANCELLED}
    ),
    # UNDER_REVIEW -> CANCELLED exists ONLY for the server-side order-cancellation
    # linkage (cancelling an order cancels its unresolved claim). No client
    # operation targets CANCELLED directly.
    PaymentStatus.UNDER_REVIEW: frozenset({PaymentStatus.CONFIRMED, PaymentStatus.REJECTED, PaymentStatus.CANCELLED}),
    # CONFIRMED is irreversible by design; corrections go through a separate
    # reversal workflow in a future phase.
    PaymentStatus.CONFIRMED: frozenset(),
    # A rejected claim may be resubmitted with better proof (replacement flow,
    # same payment record -- no duplicate claims).
    PaymentStatus.REJECTED: frozenset({PaymentStatus.PROOF_UPLOADED}),
    PaymentStatus.CANCELLED: frozenset(),
}


class FilePurpose(StrEnum):
    """Why a stored asset exists. Drives authorization and lifecycle rules."""

    CUSTOM_REQUEST_INSPIRATION = "custom_request_inspiration"
    PRODUCT_MEDIA = "product_media"
    PAYMENT_PROOF = "payment_proof"


class FileVisibility(StrEnum):
    PRIVATE = "private"
    PUBLIC = "public"


class MediaKind(StrEnum):
    """Editorial role of a product media item."""

    HERO = "hero"
    GALLERY = "gallery"
    DETAIL = "detail"
    LIFESTYLE = "lifestyle"
    VIDEO = "video"


class StockMovementType(StrEnum):
    """
    Enumeration of all valid stock movement types.
    Used in stock_movements.movement_type CHECK constraint and model validation.
    """
    PURCHASE = "purchase"
    RESERVE = "reserve"
    RELEASE = "release"
    CONSUME = "consume"
    PRODUCTION_WASTE = "production_waste"
    INVENTORY_WASTE = "inventory_waste"
    ADJUST = "adjust"
    RETURN = "return"


class ProductionOrderStatus(StrEnum):
    """
    Enumeration of production order statuses.
    Used in production_orders.status CHECK constraint and model validation.
    Matches PostgreSQL productionorderstatus type.
    """
    PENDING = "pending"
    PLANNED = "planned"
    MATERIALS_RESERVED = "materials_reserved"
    IN_PRODUCTION = "in_production"
    PAUSED = "paused"
    QUALITY_CHECK = "quality_check"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Allowed forward transitions of the production order lifecycle.
# Terminal states (COMPLETED, CANCELLED) map to an empty set.
#
# - QUALITY_CHECK -> IN_PRODUCTION is the rework path: a rejected QC decision
#   returns the order to production instead of approving it.
# - Every non-terminal state may transition to CANCELLED (server-side
#   cancellation only; there is no client-driven "set status" operation).
PRODUCTION_ORDER_TRANSITIONS: dict[ProductionOrderStatus, frozenset[ProductionOrderStatus]] = {
    ProductionOrderStatus.PENDING: frozenset({ProductionOrderStatus.PLANNED, ProductionOrderStatus.CANCELLED}),
    ProductionOrderStatus.PLANNED: frozenset(
        {ProductionOrderStatus.MATERIALS_RESERVED, ProductionOrderStatus.CANCELLED}
    ),
    ProductionOrderStatus.MATERIALS_RESERVED: frozenset(
        {ProductionOrderStatus.IN_PRODUCTION, ProductionOrderStatus.CANCELLED}
    ),
    ProductionOrderStatus.IN_PRODUCTION: frozenset(
        {
            ProductionOrderStatus.QUALITY_CHECK,
            ProductionOrderStatus.PAUSED,
            ProductionOrderStatus.CANCELLED,
        }
    ),
    ProductionOrderStatus.QUALITY_CHECK: frozenset(
        {
            ProductionOrderStatus.READY,
            ProductionOrderStatus.IN_PRODUCTION,
            ProductionOrderStatus.CANCELLED,
        }
    ),
    ProductionOrderStatus.PAUSED: frozenset({ProductionOrderStatus.IN_PRODUCTION, ProductionOrderStatus.CANCELLED}),
    ProductionOrderStatus.READY: frozenset({ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED}),
    ProductionOrderStatus.COMPLETED: frozenset(),
    ProductionOrderStatus.CANCELLED: frozenset(),
}


class ProductionMaterialReservationStatus(StrEnum):
    """Status of a production material reservation."""
    PENDING = "pending"
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"


# Allowed forward transitions of the production material reservation lifecycle.
# Terminal states (CONSUMED, RELEASED) map to an empty set.
PRODUCTION_MATERIAL_RESERVATION_TRANSITIONS: dict[ProductionMaterialReservationStatus, frozenset[ProductionMaterialReservationStatus]] = {
    ProductionMaterialReservationStatus.PENDING: frozenset({ProductionMaterialReservationStatus.RESERVED}),
    ProductionMaterialReservationStatus.RESERVED: frozenset({
        ProductionMaterialReservationStatus.CONSUMED,
        ProductionMaterialReservationStatus.RELEASED,
    }),
    ProductionMaterialReservationStatus.CONSUMED: frozenset(),
    ProductionMaterialReservationStatus.RELEASED: frozenset(),
}

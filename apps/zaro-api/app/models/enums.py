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

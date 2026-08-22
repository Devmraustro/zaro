"""Centralized role-permission matrix.

Every ZARO role maps to a deterministic set of permissions.
Authorization decisions are derived from this single source of truth.
"""

from app.models.enums import ALL_PERMISSIONS, Permission, Role

# Deny by default: if a role is not listed for a permission, it is denied.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: ALL_PERMISSIONS,
    Role.ADMIN: frozenset(
        {
            Permission.USERS_READ,
            Permission.USERS_CREATE,
            Permission.USERS_UPDATE,
            Permission.USERS_DISABLE,
            Permission.PRODUCTS_READ,
            Permission.PRODUCTS_CREATE,
            Permission.PRODUCTS_UPDATE,
            Permission.PRODUCTS_DELETE,
            Permission.PRODUCTS_MANAGE_PRICE,
            Permission.MATERIALS_READ,
            Permission.MATERIALS_CREATE,
            Permission.MATERIALS_UPDATE,
            Permission.MATERIALS_DELETE,
            Permission.INVENTORY_READ,
            Permission.INVENTORY_MANAGE,
            Permission.CUSTOMERS_READ,
            Permission.CUSTOMERS_CREATE,
            Permission.CUSTOMERS_UPDATE,
            Permission.CUSTOMERS_DELETE,
            Permission.LEADS_READ,
            Permission.LEADS_MANAGE,
            Permission.QUOTES_READ,
            Permission.QUOTES_CREATE,
            Permission.QUOTES_UPDATE,
            Permission.QUOTES_APPROVE,
            Permission.ORDERS_READ,
            Permission.ORDERS_CREATE,
            Permission.ORDERS_UPDATE,
            Permission.ORDERS_CANCEL,
            Permission.PAYMENTS_READ,
            Permission.PAYMENTS_REVIEW,
            Permission.PRODUCTION_READ,
            Permission.PRODUCTION_MANAGE,
            Permission.QUALITY_READ,
            Permission.QUALITY_MANAGE,
            Permission.DELIVERY_READ,
            Permission.DELIVERY_MANAGE,
            Permission.CONTENT_READ,
            Permission.CONTENT_MANAGE,
            Permission.AUDIT_READ,
            Permission.CUSTOM_REQUESTS_READ,
            Permission.CUSTOM_REQUESTS_UPDATE,
        }
    ),
    Role.SALES: frozenset(
        {
            Permission.PRODUCTS_READ,
            Permission.CUSTOMERS_READ,
            Permission.CUSTOMERS_CREATE,
            Permission.CUSTOMERS_UPDATE,
            Permission.LEADS_READ,
            Permission.LEADS_MANAGE,
            Permission.QUOTES_READ,
            Permission.QUOTES_CREATE,
            Permission.QUOTES_UPDATE,
            Permission.ORDERS_READ,
            Permission.CUSTOM_REQUESTS_READ,
            Permission.CUSTOM_REQUESTS_UPDATE,
        }
    ),
    Role.PRODUCTION: frozenset(
        {
            Permission.PRODUCTS_READ,
            Permission.MATERIALS_READ,
            Permission.INVENTORY_READ,
            Permission.ORDERS_READ,
            Permission.PRODUCTION_READ,
            Permission.PRODUCTION_MANAGE,
            Permission.QUALITY_READ,
            Permission.QUALITY_MANAGE,
            Permission.DELIVERY_READ,
        }
    ),
    Role.CONTENT: frozenset(
        {
            Permission.PRODUCTS_READ,
            Permission.CONTENT_READ,
            Permission.CONTENT_MANAGE,
            # NOTE: CONTENT deliberately has NO customer access. Catalog
            # editors never need customer PII (privacy requirement).
        }
    ),
    Role.ACCOUNTING: frozenset(
        {
            Permission.PAYMENTS_READ,
            Permission.PAYMENTS_REVIEW,
            Permission.FINANCE_READ,
            Permission.FINANCE_MANAGE,
            Permission.ORDERS_READ,
            Permission.CUSTOMERS_READ,
            Permission.INVENTORY_READ,
            Permission.AUDIT_READ,
        }
    ),
    Role.WORKER: frozenset(
        {
            Permission.PRODUCTION_READ,
            Permission.MATERIALS_READ,
            Permission.PRODUCTS_READ,
        }
    ),
    Role.CUSTOMER: frozenset(
        {
            Permission.PRODUCTS_READ,
        }
    ),
}

# Privileged actions that must be explicitly gated beyond basic RBAC.
# These represent operations where resource-level authorization is required
# (e.g. customer can only view THEIR OWN orders).
RESOURCE_OWNERSHIP_REQUIRED: frozenset[Permission] = frozenset(
    {
        Permission.ORDERS_READ,
        Permission.ORDERS_UPDATE,
        Permission.ORDERS_CANCEL,
        Permission.QUOTES_READ,
        Permission.QUOTES_APPROVE,
        Permission.PAYMENTS_SUBMIT,
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_UPDATE,
        Permission.CUSTOM_REQUESTS_READ,
        Permission.CUSTOM_REQUESTS_UPDATE,
    }
)


def get_permissions_for_role(role: Role) -> frozenset[Permission]:
    """Return the direct permissions for a role. Empty frozenset if role unknown."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def get_all_permissions_for_role(role: Role) -> frozenset[Permission]:
    """Return all permissions for a role (alias for clarity)."""
    return get_permissions_for_role(role)

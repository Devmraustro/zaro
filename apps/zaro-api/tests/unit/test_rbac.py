from app.core.rbac import ROLE_PERMISSIONS, get_permissions_for_role, has_permission
from app.models.enums import ALL_PERMISSIONS, Permission, Role


class TestRoles:
    def test_all_expected_roles_exist(self):
        expected = {"owner", "admin", "sales", "production", "content", "accounting", "worker", "customer"}
        actual = {role.value for role in Role}
        assert actual == expected

    def test_role_count(self):
        assert len(Role) == 8

    def test_roles_are_strings(self):
        for role in Role:
            assert isinstance(role.value, str)
            assert len(role.value) > 0

    def test_role_names_are_lowercase(self):
        for role in Role:
            assert role.value == role.value.lower()


class TestPermissions:
    def test_all_expected_permission_groups_exist(self):
        groups = {p.value.split(".")[0] for p in Permission}
        expected_groups = {
            "users",
            "products",
            "materials",
            "inventory",
            "customers",
            "custom_requests",
            "leads",
            "quotes",
            "orders",
            "payments",
            "production",
            "quality",
            "delivery",
            "content",
            "finance",
            "audit",
        }
        assert groups == expected_groups

    def test_permission_count(self):
        assert len(Permission) >= 45

    def test_permissions_are_dotted_strings(self):
        for perm in Permission:
            assert "." in perm.value
            parts = perm.value.split(".")
            assert len(parts) == 2
            assert len(parts[0]) > 0
            assert len(parts[1]) > 0

    def test_all_permissions_in_frozenset(self):
        assert frozenset(Permission) == ALL_PERMISSIONS


class TestRolePermissionMatrix:
    def test_every_role_has_permissions_defined(self):
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"Role {role.value} missing from ROLE_PERMISSIONS"

    def test_owner_has_all_permissions(self):
        owner_perms = ROLE_PERMISSIONS[Role.OWNER]
        assert owner_perms == ALL_PERMISSIONS

    def test_worker_has_limited_permissions(self):
        worker_perms = ROLE_PERMISSIONS[Role.WORKER]
        assert len(worker_perms) < 10
        assert Permission.PRODUCTION_READ in worker_perms
        assert Permission.PRODUCTS_READ in worker_perms
        assert Permission.FINANCE_READ not in worker_perms
        assert Permission.PAYMENTS_CONFIRM not in worker_perms

    def test_customer_has_minimal_permissions(self):
        customer_perms = ROLE_PERMISSIONS[Role.CUSTOMER]
        assert len(customer_perms) <= 3
        assert Permission.PRODUCTS_READ in customer_perms
        assert Permission.PAYMENTS_CONFIRM not in customer_perms
        assert Permission.USERS_READ not in customer_perms

    def test_sales_cannot_confirm_payments(self):
        sales_perms = ROLE_PERMISSIONS[Role.SALES]
        assert Permission.PAYMENTS_CONFIRM not in sales_perms
        assert Permission.PAYMENTS_REJECT not in sales_perms
        assert Permission.FINANCE_READ not in sales_perms

    def test_production_cannot_manage_users(self):
        prod_perms = ROLE_PERMISSIONS[Role.PRODUCTION]
        assert Permission.USERS_READ not in prod_perms
        assert Permission.USERS_CREATE not in prod_perms
        assert Permission.USERS_ASSIGN_ROLE not in prod_perms

    def test_content_cannot_access_finance(self):
        content_perms = ROLE_PERMISSIONS[Role.CONTENT]
        assert Permission.FINANCE_READ not in content_perms
        assert Permission.FINANCE_MANAGE not in content_perms
        assert Permission.PAYMENTS_CONFIRM not in content_perms

    def test_accounting_cannot_manage_roles(self):
        acct_perms = ROLE_PERMISSIONS[Role.ACCOUNTING]
        assert Permission.USERS_ASSIGN_ROLE not in acct_perms
        assert Permission.USERS_DISABLE not in acct_perms
        assert Permission.PAYMENTS_CONFIRM not in acct_perms

    def test_admin_cannot_confirm_payments(self):
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.PAYMENTS_CONFIRM not in admin_perms
        assert Permission.PAYMENTS_REJECT not in admin_perms

    def test_only_owner_can_assign_roles(self):
        for role in Role:
            perms = ROLE_PERMISSIONS[role]
            if role == Role.OWNER:
                assert Permission.USERS_ASSIGN_ROLE in perms
            else:
                assert Permission.USERS_ASSIGN_ROLE not in perms

    def test_no_role_has_duplicate_permissions(self):
        for role, perms in ROLE_PERMISSIONS.items():
            assert len(perms) == len(set(perms)), f"Duplicate permissions for {role.value}"


class TestPermissionLookup:
    def test_get_permissions_for_known_role(self):
        perms = get_permissions_for_role(Role.OWNER)
        assert Permission.AUDIT_READ in perms

    def test_get_permissions_for_unknown_role(self):
        perms = get_permissions_for_role("nonexistent")  # type: ignore[arg-type]
        assert perms == frozenset()

    def test_has_permission_owner(self):
        assert has_permission(Role.OWNER, Permission.PAYMENTS_CONFIRM) is True

    def test_has_permission_worker_deny(self):
        assert has_permission(Role.WORKER, Permission.PAYMENTS_CONFIRM) is False

    def test_has_permission_customer_deny(self):
        assert has_permission(Role.CUSTOMER, Permission.USERS_READ) is False

    def test_deny_by_default(self):
        for role in Role:
            for perm in ALL_PERMISSIONS:
                result = has_permission(role, perm)
                if role == Role.OWNER:
                    assert result is True, f"OWNER missing {perm.value}"
                else:
                    if perm not in ROLE_PERMISSIONS.get(role, frozenset()):
                        assert result is False, f"{role.value} should NOT have {perm.value}"


class TestPermissionUniqueness:
    def test_permissions_are_unique(self):
        seen = set()
        for perm in Permission:
            assert perm.value not in seen, f"Duplicate permission: {perm.value}"
            seen.add(perm.value)

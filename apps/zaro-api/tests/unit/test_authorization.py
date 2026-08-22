import pytest
from httpx import AsyncClient

from app.models.enums import Role


class TestUnauthenticatedAccess:
    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, client: AsyncClient):
        response = await client.get("/api/v1/audit/logs")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_auth_header_returns_401(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": "NotBearer token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_returns_401(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401


class TestForbiddenAccess:
    @pytest.mark.asyncio
    async def test_worker_cannot_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.WORKER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "forbidden"

    @pytest.mark.asyncio
    async def test_customer_cannot_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.CUSTOMER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sales_cannot_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.SALES)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_production_cannot_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.PRODUCTION)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_content_cannot_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.CONTENT)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403


class TestAuthorizedAccess:
    @pytest.mark.asyncio
    async def test_owner_can_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.ADMIN)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accounting_can_access_audit_logs(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.ACCOUNTING)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 200


class TestPermissionDeniedAuditLogging:
    @pytest.mark.asyncio
    async def test_permission_denial_creates_audit_event(self, client: AsyncClient, auth_header_factory, db_session):
        from sqlalchemy import select

        from app.models.audit_log import AuditLog

        headers, user = await auth_header_factory(role=Role.WORKER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action == "PERMISSION_DENIED",
            )
        )
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.result == "DENIED"
        assert event.metadata_json["required_permission"] == "audit.read"
        assert event.metadata_json["user_role"] == "worker"


class TestErrorDoesNotLeakInternals:
    @pytest.mark.asyncio
    async def test_403_does_not_leak_role_details(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.WORKER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        body = response.text
        assert "traceback" not in body.lower()
        assert ".py" not in body

    @pytest.mark.asyncio
    async def test_401_does_not_leak_implementation_details(self, client: AsyncClient):
        response = await client.get("/api/v1/audit/logs")
        body = response.text
        assert "traceback" not in body.lower()
        assert ".py" not in body
        assert "sqlalchemy" not in body.lower()


class TestPrivilegeEscalation:
    @pytest.mark.asyncio
    async def test_cannot_self_assign_owner_role_via_header(self, client: AsyncClient, auth_header_factory):
        _headers, _user = await auth_header_factory(role=Role.WORKER)
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "attacker@example.com",
                "password": "password123",
                "role": "owner",
            },
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_worker_cannot_access_admin_endpoints(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.WORKER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_customer_cannot_access_worker_endpoints(self, client: AsyncClient, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.CUSTOMER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

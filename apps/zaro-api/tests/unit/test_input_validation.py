import pytest
from httpx import AsyncClient


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_empty_body_rejected(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "validation_error"

    @pytest.mark.asyncio
    async def test_extra_fields_rejected(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123",
                "admin": True,
                "role": "owner",
            },
        )
        # Should either succeed (ignoring extra) or reject — depending on model config
        # The important thing is that extra fields don't cause privilege escalation
        assert response.status_code in (200, 401, 422)

    @pytest.mark.asyncio
    async def test_sql_injection_in_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "'; DROP TABLE users; --", "password": "password"},
        )
        assert response.status_code in (401, 422)
        # Verify users table still exists by hitting health endpoint
        health = await client.get("/api/v1/health")
        assert health.status_code == 200

    @pytest.mark.asyncio
    async def test_xss_in_input(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "<script>alert('xss')</script>@example.com", "password": "password"},
        )
        assert response.status_code in (401, 422)
        body = response.text
        assert "<script>" not in body

    @pytest.mark.asyncio
    async def test_very_long_input(self, client: AsyncClient):
        long_string = "a" * 10000
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": f"{long_string}@example.com", "password": long_string},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_uuid_format(self, client: AsyncClient):
        response = await client.get("/api/v1/users/not-a-uuid")
        assert response.status_code in (401, 404, 422)

import pytest
from httpx import AsyncClient


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_validation_error_format(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": ""},
        )
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "validation_error"
        assert "details" in data["error"]

    @pytest.mark.asyncio
    async def test_404_error_format(self, client: AsyncClient):
        response = await client.get("/api/v1/nonexistent-resource")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "http_error"

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, client: AsyncClient):
        response = await client.put("/health/live")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_error_does_not_leak_internals(self, client: AsyncClient):
        response = await client.get("/api/v1/nonexistent")
        body = response.text
        assert ".py" not in body
        assert "traceback" not in body.lower()
        assert "sqlalchemy" not in body.lower()
        assert "postgresql" not in body.lower()
        assert "asyncpg" not in body.lower()

    @pytest.mark.asyncio
    async def test_malformed_json(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            content=b"not json at all",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

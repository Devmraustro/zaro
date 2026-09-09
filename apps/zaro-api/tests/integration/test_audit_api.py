"""Integration tests for the audit log endpoint."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def owner_headers(auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    return headers


@pytest.mark.anyio
async def test_list_logs_ok(client, owner_headers):
    resp = await client.get("/api/v1/audit/logs", headers=owner_headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.anyio
async def test_invalid_actor_id_returns_422_not_500(client, owner_headers):
    resp = await client.get("/api/v1/audit/logs?actor_id=not-a-uuid", headers=owner_headers)
    assert resp.status_code == 422, resp.text

"""Integration tests for materials + price history."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def create_material(client, headers, code="MAT-STL-01", name="Steel tube 40x40") -> dict:
    resp = await client.post(
        "/api/v1/admin/materials",
        json={"name": name, "code": code, "category": "steel", "unit": "kg"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def owner_headers(auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    return headers


@pytest.mark.anyio
async def test_create_and_get_material(client, owner_headers):
    material = await create_material(client, owner_headers)
    assert material["code"] == "MAT-STL-01"
    assert material["category"] == "steel"
    assert material["prices"] == []

    resp = await client.get(f"/api/v1/admin/materials/{material['id']}", headers=owner_headers)
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_duplicate_code_conflict(client, owner_headers):
    await create_material(client, owner_headers)
    resp = await client.post(
        "/api/v1/admin/materials",
        json={"name": "Other", "code": "MAT-STL-01", "category": "steel", "unit": "kg"},
        headers=owner_headers,
    )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_price_history_append_only(client, owner_headers):
    from datetime import UTC, datetime, timedelta

    material = await create_material(client, owner_headers)
    base = datetime.now(UTC) - timedelta(days=10)

    r1 = await client.post(
        f"/api/v1/admin/materials/{material['id']}/prices",
        json={"unit_price_minor": 120000, "effective_from": base.isoformat()},
        headers=owner_headers,
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/admin/materials/{material['id']}/prices",
        json={"unit_price_minor": 135000},
        headers=owner_headers,
    )
    assert r2.status_code == 201

    detail = (await client.get(f"/api/v1/admin/materials/{material['id']}", headers=owner_headers)).json()
    assert len(detail["prices"]) == 2
    # Newest effective first.
    assert detail["prices"][0]["unit_price_minor"] == 135000


@pytest.mark.anyio
async def test_same_effective_from_rejected(client, owner_headers):
    from datetime import UTC, datetime

    material = await create_material(client, owner_headers)
    at = datetime.now(UTC)
    payload = {"unit_price_minor": 100, "effective_from": at.isoformat()}
    assert (
        await client.post(f"/api/v1/admin/materials/{material['id']}/prices", json=payload, headers=owner_headers)
    ).status_code == 201
    resp = await client.post(f"/api/v1/admin/materials/{material['id']}/prices", json=payload, headers=owner_headers)
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "role,status_code",
    [("owner", 201), ("admin", 201), ("sales", 403), ("content", 403), ("worker", 403), ("customer", 403)],
)
@pytest.mark.anyio
async def test_material_create_rbac(client, auth_header_factory, role, status_code):
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post(
        "/api/v1/admin/materials",
        json={"name": "M", "code": f"MAT-{role.upper()}-1", "category": "wood", "unit": "meter"},
        headers=headers,
    )
    assert resp.status_code == status_code


@pytest.mark.anyio
async def test_worker_can_read_materials(client, auth_header_factory, owner_headers):
    """WORKER keeps read access to materials for production context."""
    await create_material(client, owner_headers)
    worker_headers, _user = await auth_header_factory(role="worker")
    resp = await client.get("/api/v1/admin/materials", headers=worker_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.anyio
async def test_negative_price_rejected(client, owner_headers):
    material = await create_material(client, owner_headers)
    resp = await client.post(
        f"/api/v1/admin/materials/{material['id']}/prices",
        json={"unit_price_minor": -5},
        headers=owner_headers,
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_update_material_fields(client, owner_headers):
    material = await create_material(client, owner_headers)
    resp = await client.patch(
        f"/api/v1/admin/materials/{material['id']}",
        json={"is_active": False, "notes": "Supplier changed"},
        headers=owner_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert body["notes"] == "Supplier changed"

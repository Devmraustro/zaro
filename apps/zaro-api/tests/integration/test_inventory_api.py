"""Integration tests for the inventory endpoints."""

import uuid
from decimal import Decimal

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def owner_headers(auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    return headers


@pytest.fixture
async def customer_headers(auth_header_factory):
    headers, _user = await auth_header_factory(role="customer")
    return headers


@pytest.fixture
async def material(client, owner_headers):
    resp = await client.post(
        "/api/v1/admin/materials",
        json={"name": "Api Steel", "code": "API-STL-01", "category": "steel", "unit": "kg"},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _purchase_payload(material_id, quantity="10", key=None):
    return {
        "material_id": material_id,
        "quantity": quantity,
        "idempotency_key": key or str(uuid.uuid4()),
        "reference_type": "purchase_order",
        "unit_price_minor": 5000,
    }


@pytest.mark.anyio
async def test_purchase_and_stock_level(client, owner_headers, material):
    resp = await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"]),
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert Decimal(body["stock_level"]["on_hand"]) == Decimal("10")

    resp = await client.get(f"/api/v1/admin/inventory/{material['id']}", headers=owner_headers)
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["on_hand"]) == Decimal("10")


@pytest.mark.anyio
async def test_purchase_idempotent_replay_returns_same_movement(client, owner_headers, material):
    key = str(uuid.uuid4())
    first = await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"], key=key),
        headers=owner_headers,
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"], key=key),
        headers=owner_headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["movement_id"] == first.json()["movement_id"]
    assert Decimal(second.json()["stock_level"]["on_hand"]) == Decimal("10")


@pytest.mark.anyio
async def test_purchase_key_reuse_with_different_payload_conflicts(client, owner_headers, material):
    key = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"], quantity="10", key=key),
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"], quantity="5", key=key),
        headers=owner_headers,
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.anyio
async def test_reserve_release_consume_cycle(client, owner_headers, material):
    await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"], quantity="20"),
        headers=owner_headers,
    )
    ref = str(uuid.uuid4())
    base = {
        "material_id": material["id"],
        "reference_type": "production_order",
        "reference_id": ref,
    }
    resp = await client.post(
        "/api/v1/admin/inventory/reserve",
        json={**base, "quantity": "12", "idempotency_key": str(uuid.uuid4())},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    assert Decimal(resp.json()["stock_level"]["reserved"]) == Decimal("12")

    resp = await client.post(
        "/api/v1/admin/inventory/consume",
        json={**base, "quantity": "10", "idempotency_key": str(uuid.uuid4())},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    sl = resp.json()["stock_level"]
    assert (Decimal(sl["on_hand"]), Decimal(sl["reserved"])) == (Decimal("10"), Decimal("2"))

    resp = await client.post(
        "/api/v1/admin/inventory/return",
        json={**base, "quantity": "2", "idempotency_key": str(uuid.uuid4())},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    # RETURN restores availability without minting stock.
    sl = resp.json()["stock_level"]
    assert (Decimal(sl["on_hand"]), Decimal(sl["reserved"])) == (Decimal("10"), Decimal("0"))


@pytest.mark.anyio
async def test_adjust_accepts_negative_quantity(client, owner_headers, material):
    await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"], quantity="10"),
        headers=owner_headers,
    )
    resp = await client.post(
        "/api/v1/admin/inventory/adjust",
        json={
            "material_id": material["id"],
            "quantity": "-3",
            "idempotency_key": str(uuid.uuid4()),
            "notes": "recount",
        },
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    assert Decimal(resp.json()["stock_level"]["on_hand"]) == Decimal("7")


@pytest.mark.anyio
async def test_movements_route_not_shadowed_by_material_detail(client, owner_headers, material):
    """Regression: /movements must not be captured by /{material_id}."""
    await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"]),
        headers=owner_headers,
    )
    resp = await client.get("/api/v1/admin/inventory/movements", headers=owner_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1


@pytest.mark.anyio
async def test_movements_unknown_type_returns_422(client, owner_headers):
    resp = await client.get("/api/v1/admin/inventory/movements?movement_type=bogus", headers=owner_headers)
    assert resp.status_code == 422, resp.text


@pytest.mark.anyio
async def test_stock_level_unknown_material_404(client, owner_headers):
    resp = await client.get(f"/api/v1/admin/inventory/{uuid.uuid4()}", headers=owner_headers)
    assert resp.status_code == 404, resp.text


@pytest.mark.anyio
async def test_customer_cannot_manage_inventory(client, customer_headers, material):
    resp = await client.post(
        "/api/v1/admin/inventory/purchase",
        json=_purchase_payload(material["id"]),
        headers=customer_headers,
    )
    assert resp.status_code == 403, resp.text

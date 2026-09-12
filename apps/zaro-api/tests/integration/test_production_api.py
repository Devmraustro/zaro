"""Integration tests for the production endpoints (full lifecycle)."""

import uuid
from datetime import UTC, datetime, timedelta

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
async def material(client, owner_headers):
    resp = await client.post(
        "/api/v1/admin/materials",
        json={"name": "Api Pine", "code": "API-PINE-01", "category": "wood", "unit": "piece"},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def confirmed_order_id(db_session):
    """Seed a CONFIRMED order through the real commerce services."""
    from app.models.customer import Customer
    from app.models.enums import QuoteStatus
    from app.services import orders_service, quotes_service

    customer = Customer(full_name="API Prod", email="api-prod@example.com")
    db_session.add(customer)
    await db_session.commit()
    quote = await quotes_service.create_quote(
        db_session,
        customer_id=customer.id,
        custom_request_id=None,
        lines=[
            quotes_service.QuoteLineInput.build(
                description="Bench", quantity=1, unit_label="pcs", unit_price_minor=20000
            )
        ],
        valid_until=datetime.now(UTC) + timedelta(days=7),
    )
    quote = await quotes_service.change_status(db_session, quote, QuoteStatus.SENT)
    quote = await quotes_service.change_status(db_session, quote, QuoteStatus.ACCEPTED)
    order = await orders_service.create_from_quote(db_session, quote)
    order = await orders_service.apply_confirmed_deposit(db_session, order, amount_minor=order.deposit_required_minor)
    await db_session.commit()
    return str(order.id)


@pytest.fixture
async def stocked(client, owner_headers, material):
    resp = await client.post(
        "/api/v1/admin/inventory/purchase",
        json={
            "material_id": material["id"],
            "quantity": "50",
            "idempotency_key": str(uuid.uuid4()),
            "reference_type": "purchase_order",
        },
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    return material


@pytest.mark.anyio
async def test_full_lifecycle_via_api(client, owner_headers, stocked, confirmed_order_id, auth_header_factory):
    # create
    resp = await client.post(
        "/api/v1/admin/production",
        json={"order_id": confirmed_order_id},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    po = resp.json()
    assert po["status"] == "pending"
    po_id = po["id"]

    # plan
    resp = await client.post(
        f"/api/v1/admin/production/{po_id}/plan",
        json={
            "requirements": [
                {
                    "material_id": stocked["id"],
                    "quantity": "8",
                    "unit_price_minor": 1000,
                    "material_spec": "kiln dried",
                }
            ]
        },
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text

    # reserve
    resp = await client.post(
        f"/api/v1/admin/production/{po_id}/reserve",
        json={},
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "materials_reserved"

    # detail shows the reservation rows
    resp = await client.get(f"/api/v1/admin/production/{po_id}", headers=owner_headers)
    assert resp.status_code == 200, resp.text
    reservations = resp.json()["material_reservations"]
    assert len(reservations) == 1
    mr_id = reservations[0]["id"]
    assert reservations[0]["material_code"] == "API-PINE-01"

    # start -> the acting user is recorded as the assigned worker
    resp = await client.post(f"/api/v1/admin/production/{po_id}/start", json={}, headers=owner_headers)
    assert resp.status_code == 200, resp.text

    # consume everything
    resp = await client.post(
        f"/api/v1/admin/production/{po_id}/consume",
        json={
            "material_reservation_id": mr_id,
            "quantity": "8",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text

    # QC round: the owner who started production is the assigned worker, so
    # their own QC attempt is rejected (segregation of duties).
    resp = await client.post(f"/api/v1/admin/production/{po_id}/qc/start", json={}, headers=owner_headers)
    assert resp.status_code == 403, resp.text

    # A separate, authorized inspector runs the QC round.
    inspector_headers, _ = await auth_header_factory(role="production")
    resp = await client.post(f"/api/v1/admin/production/{po_id}/qc/start", json={}, headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        f"/api/v1/admin/production/{po_id}/qc/submit",
        json={"approved": True, "notes": "looks good"},
        headers=inspector_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ready"

    # complete
    resp = await client.post(f"/api/v1/admin/production/{po_id}/complete", json={}, headers=owner_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"


@pytest.mark.anyio
async def test_qc_requires_materials_accounted(client, owner_headers, stocked, confirmed_order_id, auth_header_factory):
    resp = await client.post(
        "/api/v1/admin/production",
        json={"order_id": confirmed_order_id},
        headers=owner_headers,
    )
    po_id = resp.json()["id"]
    await client.post(
        f"/api/v1/admin/production/{po_id}/plan",
        json={"requirements": [{"material_id": stocked["id"], "quantity": "8", "unit_price_minor": 1000}]},
        headers=owner_headers,
    )
    await client.post(f"/api/v1/admin/production/{po_id}/reserve", json={}, headers=owner_headers)
    await client.post(f"/api/v1/admin/production/{po_id}/start", json={}, headers=owner_headers)

    # The owner who started production is the assigned worker: their own QC
    # attempt is rejected by segregation of duties before material accounting
    # is evaluated.
    resp = await client.post(f"/api/v1/admin/production/{po_id}/qc/start", json={}, headers=owner_headers)
    assert resp.status_code == 403, resp.text

    # An independent inspector hits the material-accounting gate: open
    # reservations block the start of QC.
    inspector_headers, _ = await auth_header_factory(role="production")
    resp = await client.post(f"/api/v1/admin/production/{po_id}/qc/start", json={}, headers=inspector_headers)
    assert resp.status_code == 422, resp.text


@pytest.mark.anyio
async def test_double_create_conflicts(client, owner_headers, confirmed_order_id):
    resp = await client.post(
        "/api/v1/admin/production",
        json={"order_id": confirmed_order_id},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/api/v1/admin/production",
        json={"order_id": confirmed_order_id},
        headers=owner_headers,
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.anyio
async def test_create_from_unknown_order_404(client, owner_headers):
    resp = await client.post(
        "/api/v1/admin/production",
        json={"order_id": str(uuid.uuid4())},
        headers=owner_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.anyio
async def test_customer_cannot_manage_production(client, auth_header_factory, confirmed_order_id):
    headers, _ = await auth_header_factory(role="customer")
    resp = await client.post(
        "/api/v1/admin/production",
        json={"order_id": confirmed_order_id},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text

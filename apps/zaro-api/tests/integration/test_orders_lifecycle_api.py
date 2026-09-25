"""Integration tests for order confirm / deposit HTTP endpoints (admin surface).

Covers the two service-backed transitions PENDING_DEPOSIT -> CONFIRMED that
produce cannot start without: ``/admin/orders/{id}/confirm`` (net terms) and
``/admin/orders/{id}/deposit`` (record a confirmed deposit).
"""

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
async def pending_order_id(db_session):
    """Seed a PENDING_DEPOSIT order through the real commerce services."""
    from app.models.customer import Customer
    from app.models.enums import QuoteStatus
    from app.services import orders_service, quotes_service

    customer = Customer(full_name="API Order", email=f"order-{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(customer)
    await db_session.commit()
    quote = await quotes_service.create_quote(
        db_session,
        customer_id=customer.id,
        custom_request_id=None,
        lines=[
            quotes_service.QuoteLineInput.build(
                description="Table", quantity=1, unit_label="pcs", unit_price_minor=100000
            )
        ],
        valid_until=datetime.now(UTC) + timedelta(days=7),
    )
    quote = await quotes_service.change_status(db_session, quote, QuoteStatus.SENT)
    quote = await quotes_service.change_status(db_session, quote, QuoteStatus.ACCEPTED)
    order = await orders_service.create_from_quote(db_session, quote)
    await db_session.commit()
    return str(order.id)


async def _audit_entries(client, owner_headers, action: str, resource_id: str) -> list[dict]:
    logs = (await client.get("/api/v1/audit/logs", headers=owner_headers, params={"page_size": 100})).json()["items"]
    return [e for e in logs if e["action"] == action and e["resource_id"] == resource_id]


# --- Confirm (no deposit / net terms) ----------------------------------------


@pytest.mark.anyio
async def test_confirm_without_deposit(client, owner_headers, pending_order_id):
    resp = await client.post(f"/api/v1/admin/orders/{pending_order_id}/confirm", headers=owner_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_at"] is not None
    assert body["deposit_paid_minor"] == 0

    entries = await _audit_entries(client, owner_headers, "ORDER_STATUS_CHANGED", pending_order_id)
    assert entries, "expected ORDER_STATUS_CHANGED audit entry"
    meta = entries[0]["metadata"]
    assert meta["old_status"] == "pending_deposit"
    assert meta["new_status"] == "confirmed"
    assert meta["method"] == "confirm_without_deposit"


@pytest.mark.anyio
async def test_confirm_unknown_order_404(client, owner_headers):
    resp = await client.post(f"/api/v1/admin/orders/{uuid.uuid4()}/confirm", headers=owner_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_confirm_on_confirmed_order_conflicts(client, owner_headers, pending_order_id):
    first = await client.post(f"/api/v1/admin/orders/{pending_order_id}/confirm", headers=owner_headers)
    assert first.status_code == 200, first.text
    second = await client.post(f"/api/v1/admin/orders/{pending_order_id}/confirm", headers=owner_headers)
    assert second.status_code == 409


@pytest.mark.anyio
async def test_confirm_unlocks_production_via_http(client, owner_headers, pending_order_id):
    # Production orders can only be created from CONFIRMED orders, and the only
    # HTTP path to CONFIRMED is the admin confirm/deposit surface. Closing loop:
    resp = await client.post(f"/api/v1/admin/orders/{pending_order_id}/confirm", headers=owner_headers)
    assert resp.status_code == 200, resp.text

    create = await client.post("/api/v1/admin/production", json={"order_id": pending_order_id}, headers=owner_headers)
    assert create.status_code == 201, create.text
    assert create.json()["status"] == "pending"


# --- Deposit recording -------------------------------------------------------


@pytest.mark.anyio
async def test_full_deposit_confirms_order(client, owner_headers, pending_order_id):
    resp = await client.post(
        f"/api/v1/admin/orders/{pending_order_id}/deposit", json={"amount_minor": 40000}, headers=owner_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["deposit_paid_minor"] == 40000
    assert body["balance_due_minor"] == 60000
    assert body["confirmed_at"] is not None

    entries = await _audit_entries(client, owner_headers, "ORDER_DEPOSIT_RECORDED", pending_order_id)
    assert entries, "expected ORDER_DEPOSIT_RECORDED audit entry"
    meta = entries[0]["metadata"]
    assert meta["amount_minor"] == 40000
    assert meta["old_status"] == "pending_deposit"
    assert meta["new_status"] == "confirmed"


@pytest.mark.anyio
async def test_partial_deposit_keeps_pending(client, owner_headers, pending_order_id):
    resp = await client.post(
        f"/api/v1/admin/orders/{pending_order_id}/deposit", json={"amount_minor": 10000}, headers=owner_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending_deposit"
    assert body["deposit_paid_minor"] == 10000
    assert body["balance_due_minor"] == 90000
    assert body["confirmed_at"] is None


@pytest.mark.anyio
async def test_deposit_exceeding_total_rejected(client, owner_headers, pending_order_id):
    resp = await client.post(
        f"/api/v1/admin/orders/{pending_order_id}/deposit", json={"amount_minor": 200000}, headers=owner_headers
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.anyio
async def test_deposit_extra_fields_forbidden(client, owner_headers, pending_order_id):
    resp = await client.post(
        f"/api/v1/admin/orders/{pending_order_id}/deposit",
        json={"amount_minor": 40000, "status": "confirmed"},
        headers=owner_headers,
    )
    assert resp.status_code == 422


# --- RBAC --------------------------------------------------------------------


@pytest.mark.parametrize(
    "role,status_code",
    [("owner", 200), ("admin", 200), ("sales", 403), ("production", 403), ("worker", 403), ("customer", 403)],
)
@pytest.mark.anyio
async def test_confirm_rbac(client, auth_header_factory, pending_order_id, role, status_code):
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post(f"/api/v1/admin/orders/{pending_order_id}/confirm", headers=headers)
    assert resp.status_code == status_code


@pytest.mark.parametrize(
    "role,status_code",
    [("owner", 200), ("admin", 200), ("sales", 403), ("production", 403), ("worker", 403), ("customer", 403)],
)
@pytest.mark.anyio
async def test_deposit_rbac(client, auth_header_factory, pending_order_id, role, status_code):
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post(
        f"/api/v1/admin/orders/{pending_order_id}/deposit", json={"amount_minor": 40000}, headers=headers
    )
    assert resp.status_code == status_code

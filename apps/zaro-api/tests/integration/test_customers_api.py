"""Integration tests for customer management + privacy RBAC."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def owner_headers(auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    return headers


async def create_customer(client, headers, email=None, phone=None) -> dict:
    payload = {"full_name": "Amine Belkacem", "city": "Alger"}
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone
    resp = await client.post("/api/v1/admin/customers", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.anyio
async def test_create_and_list(client, owner_headers):
    customer = await create_customer(client, owner_headers, email="amine@example.com", phone="0550112233")
    assert customer["status"] == "active"
    assert customer["email"] == "amine@example.com"

    listing = (await client.get("/api/v1/admin/customers", headers=owner_headers)).json()
    assert listing["total"] == 1

    found = (await client.get("/api/v1/admin/customers", params={"search": "Belkacem"}, headers=owner_headers)).json()
    assert found["total"] == 1


@pytest.mark.anyio
async def test_duplicate_email_conflict(client, owner_headers):
    await create_customer(client, owner_headers, email="dup@example.com")
    resp = await client.post(
        "/api/v1/admin/customers",
        json={"full_name": "Other Person", "email": "dup@example.com"},
        headers=owner_headers,
    )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_update_and_block(client, owner_headers):
    customer = await create_customer(client, owner_headers)
    resp = await client.patch(
        f"/api/v1/admin/customers/{customer['id']}",
        json={"status": "blocked", "notes": "Chargeback risk"},
        headers=owner_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"


@pytest.mark.parametrize(
    "role,status_code",
    [
        ("owner", 200),
        ("admin", 200),
        ("sales", 200),
        ("accounting", 200),
        ("content", 403),  # privacy: catalog staff never see customers
        ("production", 403),
        ("worker", 403),
        ("customer", 403),
    ],
)
@pytest.mark.anyio
async def test_customer_read_rbac(client, auth_header_factory, role, status_code):
    owner = await auth_header_factory(role="owner")
    await create_customer(client, owner[0])
    headers, _user = await auth_header_factory(role=role)
    resp = await client.get("/api/v1/admin/customers", headers=headers)
    assert resp.status_code == status_code


@pytest.mark.parametrize(
    "role,status_code",
    [("sales", 201), ("content", 403), ("worker", 403), ("production", 403)],
)
@pytest.mark.anyio
async def test_customer_create_rbac(client, auth_header_factory, role, status_code):
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post(
        "/api/v1/admin/customers",
        json={"full_name": f"Person {role}"},
        headers=headers,
    )
    assert resp.status_code == status_code

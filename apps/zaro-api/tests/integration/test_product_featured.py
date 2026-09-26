"""Integration tests for the admin ``is_featured`` write path.

``Product.is_featured`` has existed as a column since migration 0004 and is
already read by the public ``?featured=true`` filter, but it had no admin
write path. These tests pin the behaviour that was added:

- create may set it, default is ``False``;
- update may set AND clear it (the ``exclude_unset`` interaction is the
  subtle part: an explicit ``false`` must persist, an absent key must not);
- featured writes go through the existing catalog permission matrix and
  leave the existing ``PRODUCT_UPDATED`` audit trail.
"""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --- Helpers ------------------------------------------------------------------


async def create_product(client, headers, *, name="Atlas Dining Table", **extra) -> dict:
    payload = {"name": name, **extra}
    resp = await client.post("/api/v1/admin/products", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def publish(client, headers, product: dict) -> dict:
    await client.post(
        f"/api/v1/admin/products/{product['id']}/price",
        json={"selling_price_minor": 14900000},
        headers=headers,
    )
    resp = await client.post(f"/api/v1/admin/products/{product['id']}/publish", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def owner_headers_factory(auth_header_factory):
    async def _make():
        headers, _user = await auth_header_factory(role="owner")
        return headers

    return _make


# --- Create -------------------------------------------------------------------


@pytest.mark.anyio
async def test_is_featured_defaults_to_false(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    assert product["is_featured"] is False


@pytest.mark.anyio
async def test_create_accepts_is_featured_true(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner, is_featured=True)
    assert product["is_featured"] is True

    fetched = await client.get(f"/api/v1/admin/products/{product['id']}", headers=owner)
    assert fetched.json()["is_featured"] is True


# --- Update -------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_can_feature_a_product(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)

    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}",
        json={"is_featured": True},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_featured"] is True


@pytest.mark.anyio
async def test_update_can_unfeature_a_product(client, owner_headers_factory):
    """Regression guard: an explicit ``false`` must clear the flag.

    ``update_product`` skips ``None`` values, so a naive implementation would
    silently ignore the request to un-feature a product.
    """
    owner = await owner_headers_factory()
    product = await create_product(client, owner, is_featured=True)

    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}",
        json={"is_featured": False},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_featured"] is False

    fetched = await client.get(f"/api/v1/admin/products/{product['id']}", headers=owner)
    assert fetched.json()["is_featured"] is False


@pytest.mark.anyio
async def test_update_omitting_is_featured_leaves_it_unchanged(client, owner_headers_factory):
    """Absent keys must not clobber the flag (partial-update contract)."""
    owner = await owner_headers_factory()
    product = await create_product(client, owner, is_featured=True)

    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}",
        json={"description": "Solid oak dining table"},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_featured"] is True


@pytest.mark.anyio
async def test_featured_update_survives_alongside_other_fields(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)

    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}",
        json={"name": "Atlas Table Renamed", "is_featured": True},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Atlas Table Renamed"
    assert body["is_featured"] is True


# --- Public behaviour ----------------------------------------------------------


@pytest.mark.anyio
async def test_public_featured_filter_uses_written_flag(client, owner_headers_factory):
    """The write path must actually drive the existing public filter."""
    owner = await owner_headers_factory()
    featured = await create_product(client, owner, name="Featured Table", is_featured=True)
    ordinary = await create_product(client, owner, name="Ordinary Chair")
    await publish(client, owner, featured)
    await publish(client, owner, ordinary)

    resp = await client.get("/api/v1/products?featured=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_featured"] is True
    assert body["items"][0]["name"] == "Featured Table"

    unfiltered = await client.get("/api/v1/products")
    assert unfiltered.json()["total"] == 2


@pytest.mark.anyio
async def test_unfeaturing_removes_product_from_public_featured_filter(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner, is_featured=True)
    await publish(client, owner, product)

    assert (await client.get("/api/v1/products?featured=true")).json()["total"] == 1

    await client.patch(
        f"/api/v1/admin/products/{product['id']}",
        json={"is_featured": False},
        headers=owner,
    )

    assert (await client.get("/api/v1/products?featured=true")).json()["total"] == 0
    assert (await client.get("/api/v1/products")).json()["total"] == 1


# --- Audit --------------------------------------------------------------------


@pytest.mark.anyio
async def test_featured_change_is_recorded_in_existing_audit_event(client, db_session, owner_headers_factory):
    from sqlalchemy import select

    from app.models.audit_log import AuditLog

    owner = await owner_headers_factory()
    product = await create_product(client, owner)

    await client.patch(
        f"/api/v1/admin/products/{product['id']}",
        json={"is_featured": True},
        headers=owner,
    )

    rows = (await db_session.execute(select(AuditLog).where(AuditLog.action == "PRODUCT_UPDATED"))).scalars().all()
    updated = [r for r in rows if r.resource_id == product["id"]]
    assert len(updated) == 1
    assert updated[0].result == "SUCCESS"
    assert updated[0].metadata_json["fields"] == ["is_featured"]


# --- RBAC ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "role,status_code",
    [
        ("owner", 200),
        ("admin", 200),
        ("sales", 403),
        ("content", 403),
        ("production", 403),
        ("worker", 403),
        ("customer", 403),
    ],
)
@pytest.mark.anyio
async def test_featured_update_rbac(client, auth_header_factory, role, status_code):
    """Featuring is catalog work: it obeys the existing products.update matrix."""
    owner_headers, _ = await auth_header_factory(role="owner")
    product = await create_product(client, owner_headers)

    headers, _user = await auth_header_factory(role=role)
    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}",
        json={"is_featured": True},
        headers=headers,
    )
    assert resp.status_code == status_code


@pytest.mark.parametrize(
    "role,status_code",
    [
        ("owner", 201),
        ("admin", 201),
        ("sales", 403),
        ("content", 403),
        ("worker", 403),
    ],
)
@pytest.mark.anyio
async def test_create_with_is_featured_rbac(client, auth_header_factory, role, status_code):
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post(
        "/api/v1/admin/products",
        json={"name": "Featured Probe", "is_featured": True},
        headers=headers,
    )
    assert resp.status_code == status_code

"""Integration tests for catalog endpoints (public + admin)."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --- Helpers ------------------------------------------------------------------


async def create_category(client, auth_headers, name="Tables") -> dict:
    resp = await client.post("/api/v1/admin/categories", json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_product(client, auth_headers, category_id=None, name="Atlas Dining Table") -> dict:
    payload = {
        "name": name,
        "description": "Solid oak dining table",
        "dimensions": {"width": 180, "height": 75, "depth": 90, "unit": "cm"},
        "materials_spec": [{"name": "Oak", "finish": "natural"}],
    }
    if category_id:
        payload["category_id"] = category_id
    resp = await client.post("/api/v1/admin/products", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def set_price(client, auth_headers, product_id, price_minor=14900000):
    resp = await client.post(
        f"/api/v1/admin/products/{product_id}/price",
        json={"selling_price_minor": price_minor},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def owner_headers_factory(auth_header_factory):
    async def _make():
        headers, _user = await auth_header_factory(role="owner")
        return headers

    return _make


# --- Public listing -----------------------------------------------------------


@pytest.mark.anyio
async def test_public_listing_empty(client):
    resp = await client.get("/api/v1/products")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.anyio
async def test_draft_products_hidden_from_public(client, app_factory, owner_headers_factory):
    client = client
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    assert product["status"] == "draft"

    resp = await client.get("/api/v1/products")
    assert resp.json()["total"] == 0

    detail = await client.get(f"/api/v1/products/{product['slug']}")
    assert detail.status_code == 404


@pytest.mark.anyio
async def test_publish_flow_and_public_visibility(client, owner_headers_factory):
    owner = await owner_headers_factory()
    category = await create_category(client, owner)
    product = await create_product(client, owner, category_id=category["id"])

    # Publish without price must fail.
    resp = await client.post(f"/api/v1/admin/products/{product['id']}/publish", headers=owner)
    assert resp.status_code == 422

    await set_price(client, owner, product["id"])
    resp = await client.post(f"/api/v1/admin/products/{product['id']}/publish", headers=owner)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    listing = await client.get("/api/v1/products")
    body = listing.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["product_code"].startswith("ZAR-TAB-")
    assert item["selling_price_minor"] == 14900000
    # No cost/internal fields leak into public payloads:
    assert "created_by" not in item
    assert "status" not in item

    detail = await client.get(f"/api/v1/products/{product['slug']}")
    assert detail.status_code == 200


@pytest.mark.anyio
async def test_product_code_sequencing_per_category(client, owner_headers_factory):
    owner = await owner_headers_factory()
    tables = await create_category(client, owner, name="Tables")
    chairs = await create_category(client, owner, name="Chairs")

    p1 = await create_product(client, owner, category_id=tables["id"], name="Table One")
    p2 = await create_product(client, owner, category_id=tables["id"], name="Table Two")
    c1 = await create_product(client, owner, category_id=chairs["id"], name="Chair One")
    no_cat = await create_product(client, owner, name="Mystery Item")

    assert p1["product_code"] == "ZAR-TAB-001"
    assert p2["product_code"] == "ZAR-TAB-002"
    assert c1["product_code"] == "ZAR-CHA-001"
    assert no_cat["product_code"] == "ZAR-GEN-001"


@pytest.mark.anyio
async def test_slug_uniquification(client, owner_headers_factory):
    owner = await owner_headers_factory()
    p1 = await create_product(client, owner, name="Same Name")
    p2 = await create_product(client, owner, name="Same Name")
    p3 = await create_product(client, owner, name="Same Name")
    slugs = {p1["slug"], p2["slug"], p3["slug"]}
    assert len(slugs) == 3
    assert p2["slug"] == "same-name-2"


@pytest.mark.anyio
async def test_filters_sort_pagination(client, owner_headers_factory):
    owner = await owner_headers_factory()
    cat_a = await create_category(client, owner, name="Alpha")
    cat_b = await create_category(client, owner, name="Beta")

    for i, (cat, price) in enumerate([(cat_a, 300), (cat_a, 100), (cat_b, 200), (cat_b, 500)], start=1):
        p = await create_product(client, owner, category_id=cat["id"], name=f"Item {i:02d}")
        await set_price(client, owner, p["id"], price)
        await client.post(f"/api/v1/admin/products/{p['id']}/publish", headers=owner)

    resp = await client.get("/api/v1/products", params={"sort": "price_asc"})
    prices = [i["selling_price_minor"] for i in resp.json()["items"]]
    assert prices == [100, 200, 300, 500]

    resp = await client.get("/api/v1/products", params={"category": cat_b["slug"], "sort": "price_desc"})
    items = resp.json()["items"]
    assert len(items) == 2
    assert [i["selling_price_minor"] for i in items] == [500, 200]

    resp = await client.get("/api/v1/products", params={"search": "Item 03"})
    assert resp.json()["total"] == 1

    resp = await client.get("/api/v1/products", params={"page": 2, "page_size": 3})
    body = resp.json()
    assert body["page"] == 2
    assert len(body["items"]) == 1
    assert body["has_previous"] is True
    assert body["has_next"] is False


@pytest.mark.anyio
async def test_archive_hides_from_public(client, owner_headers_factory):
    owner = await owner_headers_factory()
    p = await create_product(client, owner)
    await set_price(client, owner, p["id"])
    await client.post(f"/api/v1/admin/products/{p['id']}/publish", headers=owner)
    resp = await client.post(f"/api/v1/admin/products/{p['id']}/archive", headers=owner)
    assert resp.status_code == 200
    assert (await client.get("/api/v1/products")).json()["total"] == 0
    # Re-publishing an archived product is rejected.
    resp = await client.post(f"/api/v1/admin/products/{p['id']}/publish", headers=owner)
    assert resp.status_code == 409


# --- Mass assignment & protected fields ----------------------------------------


@pytest.mark.anyio
async def test_mass_assignment_rejected_on_create(client, owner_headers_factory):
    owner = await owner_headers_factory()
    resp = await client.post(
        "/api/v1/admin/products",
        json={
            "name": "Hack Attempt",
            "product_code": "ZAR-HCK-999",
            "status": "active",
            "selling_price_minor": 1,
            "slug": "hacked",
        },
        headers=owner,
    )
    # extra fields are structurally rejected -- protected fields unreachable.
    assert resp.status_code == 422
    listing = await client.get("/api/v1/admin/products", headers=owner)
    assert listing.json()["total"] == 0


@pytest.mark.anyio
async def test_update_cannot_change_protected_fields(client, owner_headers_factory):
    owner = await owner_headers_factory()
    p = await create_product(client, owner)
    resp = await client.patch(
        f"/api/v1/admin/products/{p['id']}",
        json={"status": "active", "product_code": "ZAR-XXX-001"},
        headers=owner,
    )
    assert resp.status_code == 422


# --- RBAC matrix ---------------------------------------------------------------


@pytest.mark.parametrize(
    "role,status_code",
    [
        ("owner", 201),
        ("admin", 201),
        ("sales", 403),
        ("content", 403),  # CONTENT has read-only product access in the RBAC matrix
        ("production", 403),
        ("worker", 403),
        ("customer", 403),
    ],
)
@pytest.mark.anyio
async def test_product_create_rbac(client, auth_header_factory, role, status_code):
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post("/api/v1/admin/products", json={"name": "RBAC Probe"}, headers=headers)
    assert resp.status_code == status_code


@pytest.mark.parametrize(
    "role,status_code",
    [
        ("owner", 200),
        ("admin", 200),
        ("content", 403),
        ("worker", 403),
    ],
)
@pytest.mark.anyio
async def test_price_management_rbac(client, auth_header_factory, role, status_code):
    owner = await auth_header_factory(role="owner")
    owner_headers = owner[0]
    p = await create_product(client, owner_headers)
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post(
        f"/api/v1/admin/products/{p['id']}/price",
        json={"selling_price_minor": 12345},
        headers=headers,
    )
    assert resp.status_code == status_code


@pytest.mark.anyio
async def test_variant_price_requires_manage_price(client, auth_header_factory):
    owner_headers, _ = await auth_header_factory(role="owner")
    admin_headers, _ = await auth_header_factory(role="admin")
    worker_headers, _ = await auth_header_factory(role="worker")
    p = await create_product(client, owner_headers)

    # Roles without products.update cannot create variants at all.
    resp = await client.post(
        f"/api/v1/admin/products/{p['id']}/variants",
        json={"label": "120cm / Black"},
        headers=worker_headers,
    )
    assert resp.status_code == 403

    # Admin (update + manage_price) can set a price override.
    resp = await client.post(
        f"/api/v1/admin/products/{p['id']}/variants",
        json={"label": "150cm / Black", "price_override_minor": 100},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["sku"].endswith("-V01")


# --- Variants -------------------------------------------------------------------


@pytest.mark.anyio
async def test_variant_effective_price_fallback(client, owner_headers_factory):
    owner = await owner_headers_factory()
    p = await create_product(client, owner)
    await set_price(client, owner, p["id"], 100000)
    await client.post(
        f"/api/v1/admin/products/{p['id']}/variants",
        json={"label": "No override"},
        headers=owner,
    )
    await client.post(
        f"/api/v1/admin/products/{p['id']}/variants",
        json={"label": "Override", "price_override_minor": 22222},
        headers=owner,
    )
    await client.post(f"/api/v1/admin/products/{p['id']}/publish", headers=owner)

    detail = (await client.get(f"/api/v1/products/{p['slug']}")).json()
    prices = {v["effective_price_minor"] for v in detail["variants"]}
    assert prices == {100000, 22222}


# --- Admin listing shows drafts --------------------------------------------------


@pytest.mark.anyio
async def test_admin_listing_includes_drafts(client, owner_headers_factory):
    owner = await owner_headers_factory()
    await create_product(client, owner)
    resp = await client.get("/api/v1/admin/products", headers=owner)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

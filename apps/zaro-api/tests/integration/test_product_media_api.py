"""Integration tests for admin product-media management (upload/update/delete)."""

import uuid

import pytest

pytestmark = pytest.mark.anyio

# A minimal but valid PNG (signature only is enough for magic-byte sniffing).
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"tEXtZaROtestpayload" * 8


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def owner_headers_factory(auth_header_factory):
    async def _make():
        headers, _user = await auth_header_factory(role="owner")
        return headers

    return _make


async def create_product(client, auth_headers, name="Atlas Media Table") -> dict:
    resp = await client.post("/api/v1/admin/products", json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def upload_media(client, headers, product_id, **kwargs):
    default_files = {"file": ("test.png", _PNG_BYTES, "image/png")}
    default_data = {"media_kind": "gallery", "alt_text": "Product shot", "sort_order": "0"}
    data = {**default_data, **{k: str(v) for k, v in kwargs.get("data", {}).items()}}
    files = kwargs.get("files", default_files)
    resp = await client.post(
        f"/api/v1/admin/products/{product_id}/media",
        files=files,
        data=data,
        headers=headers,
    )
    return resp


# --- Serialization of media into admin/public product payloads -----------------


@pytest.mark.anyio
async def test_media_appears_in_admin_and_public_serialization(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)

    resp = await upload_media(client, owner, product["id"], data={"media_kind": "hero", "alt_text": "Hero angle"})
    assert resp.status_code == 201, resp.text
    asset = resp.json()
    assert asset["purpose"] == "product_media"
    assert asset["visibility"] == "public"

    # Admin listing carries the media (not an empty array).
    listing = (await client.get("/api/v1/admin/products", headers=owner)).json()
    admin_item = next(i for i in listing["items"] if i["id"] == product["id"])
    assert len(admin_item["media"]) == 1
    assert admin_item["media"][0]["id"] == asset["id"]
    assert admin_item["media"][0]["media_kind"] == "hero"
    assert admin_item["media"][0]["alt_text"] == "Hero angle"

    # Admin single-product detail carries media too.
    detail = (await client.get(f"/api/v1/admin/products/{product['id']}", headers=owner)).json()
    assert len(detail["media"]) == 1

    # Public content endpoint serves the image bytes.
    public_resp = await client.get(f"/api/v1/files/{asset['id']}/public-content")
    assert public_resp.status_code == 200
    assert public_resp.content == _PNG_BYTES
    assert public_resp.headers["cache-control"] == "public, max-age=3600"


@pytest.mark.anyio
async def test_public_product_detail_returns_media(client, db_session, owner_headers_factory):
    """Regression: GET /products/{slug} must include PUBLIC media for the gallery."""
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    await client.post(
        f"/api/v1/admin/products/{product['id']}/price",
        json={"selling_price_minor": 14900000},
        headers=owner,
    )
    publish = await client.post(f"/api/v1/admin/products/{product['id']}/publish", headers=owner)
    assert publish.status_code == 200, publish.text

    asset = (
        await upload_media(client, owner, product["id"], data={"media_kind": "hero", "alt_text": "Hero angle"})
    ).json()

    detail = (await client.get(f"/api/v1/products/{product['slug']}")).json()
    assert len(detail["media"]) == 1
    media = detail["media"][0]
    assert media["id"] == asset["id"]
    assert media["media_kind"] == "hero"
    assert media["alt_text"] == "Hero angle"
    assert media["url_path"] == f"/api/v1/files/{asset['id']}/public-content"
    assert media["sort_order"] == 0

    # Private-only or non-product files must not leak into the public detail payload.
    from app.models.enums import FilePurpose, FileVisibility
    from app.models.file_asset import FileAsset

    db_session.add(
        FileAsset(
            id=uuid.uuid4(),
            storage_key=f"product_media/private-{uuid.uuid4().hex}.png",
            content_type="image/png",
            size_bytes=len(_PNG_BYTES),
            sha256=uuid.uuid4().hex,
            purpose=FilePurpose.PRODUCT_MEDIA,
            visibility=FileVisibility.PRIVATE,
            product_id=uuid.UUID(product["id"]),
            media_kind="detail",
            alt_text="hidden",
            sort_order=1,
        )
    )
    await db_session.commit()
    detail = (await client.get(f"/api/v1/products/{product['slug']}")).json()
    assert [m["id"] for m in detail["media"]] == [asset["id"]]


# --- Update (reorder / retitle) -------------------------------------------------


@pytest.mark.anyio
async def test_media_metadata_update(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    asset = (await upload_media(client, owner, product["id"])).json()

    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}/media/{asset['id']}",
        json={"media_kind": "lifestyle", "alt_text": "In the living room", "sort_order": 99},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["media_kind"] == "lifestyle"
    assert updated["alt_text"] == "In the living room"
    assert updated["sort_order"] == 99

    # The admin serializer reflects the new editorial order.
    detail = (await client.get(f"/api/v1/admin/products/{product['id']}", headers=owner)).json()
    assert detail["media"][0]["media_kind"] == "lifestyle"


@pytest.mark.anyio
async def test_media_update_rejects_unknown_fields(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    asset = (await upload_media(client, owner, product["id"])).json()

    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}/media/{asset['id']}",
        json={"media_kind": "lifestyle", "storage_key": "hacked/key.png"},
        headers=owner,
    )
    assert resp.status_code == 422

    resp = await client.patch(
        f"/api/v1/admin/products/{product['id']}/media/{asset['id']}",
        json={"media_kind": "hero"},
        headers=owner,
    )
    assert resp.status_code == 200
    assert resp.json()["media_kind"] == "hero"


# --- Delete -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_media_delete_removes_object_and_asset(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    asset = (await upload_media(client, owner, product["id"])).json()

    resp = await client.delete(f"/api/v1/admin/products/{product['id']}/media/{asset['id']}", headers=owner)
    assert resp.status_code == 204

    # Row gone from admin list, public content 404s.
    listing = (await client.get("/api/v1/admin/products", headers=owner)).json()
    admin_item = next(i for i in listing["items"] if i["id"] == product["id"])
    assert admin_item["media"] == []

    missing = await client.get(f"/api/v1/files/{asset['id']}/public-content")
    assert missing.status_code == 404

    # Deleting again is a 404 (idempotent by absence).
    again = await client.delete(f"/api/v1/admin/products/{product['id']}/media/{asset['id']}", headers=owner)
    assert again.status_code == 404


# --- Ownership / isolation -------------------------------------------------------


@pytest.mark.anyio
async def test_media_cannot_be_managed_through_another_product(client, owner_headers_factory):
    owner = await owner_headers_factory()
    p1 = await create_product(client, owner, name="Table One")
    p2 = await create_product(client, owner, name="Table Two")
    asset = (await upload_media(client, owner, p1["id"])).json()

    # PATCH + DELETE through the wrong product are 404 (not 403): no cross-tenant signal.
    resp = await client.patch(
        f"/api/v1/admin/products/{p2['id']}/media/{asset['id']}",
        json={"alt_text": "other"},
        headers=owner,
    )
    assert resp.status_code == 404

    resp = await client.delete(f"/api/v1/admin/products/{p2['id']}/media/{asset['id']}", headers=owner)
    assert resp.status_code == 404

    # Asset untouched on the owning product.
    detail = (await client.get(f"/api/v1/admin/products/{p1['id']}", headers=owner)).json()
    assert len(detail["media"]) == 1


# --- RBAC --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_media_mutations_require_products_update(client, auth_header_factory, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    asset = (await upload_media(client, owner, product["id"])).json()

    worker_headers, _ = await auth_header_factory(role="worker")
    content_headers, _ = await auth_header_factory(role="content")
    sales_headers, _ = await auth_header_factory(role="sales")

    for headers in (worker_headers, content_headers, sales_headers):
        patch_resp = await client.patch(
            f"/api/v1/admin/products/{product['id']}/media/{asset['id']}",
            json={"alt_text": "blocked"},
            headers=headers,
        )
        assert patch_resp.status_code == 403
        del_resp = await client.delete(f"/api/v1/admin/products/{product['id']}/media/{asset['id']}", headers=headers)
        assert del_resp.status_code == 403

    # Asset survives.
    detail = (await client.get(f"/api/v1/admin/products/{product['id']}", headers=owner)).json()
    assert len(detail["media"]) == 1


@pytest.mark.anyio
async def test_media_list_is_readable_by_products_read(client, auth_header_factory, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    await upload_media(client, owner, product["id"])

    content_headers, _ = await auth_header_factory(role="content")
    resp = await client.get(f"/api/v1/admin/products/{product['id']}/media", headers=content_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# --- Audit -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_media_actions_are_audited(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    asset = (await upload_media(client, owner, product["id"])).json()

    await client.patch(
        f"/api/v1/admin/products/{product['id']}/media/{asset['id']}",
        json={"alt_text": "audited"},
        headers=owner,
    )
    await client.delete(f"/api/v1/admin/products/{product['id']}/media/{asset['id']}", headers=owner)

    resp = await client.get("/api/v1/audit/logs", params={"action": "FILE_UPDATED"}, headers=owner)
    assert resp.status_code == 200
    actions = [entry["action"] for entry in resp.json()["items"]]
    assert "FILE_UPDATED" in actions

    resp = await client.get("/api/v1/audit/logs", params={"action": "FILE_DELETED"}, headers=owner)
    del_entries = resp.json()["items"]
    assert any(entry["resource_id"] == asset["id"] for entry in del_entries)

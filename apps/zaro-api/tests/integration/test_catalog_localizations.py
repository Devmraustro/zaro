"""Integration tests for catalog localization (admin CRUD + public resolution)."""

import pytest

pytestmark = pytest.mark.anyio

LOCALES_URL = "/api/v1"


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --- Helpers ------------------------------------------------------------------


async def create_category(client, auth_headers, name="Tables") -> dict:
    resp = await client.post(f"{LOCALES_URL}/admin/categories", json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_product(client, auth_headers, name="Atlas Dining Table") -> dict:
    payload = {"name": name, "description": "Solid oak dining table"}
    resp = await client.post(f"{LOCALES_URL}/admin/products", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def publish_product(client, auth_headers, product_id, price_minor=14900000) -> dict:
    resp = await client.post(
        f"{LOCALES_URL}/admin/products/{product_id}/price",
        json={"selling_price_minor": price_minor},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(f"{LOCALES_URL}/admin/products/{product_id}/publish", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def owner_headers_factory(auth_header_factory):
    async def _make():
        headers, _user = await auth_header_factory(role="owner")
        return headers

    return _make


# --- Admin localization CRUD --------------------------------------------------


@pytest.mark.anyio
async def test_upsert_list_and_delete_product_localization(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)

    resp = await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table Atlas", "description": "Table en chêne massif"},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["locale"] == "fr"
    assert body["name"] == "Table Atlas"

    listed = await client.get(f"{LOCALES_URL}/admin/products/{product['id']}/localizations", headers=owner)
    assert listed.status_code == 200
    assert [r["locale"] for r in listed.json()] == ["fr"]

    # Upserting again replaces in place (single row).
    resp = await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table Atlas Deux", "description": None},
        headers=owner,
    )
    assert resp.status_code == 200
    listed = await client.get(f"{LOCALES_URL}/admin/products/{product['id']}/localizations", headers=owner)
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "Table Atlas Deux"
    assert rows[0]["description"] is None

    resp = await client.delete(f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr", headers=owner)
    assert resp.status_code == 204
    listed = await client.get(f"{LOCALES_URL}/admin/products/{product['id']}/localizations", headers=owner)
    assert listed.json() == []


@pytest.mark.anyio
async def test_delete_missing_localization_returns_404(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    resp = await client.delete(f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr", headers=owner)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_localization_requires_product_update_permission(client, auth_header_factory):
    worker, _ = await auth_header_factory(role="worker")
    owner, _ = await auth_header_factory(role="owner")
    product = await create_product(client, owner)

    resp = await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table"},
        headers=worker,
    )
    assert resp.status_code == 403

    resp = await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table"},
        headers=owner,
    )
    assert resp.status_code == 200

    resp = await client.delete(f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr", headers=worker)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_invalid_locale_and_extra_fields_rejected(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)

    resp = await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/de",
        json={"name": "Tisch"},
        headers=owner,
    )
    assert resp.status_code == 422

    resp = await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table", "created_by": "hacker"},
        headers=owner,
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_category_localization_crud(client, owner_headers_factory):
    owner = await owner_headers_factory()
    category = await create_category(client, owner)

    resp = await client.put(
        f"{LOCALES_URL}/admin/categories/{category['id']}/localizations/ar",
        json={"name": "طاولات", "description": "طاولات مصنوعة يدويا"},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "طاولات"

    listed = await client.get(f"{LOCALES_URL}/admin/categories/{category['id']}/localizations", headers=owner)
    assert [r["locale"] for r in listed.json()] == ["ar"]

    resp = await client.delete(f"{LOCALES_URL}/admin/categories/{category['id']}/localizations/ar", headers=owner)
    assert resp.status_code == 204
    assert (
        await client.get(f"{LOCALES_URL}/admin/categories/{category['id']}/localizations", headers=owner)
    ).json() == []


# --- Public localized resolution ----------------------------------------------


@pytest.mark.anyio
async def test_public_detail_uses_lang_query_parameter(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    await publish_product(client, owner, product["id"])

    await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table Atlas", "description": "Table en chêne massif"},
        headers=owner,
    )

    fr = await client.get(f"{LOCALES_URL}/products/{product['slug']}?lang=fr")
    assert fr.status_code == 200
    body = fr.json()
    assert body["name"] == "Table Atlas"
    assert body["description"] == "Table en chêne massif"
    assert body["locale"] == "fr"

    # English stays canonical when no row exists for en.
    en = await client.get(f"{LOCALES_URL}/products/{product['slug']}?lang=en")
    assert en.json()["name"] == "Atlas Dining Table"

    # Missing locale falls back to canonical English.
    ar = await client.get(f"{LOCALES_URL}/products/{product['slug']}?lang=ar")
    assert ar.json()["name"] == "Atlas Dining Table"


@pytest.mark.anyio
async def test_public_detail_honors_accept_language_header(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    await publish_product(client, owner, product["id"])

    await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table Atlas"},
        headers=owner,
    )

    resp = await client.get(
        f"{LOCALES_URL}/products/{product['slug']}", headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}
    )
    assert resp.json()["name"] == "Table Atlas"


@pytest.mark.anyio
async def test_public_listing_localizes_names(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner)
    await publish_product(client, owner, product["id"])

    await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Table Atlas"},
        headers=owner,
    )

    resp = await client.get(f"{LOCALES_URL}/products?lang=fr")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["name"] == "Table Atlas"

    resp = await client.get(f"{LOCALES_URL}/products")
    assert resp.json()["items"][0]["name"] == "Atlas Dining Table"


@pytest.mark.anyio
async def test_public_search_matches_localized_names(client, owner_headers_factory):
    owner = await owner_headers_factory()
    product = await create_product(client, owner, name="Oak Shelf")
    await publish_product(client, owner, product["id"])

    await client.put(
        f"{LOCALES_URL}/admin/products/{product['id']}/localizations/fr",
        json={"name": "Étagère en chêne"},
        headers=owner,
    )

    # Term exists only in the French localization.
    found = await client.get(f"{LOCALES_URL}/products?search=chêne&lang=fr")
    assert found.status_code == 200
    assert [p["slug"] for p in found.json()["items"]] == [product["slug"]]

    # Without the locale, the same term finds nothing.
    none = await client.get(f"{LOCALES_URL}/products?search=chêne")
    assert none.json()["total"] == 0


@pytest.mark.anyio
async def test_public_categories_localize(client, owner_headers_factory):
    owner = await owner_headers_factory()
    category = await create_category(client, owner, name="Tables")
    product = await create_product(client, owner, name="Atlas Dining Table")
    await publish_product(client, owner, product["id"])

    await client.put(
        f"{LOCALES_URL}/admin/categories/{category['id']}/localizations/ar",
        json={"name": "طاولات", "description": "طاولات مصنوعة يدويا"},
        headers=owner,
    )

    ar = await client.get(f"{LOCALES_URL}/categories?lang=ar")
    assert ar.status_code == 200
    item = next(c for c in ar.json() if c["id"] == category["id"])
    assert item["name"] == "طاولات"
    assert item["description"] == "طاولات مصنوعة يدويا"

    en = await client.get(f"{LOCALES_URL}/categories")
    item = next(c for c in en.json() if c["id"] == category["id"])
    assert item["name"] == "Tables"

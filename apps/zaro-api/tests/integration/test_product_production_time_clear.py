"""Integration tests for explicit clear semantics on ``production_time_days``.

``Product.production_time_days`` is nullable, but ``update_product`` assigned
it inside a loop that treats ``None`` as "leave unchanged", so once a product
had a production time an admin could never remove it: the admin emptied the
field, the client omitted the key, ``exclude_unset=True`` dropped it, and the
stored value survived while the UI showed a blank box.

These tests pin the three states the field must distinguish:

- key absent        -> the stored value is preserved;
- explicit ``null`` -> the column is set to ``NULL``;
- an integer        -> the column is updated.

They also pin the unchanged validation contract (nullable integer, 0..3650,
no arbitrary strings).
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


async def get_product(client, headers, product_id: str) -> dict:
    resp = await client.get(f"/api/v1/admin/products/{product_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def owner_headers_factory(auth_header_factory):
    async def _make():
        headers, _user = await auth_header_factory(role="owner")
        return headers

    return _make


# --- The three states ---------------------------------------------------------


@pytest.mark.anyio
async def test_omitted_production_time_days_preserves_existing_value(client, owner_headers_factory):
    """A PATCH that never mentions the field must not disturb it."""
    owner = await owner_headers_factory()
    created = await create_product(client, owner, production_time_days=30)
    assert created["production_time_days"] == 30

    resp = await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"name": "Atlas dining table"},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text

    assert (await get_product(client, owner, created["id"]))["production_time_days"] == 30


@pytest.mark.anyio
async def test_integer_production_time_days_updates_existing_value(client, owner_headers_factory):
    owner = await owner_headers_factory()
    created = await create_product(client, owner, production_time_days=30)

    resp = await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"production_time_days": 45},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["production_time_days"] == 45

    assert (await get_product(client, owner, created["id"]))["production_time_days"] == 45


@pytest.mark.anyio
async def test_explicit_null_clears_production_time_days(client, owner_headers_factory):
    """The regression: an explicit null must write NULL, not be ignored."""
    owner = await owner_headers_factory()
    created = await create_product(client, owner, production_time_days=30)
    assert created["production_time_days"] == 30

    resp = await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"production_time_days": None},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["production_time_days"] is None

    assert (await get_product(client, owner, created["id"]))["production_time_days"] is None


@pytest.mark.anyio
async def test_null_clear_persists_and_stays_cleared_on_later_patch(client, owner_headers_factory):
    """Clearing must survive an unrelated later update."""
    owner = await owner_headers_factory()
    created = await create_product(client, owner, production_time_days=30)

    await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"production_time_days": None},
        headers=owner,
    )
    resp = await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"name": "Atlas dining table"},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["production_time_days"] is None


@pytest.mark.anyio
async def test_zero_is_a_value_not_a_clear(client, owner_headers_factory):
    """0 is inside the allowed range and must not be confused with a clear."""
    owner = await owner_headers_factory()
    created = await create_product(client, owner, production_time_days=30)

    resp = await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"production_time_days": 0},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["production_time_days"] == 0


@pytest.mark.anyio
async def test_create_still_defaults_to_null_when_omitted(client, owner_headers_factory):
    owner = await owner_headers_factory()
    created = await create_product(client, owner)
    assert created["production_time_days"] is None


# --- Validation is unchanged --------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param(-1, id="negative"),
        pytest.param(3651, id="above-max"),
        pytest.param("abc", id="arbitrary-string"),
        pytest.param("thirty", id="non-numeric-string"),
        pytest.param(1.5, id="non-integer"),
        pytest.param([30], id="array"),
    ],
)
async def test_invalid_production_time_days_still_rejected(client, owner_headers_factory, invalid):
    owner = await owner_headers_factory()
    created = await create_product(client, owner, production_time_days=30)

    resp = await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"production_time_days": invalid},
        headers=owner,
    )
    assert resp.status_code == 422, resp.text

    # A rejected payload must not have mutated anything.
    assert (await get_product(client, owner, created["id"]))["production_time_days"] == 30


@pytest.mark.anyio
async def test_boundary_values_are_accepted(client, owner_headers_factory):
    owner = await owner_headers_factory()
    created = await create_product(client, owner)

    for boundary in (0, 3650):
        resp = await client.patch(
            f"/api/v1/admin/products/{created['id']}",
            json={"production_time_days": boundary},
            headers=owner,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["production_time_days"] == boundary


# --- Authorization is unchanged ----------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["sales", "worker", "customer"])
async def test_clearing_requires_update_permission(client, auth_header_factory, role):
    headers, _ = await auth_header_factory(role=role)
    owner_headers, _ = await auth_header_factory(role="owner")
    created = await create_product(client, owner_headers, production_time_days=30)

    resp = await client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={"production_time_days": None},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text

    # Rejected by RBAC, so the value must be untouched.
    assert (await get_product(client, owner_headers, created["id"]))["production_time_days"] == 30

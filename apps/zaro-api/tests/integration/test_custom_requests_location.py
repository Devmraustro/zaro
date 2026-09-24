"""Integration tests for custom-request delivery-location wiring.

The public submission flow must accept and persist wilaya/commune/address and
reject invalid location combinations with the standard 422 validation format.
"""

import pytest

pytestmark = pytest.mark.anyio

BASE = "/api/v1/custom-requests"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _payload(**overrides) -> dict:
    payload = {
        "full_name": "Amine Belkacem",
        "email": "amine@example.com",
        "phone": "0550112233",
        "product_type": "dining_table",
        "description": "A bespoke oak dining table for a family of six.",
        "quantity": 1,
        "wilaya": "16",
        "commune": "1601",
        "address": "12 Rue Didouche Mourad, Algiers",
    }
    payload.update(overrides)
    return payload


async def test_submit_persists_location_fields(client):
    resp = await client.post(BASE, json=_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["wilaya"] == "16"
    assert body["commune"] == "1601"
    assert body["address"] == "12 Rue Didouche Mourad, Algiers"


async def test_submit_without_location_is_allowed(client):
    payload = _payload()
    payload.pop("wilaya")
    payload.pop("commune")
    payload.pop("address")
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["wilaya"] is None


async def test_invalid_wilaya_returns_validation_error(client):
    resp = await client.post(BASE, json=_payload(wilaya="99"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_commune_from_other_wilaya_rejected(client):
    # 1901 belongs to wilaya 19 (Oran), not 16 (Algiers).
    resp = await client.post(BASE, json=_payload(wilaya="16", commune="1901"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_commune_without_wilaya_rejected(client):
    payload = _payload()
    payload.pop("wilaya")
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_wilaya_schema_rejects_non_two_digit_code(client):
    resp = await client.post(BASE, json=_payload(wilaya="ABC"))
    assert resp.status_code == 422


async def test_malformed_wilaya_code_schema_rejected(client):
    resp = await client.post(BASE, json=_payload(wilaya="160"))
    assert resp.status_code == 422

"""Integration tests for the public reference-data endpoints.

These lock the explicit-join ordering fix: without the parent join the commune
query would cross-join ``communes x wilayas`` and produce duplicate rows.
"""

import pytest

pytestmark = pytest.mark.anyio

BASE = "/api/v1/references"


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_wilayas_listed_publicly_ordered(client):
    resp = await client.get(f"{BASE}/wilayas")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert body["locale"] == "en"
    assert [w["code"] for w in body["items"]] == ["16", "19", "31"]
    for item in body["items"]:
        assert item["id"]
        assert item["name"]
        assert item["locale"] == "en"


async def test_wilaya_locale_resolution(client):
    fr = (await client.get(f"{BASE}/wilayas?lang=fr")).json()
    assert fr["locale"] == "fr"
    by_code = {w["code"]: w["name"] for w in fr["items"]}
    assert by_code["16"] == "Alger"

    ar = (await client.get(f"{BASE}/wilayas", headers={"Accept-Language": "ar-DZ,ar;q=0.9,en;q=0.8"})).json()
    assert ar["locale"] == "ar"
    assert {w["code"] for w in ar["items"]} == {"16", "19", "31"}

    bad = await client.get(f"{BASE}/wilayas?lang=de")
    assert bad.status_code == 422


async def test_communes_filtered_by_wilaya(client):
    resp = await client.get(f"{BASE}/communes?wilaya=16")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["wilaya"] == "16"
    assert [c["code"] for c in body["items"]] == ["1601", "1602"]
    assert body["total"] == 2


async def test_communes_no_duplicates_and_parent_ordering(client):
    """Regression: commune list must not cross-join wilayas.

    Ordering is by parent wilaya code then commune code, and every commune row
    appears exactly once (no cartesian-product duplicates).
    """
    resp = await client.get(f"{BASE}/communes")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    codes = [c["code"] for c in body["items"]]
    assert codes == ["1601", "1602", "1901", "3101"]
    assert body["total"] == 4
    assert len({c["id"] for c in body["items"]}) == body["total"]


async def test_communes_locale_applied(client):
    body = (await client.get(f"{BASE}/communes?wilaya=16&lang=fr")).json()
    assert body["items"][0]["name"] == "Alger Centre"
    assert all(c["locale"] == "fr" for c in body["items"])

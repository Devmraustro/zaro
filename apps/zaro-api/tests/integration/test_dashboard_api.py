"""Integration tests for the admin dashboard summary + per-role gating."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def owner_headers(auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    return headers


async def submit_request(
    client,
    *,
    full_name="Amine Belkacem",
    email=None,
    phone=None,
    product_type="dining_table",
    wilaya=None,
) -> dict:
    payload = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "product_type": product_type,
        "description": "A bespoke oak dining table for a family of six.",
        "quantity": 1,
        "wilaya": wilaya,
    }
    resp = await client.post("/api/v1/custom-requests", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_dashboard_summary_aggregates_counts(client, owner_headers):
    await submit_request(client, email="a@example.com", phone="0550112233", product_type="dining_table", wilaya="16")
    await submit_request(client, email="b@example.com", phone="0660112233", product_type="desk", wilaya="31")

    summary = (await client.get("/api/v1/admin/dashboard", headers=owner_headers)).json()

    assert summary["custom_requests"]["total"] == 2
    assert summary["custom_requests"]["by_status"]["submitted"] == 2
    assert summary["custom_requests"]["pending"] == 2
    assert summary["custom_requests"]["this_week"] >= 2
    assert summary["customers_total"] == 2
    assert summary["products"]["total"] == 0
    assert summary["products"]["active"] == 0

    assert len(summary["recent_requests"]) == 2
    recent = summary["recent_requests"]
    assert {r["product_type"] for r in recent} == {"dining_table", "desk"}
    assert {r["wilaya"] for r in recent} == {"16", "31"}
    for item in recent:
        assert item["reference"].startswith("CR-")
        assert item["status"] == "submitted"
        assert item["created_at"] is not None


async def test_dashboard_requires_authentication(client):
    resp = await client.get("/api/v1/admin/dashboard")
    assert resp.status_code in (401, 403)


async def test_dashboard_gating_by_role(client, auth_header_factory):
    # A worker has PRODUCTS_READ but no customer/request access.
    worker_headers, _ = await auth_header_factory(role="worker")
    summary = (await client.get("/api/v1/admin/dashboard", headers=worker_headers)).json()

    assert "products" in summary
    assert "custom_requests" not in summary
    assert "customers_total" not in summary
    assert "recent_requests" not in summary

    # A content role sees catalog counts only.
    content_headers, _ = await auth_header_factory(role="content")
    content_summary = (await client.get("/api/v1/admin/dashboard", headers=content_headers)).json()
    assert "products" in content_summary
    assert "customers_total" not in content_summary
    assert "custom_requests" not in content_summary

"""Integration tests for custom requests: public submission, lifecycle,
ownership scoping, and inspiration file security."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


VALID_SUBMISSION = {
    "full_name": "Yasmine Haddad",
    "email": "yasmine@example.com",
    "phone": "0661223344",
    "product_type": "dining_table",
    "description": "Large oak dining table for 8 people with steel legs",
    "desired_dimensions": "220x100x75cm",
    "materials": "Oak + black steel",
    "colors": "Natural wood, matte black",
    "quantity": 1,
    "budget_min_minor": 150000000,
    "budget_max_minor": 300000000,
}


@pytest.fixture
async def owner_headers(auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    return headers


# --- Public submission --------------------------------------------------------


@pytest.mark.anyio
async def test_public_submission_creates_customer_and_request(client, owner_headers):
    resp = await client.post("/api/v1/custom-requests", json=VALID_SUBMISSION)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reference"].startswith("CR-")
    assert body["status"] == "submitted"
    # Public payload must not leak internal fields:
    assert "customer_id" not in body
    assert "notes" not in body

    # Customer record was created (dedupe by email).
    found = (
        await client.get("/api/v1/admin/customers", params={"search": "yasmine@example.com"}, headers=owner_headers)
    ).json()
    assert found["total"] == 1

    # Staff can see the full request.
    listing = (await client.get("/api/v1/admin/custom-requests", headers=owner_headers)).json()
    assert listing["total"] == 1
    admin_item = listing["items"][0]
    assert admin_item["customer_email"] == "yasmine@example.com"


@pytest.mark.anyio
async def test_submission_dedupes_customer_by_email(client, owner_headers):
    await client.post("/api/v1/custom-requests", json=VALID_SUBMISSION)
    second = {**VALID_SUBMISSION, "full_name": "Yasmine H."}
    await client.post("/api/v1/custom-requests", json=second)

    customers = (await client.get("/api/v1/admin/customers", headers=owner_headers)).json()
    assert customers["total"] == 1
    requests_list = (await client.get("/api/v1/admin/custom-requests", headers=owner_headers)).json()
    assert requests_list["total"] == 2


@pytest.mark.anyio
async def test_submission_validation(client):
    # Missing description entirely.
    resp = await client.post("/api/v1/custom-requests", json={"full_name": "X Y"})
    assert resp.status_code == 422

    # Description too short.
    resp = await client.post(
        "/api/v1/custom-requests",
        json={**VALID_SUBMISSION, "description": "short"},
    )
    assert resp.status_code == 422

    # Unknown product_type.
    resp = await client.post(
        "/api/v1/custom-requests",
        json={**VALID_SUBMISSION, "product_type": "spaceship"},
    )
    assert resp.status_code == 422

    # budget_min > budget_max.
    resp = await client.post(
        "/api/v1/custom-requests",
        json={**VALID_SUBMISSION, "budget_min_minor": 500, "budget_max_minor": 100},
    )
    assert resp.status_code == 422

    # Mass assignment attempt.
    resp = await client.post(
        "/api/v1/custom-requests",
        json={**VALID_SUBMISSION, "status": "converted", "reference": "CR-2026-9999"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_submission_rate_limited(client, app_factory):
    app = app_factory()
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        statuses = []
        for _ in range(7):
            resp = await c.post("/api/v1/custom-requests", json=VALID_SUBMISSION)
            statuses.append(resp.status_code)
        assert 429 in statuses
        assert statuses.count(201) == 5


# --- Lifecycle transitions -----------------------------------------------------


async def _submit(client) -> dict:
    return (await client.post("/api/v1/custom-requests", json=VALID_SUBMISSION)).json()


@pytest.mark.anyio
async def test_happy_path_lifecycle(client, owner_headers):
    request_obj = await _submit(client)

    async def transition(status):
        return await client.patch(
            f"/api/v1/admin/custom-requests/{request_obj['id']}/status",
            json={"status": status},
            headers=owner_headers,
        )

    assert (await transition("under_review")).json()["status"] == "under_review"
    assert (await transition("needs_information")).json()["status"] == "needs_information"
    assert (await transition("under_review")).json()["status"] == "under_review"
    assert (await transition("quotation_pending")).json()["status"] == "quotation_pending"
    final = await transition("converted")
    assert final.json()["status"] == "converted"

    # Terminal: no further transitions.
    assert (await transition("cancelled")).status_code == 400


@pytest.mark.anyio
async def test_invalid_transitions_rejected(client, owner_headers):
    request_obj = await _submit(client)
    # submitted -> converted skips review.
    resp = await client.patch(
        f"/api/v1/admin/custom-requests/{request_obj['id']}/status",
        json={"status": "converted"},
        headers=owner_headers,
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_state_transition"

    # submitted -> needs_information also invalid.
    resp = await client.patch(
        f"/api/v1/admin/custom-requests/{request_obj['id']}/status",
        json={"status": "needs_information"},
        headers=owner_headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_status_filter_admin_listing(client, owner_headers):
    await _submit(client)
    listing = (
        await client.get("/api/v1/admin/custom-requests", params={"status": "submitted"}, headers=owner_headers)
    ).json()
    assert listing["total"] == 1
    listing = (
        await client.get("/api/v1/admin/custom-requests", params={"status": "converted"}, headers=owner_headers)
    ).json()
    assert listing["total"] == 0


@pytest.mark.parametrize(
    "role,status_code",
    [("owner", 200), ("admin", 200), ("sales", 200), ("content", 403), ("production", 403), ("worker", 403)],
)
@pytest.mark.anyio
async def test_admin_listing_rbac(client, auth_header_factory, role, status_code):
    await _submit(client)
    headers, _user = await auth_header_factory(role=role)
    resp = await client.get("/api/v1/admin/custom-requests", headers=headers)
    assert resp.status_code == status_code


@pytest.mark.anyio
async def test_status_change_requires_update_permission(client, auth_header_factory):
    # SALES has custom_requests.read but we test update via a role without it.
    worker_headers, _user2 = await auth_header_factory(role="worker")
    request_obj = await _submit(client)
    resp = await client.patch(
        f"/api/v1/admin/custom-requests/{request_obj['id']}/status",
        json={"status": "under_review"},
        headers=worker_headers,
    )
    assert resp.status_code == 403


# --- Customer self-service ownership -------------------------------------------


@pytest.mark.anyio
async def test_customer_sees_own_requests_only(client, auth_header_factory):
    # Customer A account with matching email.
    user_a_headers, user_a = await auth_header_factory(role="customer")

    # Submit as customer A (email matches their account).
    submission_a = {**VALID_SUBMISSION, "email": user_a.email}
    created = (await client.post("/api/v1/custom-requests", json=submission_a)).json()

    # Customer B cannot see A's request.
    user_b_headers, _user_b = await auth_header_factory(role="customer", email="b@example.com")
    mine_b = (await client.get("/api/v1/custom-requests/mine", headers=user_b_headers)).json()
    assert mine_b == []

    detail_b = await client.get(f"/api/v1/custom-requests/{created['id']}", headers=user_b_headers)
    assert detail_b.status_code == 403

    # A sees exactly their own request.
    mine_a = (await client.get("/api/v1/custom-requests/mine", headers=user_a_headers)).json()
    assert len(mine_a) == 1
    assert mine_a[0]["reference"] == created["reference"]

    detail_a = await client.get(f"/api/v1/custom-requests/{created['id']}", headers=user_a_headers)
    assert detail_a.status_code == 200


@pytest.mark.anyio
async def test_anonymous_cannot_access_mine(client):
    resp = await client.get("/api/v1/custom-requests/mine")
    assert resp.status_code == 401


# --- Inspiration files ----------------------------------------------------------

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.anyio
async def test_inspiration_upload_and_signed_access(client, auth_header_factory):
    user_headers, user = await auth_header_factory(role="customer")
    submission = {**VALID_SUBMISSION, "email": user.email}
    created = (await client.post("/api/v1/custom-requests", json=submission)).json()

    resp = await client.post(
        f"/api/v1/custom-requests/{created['id']}/files",
        files={"file": ("inspiration.png", PNG_BYTES, "image/png")},
        headers=user_headers,
    )
    assert resp.status_code == 201, resp.text
    asset = resp.json()
    assert asset["purpose"] == "custom_request_inspiration"
    assert asset["visibility"] == "private"

    # Owner gets a signed URL...
    access = await client.get(f"/api/v1/files/{asset['id']}/access-url", headers=user_headers)
    assert access.status_code == 200
    url_path = access.json()["url_path"]
    content = await client.get(url_path)
    assert content.status_code == 200
    assert content.content.startswith(b"\x89PNG")

    # ...but a stranger does not.
    stranger_headers, _stranger = await auth_header_factory(role="customer", email="stranger@example.com")
    denied = await client.get(f"/api/v1/files/{asset['id']}/access-url", headers=stranger_headers)
    assert denied.status_code == 403

    # Direct content access without token is rejected.
    no_token = await client.get(f"/api/v1/files/{asset['id']}/content")
    assert no_token.status_code == 422  # missing query param

    # Tampered token rejected.
    tampered = await client.get(f"/api/v1/files/{asset['id']}/content?token=0|deadbeef")
    assert tampered.status_code == 403


@pytest.mark.anyio
async def test_disguised_upload_rejected(client, auth_header_factory):
    user_headers, user = await auth_header_factory(role="customer")
    submission = {**VALID_SUBMISSION, "email": user.email}
    created = (await client.post("/api/v1/custom-requests", json=submission)).json()

    # HTML disguised as .png must be rejected by magic-byte sniffing.
    evil = b"<html><script>alert(1)</script></html>"
    resp = await client.post(
        f"/api/v1/custom-requests/{created['id']}/files",
        files={"file": ("evil.png", evil, "image/png")},
        headers=user_headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_staff_can_access_request_files(client, auth_header_factory):
    user_headers, user = await auth_header_factory(role="customer")
    submission = {**VALID_SUBMISSION, "email": user.email}
    created = (await client.post("/api/v1/custom-requests", json=submission)).json()
    upload = await client.post(
        f"/api/v1/custom-requests/{created['id']}/files",
        files={"file": ("mood.png", PNG_BYTES, "image/png")},
        headers=user_headers,
    )
    asset_id = upload.json()["id"]

    sales_headers, _sales = await auth_header_factory(role="sales")
    access = await client.get(f"/api/v1/files/{asset_id}/access-url", headers=sales_headers)
    assert access.status_code == 200

    worker_headers, _worker = await auth_header_factory(role="worker")
    denied = await client.get(f"/api/v1/files/{asset_id}/access-url", headers=worker_headers)
    assert denied.status_code == 403

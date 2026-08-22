"""Integration tests for the restricted cost-estimate endpoint."""

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


VALID_ESTIMATE = {
    "material_lines": [
        {
            "label": "Oak panel",
            "quantity": "2.5",
            "unit": "square_meter",
            "unit_price_minor": 800000,
            "waste_percent": "10",
        },
        {"label": "Steel legs", "quantity": "4", "unit": "piece", "unit_price_minor": 150000},
    ],
    "labor_lines": [
        {"label": "Joinery", "hours": "6", "hourly_rate_minor": 200000},
    ],
    "expense_lines": [
        {"label": "Glue/screws", "line_type": "consumable", "amount_minor": 250000},
        {"label": "Workshop overhead", "line_type": "overhead", "percent_of_production_cost": "15"},
    ],
    "pricing": {"method": "target_margin", "target_margin_percent": "30"},
}


@pytest.mark.parametrize(
    "role,status_code",
    [("owner", 200), ("admin", 200), ("sales", 403), ("content", 403), ("accounting", 403), ("worker", 403)],
)
@pytest.mark.anyio
async def test_cost_estimate_rbac(client, auth_header_factory, role, status_code):
    """Cost data is sensitive: only price managers may compute estimates."""
    headers, _user = await auth_header_factory(role=role)
    resp = await client.post("/api/v1/admin/cost-estimates", json=VALID_ESTIMATE, headers=headers)
    assert resp.status_code == status_code


@pytest.mark.anyio
async def test_cost_estimate_math(client, auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    resp = await client.post("/api/v1/admin/cost-estimates", json=VALID_ESTIMATE, headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    # Materials: (2.5 * 1.10 * 800000) = 2200000; 4 * 150000 = 600000 -> 2800000
    assert body["material_subtotal_minor"] == 2800000
    # Labor: 6 * 200000 = 1200000
    assert body["labor_subtotal_minor"] == 1200000
    # Production subtotal: 4000000; consumables 250000 + overhead 15% = 600000
    assert body["expense_subtotal_minor"] == 850000
    # Real cost: 4850000
    assert body["real_cost_minor"] == 4850000
    # Selling at 30% margin: 4850000 / 0.7 = 6928571.43 -> 6928571
    assert body["selling_price_minor"] == 6928571
    assert len(body["lines"]) == 5
    assert all(line["explanation"] for line in body["lines"])


@pytest.mark.anyio
async def test_cost_estimate_deterministic(client, auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")
    results = [
        (await client.post("/api/v1/admin/cost-estimates", json=VALID_ESTIMATE, headers=headers)).json()[
            "selling_price_minor"
        ]
        for _ in range(5)
    ]
    assert len(set(results)) == 1


@pytest.mark.anyio
async def test_cost_estimate_validation(client, auth_header_factory):
    headers, _user = await auth_header_factory(role="owner")

    # Negative quantity.
    bad = {**VALID_ESTIMATE, "material_lines": [{**VALID_ESTIMATE["material_lines"][0], "quantity": "-1"}]}
    resp = await client.post("/api/v1/admin/cost-estimates", json=bad, headers=headers)
    assert resp.status_code == 422

    # Margin >= 100 unsolvable.
    bad_pricing = {**VALID_ESTIMATE, "pricing": {"method": "target_margin", "target_margin_percent": "100"}}
    resp = await client.post("/api/v1/admin/cost-estimates", json=bad_pricing, headers=headers)
    assert resp.status_code == 422

    # Manual pricing without a price value.
    bad_manual = {**VALID_ESTIMATE, "pricing": {"method": "manual"}}
    resp = await client.post("/api/v1/admin/cost-estimates", json=bad_manual, headers=headers)
    assert resp.status_code == 422

    # Zero unit prices allowed but flagged.
    zero_price = {
        **VALID_ESTIMATE,
        "material_lines": [{"label": "Scrap", "quantity": "1", "unit": "kg", "unit_price_minor": 0}],
        "labor_lines": [],
        "expense_lines": [],
        "pricing": {"method": "markup", "markup_percent": "20"},
    }
    resp = await client.post("/api/v1/admin/cost-estimates", json=zero_price, headers=headers)
    assert resp.status_code == 200
    assert any("zero-priced" in note for note in resp.json()["notes"])

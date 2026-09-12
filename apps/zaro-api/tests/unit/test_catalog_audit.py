"""Admin catalog mutations must each leave an audit trail.

Covers the four mutation endpoints that previously wrote no audit event:
POST /admin/categories, PATCH /admin/categories/{id},
POST /admin/products/{id}/variants, PATCH /admin/products/{id}/variants/{vid}.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog

pytestmark = pytest.mark.asyncio


async def _audit_events(db_session, action: str) -> list[AuditLog]:
    rows = (await db_session.execute(select(AuditLog).where(AuditLog.action == action))).scalars().all()
    return list(rows)


class TestCategoryMutationsAudited:
    async def test_category_create_writes_audit_event(self, client: AsyncClient, db_session, auth_header_factory):
        headers, _user = await auth_header_factory(role="owner")
        resp = await client.post("/api/v1/admin/categories", json={"name": "Chairs"}, headers=headers)
        assert resp.status_code == 201, resp.text

        rows = await _audit_events(db_session, "CATEGORY_CREATED")
        assert len(rows) == 1
        assert rows[0].result == "SUCCESS"
        assert rows[0].resource_type == "category"
        assert rows[0].resource_id == str(resp.json()["id"])

    async def test_category_update_writes_audit_event(self, client: AsyncClient, db_session, auth_header_factory):
        headers, _user = await auth_header_factory(role="owner")
        created = (await client.post("/api/v1/admin/categories", json={"name": "Chairs"}, headers=headers)).json()
        cat_id = created["id"]
        resp = await client.patch(
            f"/api/v1/admin/categories/{cat_id}",
            json={"description": "Three-legged"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        rows = await _audit_events(db_session, "CATEGORY_UPDATED")
        assert len(rows) == 1
        assert rows[0].result == "SUCCESS"
        assert rows[0].resource_id == cat_id
        assert rows[0].metadata_json["fields"] == ["description"]


class TestVariantMutationsAudited:
    async def _make_product(self, client: AsyncClient, headers: dict) -> dict:
        cat = (await client.post("/api/v1/admin/categories", json={"name": "Chairs"}, headers=headers)).json()
        product = (
            await client.post(
                "/api/v1/admin/products",
                json={"name": "Aria Chair", "category_id": cat["id"]},
                headers=headers,
            )
        ).json()
        return product

    async def test_variant_create_writes_audit_event(self, client: AsyncClient, db_session, auth_header_factory):
        headers, _user = await auth_header_factory(role="owner")
        product = await self._make_product(client, headers)

        resp = await client.post(
            f"/api/v1/admin/products/{product['id']}/variants",
            json={"label": "Oak"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

        rows = await _audit_events(db_session, "PRODUCT_VARIANT_CREATED")
        assert len(rows) == 1
        assert rows[0].result == "SUCCESS"
        assert rows[0].resource_type == "variant"
        assert rows[0].resource_id == resp.json()["id"]

    async def test_variant_update_writes_audit_event(self, client: AsyncClient, db_session, auth_header_factory):
        headers, _user = await auth_header_factory(role="owner")
        product = await self._make_product(client, headers)
        variant = await client.post(
            f"/api/v1/admin/products/{product['id']}/variants",
            json={"label": "Oak"},
            headers=headers,
        )
        assert variant.status_code == 201, variant.text
        variant = variant.json()
        resp = await client.patch(
            f"/api/v1/admin/products/{product['id']}/variants/{variant['id']}",
            json={"label": "Oak Natural"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        rows = await _audit_events(db_session, "PRODUCT_VARIANT_UPDATED")
        assert len(rows) == 1
        assert rows[0].result == "SUCCESS"
        assert rows[0].resource_id == variant["id"]
        assert rows[0].metadata_json["fields"] == ["label"]

"""Staff dashboard summary.

A single permission-aware aggregation for the admin landing page. Each
metric is only computed when the caller's role has the matching read
permission, so e.g. a production or content user gets a useful partial view
without ever touching customer data.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rbac import has_permission
from app.db.session import get_db
from app.models.custom_request import CustomRequest
from app.models.customer import Customer
from app.models.enums import CustomRequestStatus, Permission, ProductStatus
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])

RECENT_LIMIT = 8


def _recent_item(request_obj: CustomRequest) -> dict[str, Any]:
    return {
        "id": str(request_obj.id),
        "reference": request_obj.reference,
        "status": str(request_obj.status),
        "product_type": request_obj.product_type,
        "customer_name": request_obj.customer_name,
        "wilaya": request_obj.wilaya,
        "created_at": request_obj.created_at.isoformat() if request_obj.created_at else None,
    }


@router.get("")
async def dashboard_summary(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Aggregated counts and recent activity for the admin dashboard."""
    payload: dict[str, Any] = {}

    if has_permission(user.role, Permission.CUSTOM_REQUESTS_READ):
        total = (await db.execute(select(func.count()).select_from(CustomRequest))).scalar_one()
        breakdown: dict[str, int] = {}
        for status in CustomRequestStatus:
            breakdown[status.value] = (
                await db.execute(
                    select(func.count()).select_from(CustomRequest).where(CustomRequest.status == status.value)
                )
            ).scalar_one()
        week_ago = datetime.now(UTC) - timedelta(days=7)
        this_week = (
            await db.execute(
                select(func.count()).select_from(CustomRequest).where(CustomRequest.created_at >= week_ago)
            )
        ).scalar_one()
        recent = await custom_requests_snapshot(db)
        payload["custom_requests"] = {
            "total": total,
            "by_status": breakdown,
            "pending": breakdown[CustomRequestStatus.SUBMITTED.value]
            + breakdown[CustomRequestStatus.UNDER_REVIEW.value],
            "this_week": this_week,
        }
        payload["recent_requests"] = recent

    if has_permission(user.role, Permission.CUSTOMERS_READ):
        payload["customers_total"] = (await db.execute(select(func.count()).select_from(Customer))).scalar_one()

    if has_permission(user.role, Permission.PRODUCTS_READ):
        products_total = (await db.execute(select(func.count()).select_from(Product))).scalar_one()
        products_active = (
            await db.execute(
                select(func.count()).select_from(Product).where(Product.status == ProductStatus.ACTIVE.value)
            )
        ).scalar_one()
        payload["products"] = {"total": products_total, "active": products_active}

    return payload


async def custom_requests_snapshot(db: AsyncSession) -> list[dict[str, Any]]:
    """Most recent custom requests for the dashboard — slim, no PII beyond the submission snapshot."""
    stmt = select(CustomRequest).order_by(CustomRequest.created_at.desc()).limit(RECENT_LIMIT)
    results = (await db.execute(stmt)).scalars().all()
    return [_recent_item(r) for r in results]

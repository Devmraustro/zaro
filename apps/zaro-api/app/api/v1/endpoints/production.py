"""Production endpoints: production orders and material operations.

Phase 4 MVP: production orders created from confirmed orders only.
All financial invariants enforced server-side. Clients never control
prices, totals, deposits, or state transitions.
"""

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, require_permission
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.production import ProductionOrder
from app.models.user import User
from app.schemas.production import (
    ProductionConsumeRequest,
    ProductionOrderAction,
    ProductionOrderActionWithNote,
    ProductionOrderCancel,
    ProductionOrderPlan,
    ProductionReleaseRequest,
    ProductionReturnRequest,
    ProductionWasteRequest,
    QualityCheckStartRequest,
    QualityCheckSubmitRequest,
)
from app.services import production_service
from app.services.audit import record_event

router = APIRouter(prefix="/admin/production", tags=["admin-production"])

# Note: public-facing endpoints for production tracking (customer view) would go
# under a separate router with different auth/ownership checks. Phase 4 MVP
# focuses on admin operations.

# --- Helpers ----------------------------------------------------------------


def serialize_production_order(po, include_materials: bool = False) -> dict[str, Any]:
    data = {
        "id": str(po.id),
        "production_number": po.production_number,
        "order_id": str(po.order_id) if po.order_id else None,
        "customer_id": str(po.customer_id) if po.customer_id else None,
        "custom_request_id": str(po.custom_request_id) if po.custom_request_id else None,
        "status": po.status,
        "estimated_material_cost_minor": po.estimated_material_cost_minor,
        "actual_material_cost_minor": po.actual_material_cost_minor,
        "planned_start_date": po.planned_start_date.isoformat() if po.planned_start_date else None,
        "planned_end_date": po.planned_end_date.isoformat() if po.planned_end_date else None,
        "actual_start_date": po.actual_start_date.isoformat() if po.actual_start_date else None,
        "actual_end_date": po.actual_end_date.isoformat() if po.actual_end_date else None,
        "assigned_worker_id": str(po.assigned_worker_id) if po.assigned_worker_id else None,
        "supervisor_id": str(po.supervisor_id) if po.supervisor_id else None,
        "qc_inspector_id": str(po.qc_inspector_id) if po.qc_inspector_id else None,
        "planned_at": po.planned_at.isoformat() if po.planned_at else None,
        "materials_reserved_at": po.materials_reserved_at.isoformat() if po.materials_reserved_at else None,
        "production_started_at": po.production_started_at.isoformat() if po.production_started_at else None,
        "paused_at": po.paused_at.isoformat() if po.paused_at else None,
        "quality_check_started_at": po.quality_check_started_at.isoformat() if po.quality_check_started_at else None,
        "quality_check_completed_at": po.quality_check_completed_at.isoformat()
        if po.quality_check_completed_at
        else None,
        "ready_at": po.ready_at.isoformat() if po.ready_at else None,
        "completed_at": po.completed_at.isoformat() if po.completed_at else None,
        "cancelled_at": po.cancelled_at.isoformat() if po.cancelled_at else None,
        "cancellation_reason": po.cancellation_reason,
        "qc_notes": po.qc_notes,
        "qc_defects": po.qc_defects,
        "notes": po.notes,
        "created_at": po.created_at.isoformat() if po.created_at else None,
        "updated_at": po.updated_at.isoformat() if po.updated_at else None,
    }
    if include_materials:
        # This would need to be implemented - for now return empty
        data["material_reservations"] = []
    return data


async def get_production_order_or_404(db: AsyncSession, production_order_id: UUID) -> "ProductionOrder":
    from app.models.production import ProductionOrder

    po = await db.get(ProductionOrder, production_order_id)
    if po is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Production order not found")
    return po


# --- Admin Endpoints ---------------------------------------------------------


@router.post("", status_code=201)
async def create_production_order(
    request: Request,
    payload: "ProductionOrderPlan",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict[str, Any]:
    """Create a production order from a confirmed order.

    Server-side: validates order is CONFIRMED, creates production order with
    snapshot of financials. No client-controlled financials.
    """
    from app.models.order import Order

    order = await db.get(Order, payload.order_id)
    if order is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Order not found")

    po = await production_service.create_production_order(
        db,
        order=order,
        created_by=user.id,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_ORDER_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "production_number": po.production_number,
            "order_number": order.order_number,
            "estimated_material_cost_minor": po.estimated_material_cost_minor,
        },
    )
    await db.commit()

    return {"id": str(po.id), "production_number": po.production_number, "status": po.status}


@router.get("")
async def list_production_orders(
    _user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_READ))],
    db: Annotated["AsyncSession", Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = Query(
        None,
        pattern=r"^(pending|planned|materials_reserved|in_production|paused|quality_check|ready|completed|cancelled)$",
    ),
) -> dict:
    from sqlalchemy import func

    from app.models.production import ProductionOrder

    stmt = select(ProductionOrder)
    count_stmt = select(func.count()).select_from(ProductionOrder)

    if status:
        stmt = stmt.where(ProductionOrder.status == status)
        count_stmt = count_stmt.where(ProductionOrder.status == status)

    stmt = stmt.order_by(ProductionOrder.created_at.desc())
    total = (await db.execute(count_stmt)).scalar_one()
    pos = list((await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all())

    items = []
    for po in pos:
        items.append(
            {
                "id": str(po.id),
                "production_number": po.production_number,
                "order_id": str(po.order_id) if po.order_id else None,
                "status": po.status,
                "estimated_material_cost_minor": po.estimated_material_cost_minor,
                "actual_material_cost_minor": po.actual_material_cost_minor,
                "assigned_worker_id": str(po.assigned_worker_id) if po.assigned_worker_id else None,
                "created_at": po.created_at.isoformat() if po.created_at else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.get("/{production_order_id}")
async def get_production_order(
    production_order_id: UUID,
    _user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_READ))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict[str, Any]:
    po = await get_production_order_or_404(db, production_order_id)
    return serialize_production_order(po, include_materials=True)


@router.post("/{production_order_id}/plan")
async def plan_production(
    request: Request,
    production_order_id: UUID,
    payload: "ProductionOrderPlan",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    """Generate material reservations from order lines (BOM snapshot)."""
    from app.models.material import Material

    po = await get_production_order_or_404(db, production_order_id)

    # Convert requirements to MaterialRequirement objects
    from app.services.production_service import MaterialRequirement

    requirements = []
    for req in payload.requirements:
        material = await db.get(Material, req.material_id)
        if material is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(f"Material {req.material_id} not found")
        requirements.append(
            MaterialRequirement(
                material_id=req.material_id,
                material_name=material.name,
                material_code=material.code,
                material_unit=material.unit.value if hasattr(material.unit, "value") else str(material.unit),
                quantity_required=Decimal(req.quantity),
                unit_price_minor=req.unit_price_minor,
                material_spec=req.material_spec,
            )
        )

    po = await production_service.plan_production(
        db,
        production_order_id=production_order_id,
        requirements=requirements,
        planned_start_date=payload.planned_start_date,
        planned_end_date=payload.planned_end_date,
        actor_user_id=user.id,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_ORDER_PLANNED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "production_number": po.production_number,
            "material_count": len(payload.requirements),
            "estimated_material_cost_minor": po.estimated_material_cost_minor,
        },
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status, "estimated_material_cost_minor": po.estimated_material_cost_minor}


@router.post("/{production_order_id}/reserve")
async def reserve_materials(
    request: Request,
    production_order_id: UUID,
    _payload: "ProductionOrderAction",  # empty body with extra="forbid"
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    """Reserve all materials for production (atomic all-or-nothing)."""
    po = await production_service.reserve_materials(db, production_order_id, actor_user_id=None)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_MATERIALS_RESERVED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "production_number": po.production_number,
            "materials_reserved": True,
        },
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status, "materials_reserved": True}


@router.post("/{production_order_id}/start")
async def start_production(
    request: Request,
    production_order_id: UUID,
    _payload: "ProductionOrderAction",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    po = await production_service.start_production(db, production_order_id, actor_user_id=user.id)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_ORDER_STATUS_CHANGED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "production_number": po.production_number,
            "old_status": "materials_reserved",
            "new_status": "in_production",
        },
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status}


@router.post("/{production_order_id}/pause")
async def pause_production(
    request: Request,
    production_order_id: UUID,
    _payload: "ProductionOrderActionWithNote",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    po = await production_service.pause_production(db, production_order_id, actor_user_id=user.id)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_ORDER_STATUS_CHANGED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"production_number": po.production_number, "old_status": "in_production", "new_status": "paused"},
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status}


@router.post("/{production_order_id}/resume")
async def resume_production(
    request: Request,
    production_order_id: UUID,
    _payload: "ProductionOrderAction",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    po = await production_service.resume_production(db, production_order_id, actor_user_id=user.id)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_ORDER_STATUS_CHANGED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"production_number": po.production_number, "old_status": "paused", "new_status": "in_production"},
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status}


@router.post("/{production_order_id}/consume")
async def consume_material(
    request: Request,
    production_order_id: UUID,
    payload: "ProductionConsumeRequest",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    """Record material consumption during production."""
    from decimal import Decimal

    mr = await production_service.consume_material(
        db,
        production_order_id=production_order_id,
        material_reservation_id=payload.material_reservation_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        actor_user_id=user.id,
        notes=payload.notes,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_CONSUMPTION_RECORDED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_material_reservation",
        resource_id=str(payload.material_reservation_id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "quantity": str(payload.quantity),
            "material_reservation_id": str(payload.material_reservation_id),
        },
    )
    await db.commit()
    return {
        "material_reservation_id": str(mr.id),
        "quantity_consumed": str(mr.quantity_consumed),
        "remaining_reserved": str(
            mr.quantity_reserved
            - mr.quantity_consumed
            - mr.quantity_wasted
            - mr.quantity_returned
            - mr.quantity_released
        ),
    }


@router.post("/{production_order_id}/waste")
async def record_waste(
    request: Request,
    production_order_id: UUID,
    payload: "ProductionWasteRequest",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    from decimal import Decimal

    mr = await production_service.record_waste(
        db,
        production_order_id=production_order_id,
        material_reservation_id=payload.material_reservation_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        actor_user_id=user.id,
        reason=payload.reason,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_WASTE_RECORDED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_material_reservation",
        resource_id=str(payload.material_reservation_id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"quantity": str(payload.quantity), "reason": payload.reason},
    )
    await db.commit()
    return {
        "material_reservation_id": str(mr.id),
        "quantity_wasted": str(mr.quantity_wasted),
        "remaining_reserved": str(
            mr.quantity_reserved
            - mr.quantity_consumed
            - mr.quantity_wasted
            - mr.quantity_returned
            - mr.quantity_released
        ),
    }


@router.post("/{production_order_id}/return")
async def return_material(
    request: Request,
    production_order_id: UUID,
    payload: "ProductionReturnRequest",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    from decimal import Decimal

    mr = await production_service.return_material(
        db,
        production_order_id=production_order_id,
        material_reservation_id=payload.material_reservation_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        actor_user_id=user.id,
        notes=payload.notes,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_MATERIAL_RETURNED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_material_reservation",
        resource_id=str(payload.material_reservation_id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"quantity": str(payload.quantity)},
    )
    await db.commit()
    return {
        "material_reservation_id": str(mr.id),
        "quantity_returned": str(mr.quantity_returned),
        "remaining_reserved": str(
            mr.quantity_reserved
            - mr.quantity_consumed
            - mr.quantity_wasted
            - mr.quantity_returned
            - mr.quantity_released
        ),
    }


@router.post("/{production_order_id}/release")
async def release_material(
    request: Request,
    production_order_id: UUID,
    payload: "ProductionReleaseRequest",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    from decimal import Decimal

    mr = await production_service.release_material(
        db,
        production_order_id=production_order_id,
        material_reservation_id=payload.material_reservation_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        actor_user_id=user.id,
        notes=payload.notes,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_MATERIAL_RELEASED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_material_reservation",
        resource_id=str(payload.material_reservation_id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"quantity": str(payload.quantity)},
    )
    await db.commit()
    return {
        "material_reservation_id": str(mr.id),
        "quantity_released": str(mr.quantity_released),
        "remaining_reserved": str(
            mr.quantity_reserved
            - mr.quantity_consumed
            - mr.quantity_wasted
            - mr.quantity_returned
            - mr.quantity_released
        ),
    }


@router.post("/{production_order_id}/cancel")
async def cancel_production(
    request: Request,
    production_order_id: UUID,
    payload: "ProductionOrderCancel",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    po = await production_service.cancel_production(
        db,
        production_order_id=production_order_id,
        reason=payload.reason,
        actor_user_id=user.id,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_CANCELLED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"production_number": po.production_number, "reason": payload.reason},
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status, "cancellation_reason": po.cancellation_reason}


@router.post("/{production_order_id}/qc/start")
async def start_quality_check(
    request: Request,
    production_order_id: UUID,
    payload: "QualityCheckStartRequest",
    user: Annotated["User", Depends(require_permission(Permission.QUALITY_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    po = await production_service.start_quality_check(
        db,
        production_order_id=production_order_id,
        inspector_id=user.id,
        actor_user_id=user.id,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_QUALITY_CHECK_STARTED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"inspector_id": str(user.id)},
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status, "qc_inspector_id": str(po.qc_inspector_id)}


@router.post("/{production_order_id}/qc/submit")
async def submit_quality_check(
    request: Request,
    production_order_id: UUID,
    payload: "QualityCheckSubmitRequest",
    user: Annotated["User", Depends(require_permission(Permission.QUALITY_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    po = await production_service.complete_quality_check(
        db,
        production_order_id=production_order_id,
        approved=payload.approved,
        inspector_id=user.id,
        defects=payload.defects,
        notes=payload.notes,
        actor_user_id=user.id,
    )

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    action = (
        AuditAction.PRODUCTION_QUALITY_CHECK_APPROVED
        if payload.approved
        else AuditAction.PRODUCTION_QUALITY_CHECK_REJECTED
    )
    await record_event(
        db,
        action=action,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"approved": payload.approved, "defects": payload.defects},
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status, "approved": payload.approved}


@router.post("/{production_order_id}/complete")
async def complete_production(
    request: Request,
    production_order_id: UUID,
    _payload: "ProductionOrderAction",
    user: Annotated["User", Depends(require_permission(Permission.PRODUCTION_MANAGE))],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> dict:
    po = await production_service.complete_production(db, production_order_id, actor_user_id=user.id)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCTION_COMPLETED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="production_order",
        resource_id=str(po.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"production_number": po.production_number},
    )
    await db.commit()
    return {"id": str(po.id), "status": po.status}

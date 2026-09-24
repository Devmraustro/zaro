"""Custom requests service: submission, listing, lifecycle transitions.

Lifecycle (enforced by CUSTOM_REQUEST_TRANSITIONS in models.enums)::

    submitted ──► under_review ──► needs_information ──► (back to review)
                       │                                        │
                       ▼                                        ▼
                quotation_pending ──► converted            quotation_pending
                       │
                       ▼
                   cancelled   (reachable from every non-terminal state)

Terminal states accept no further transitions.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateTransition, NotFoundError, ValidationFailedError
from app.models.custom_request import CustomRequest
from app.models.customer import Customer
from app.models.enums import CUSTOM_REQUEST_TRANSITIONS, CustomRequestStatus
from app.services.references import next_custom_request_reference


async def get_request(db: AsyncSession, request_id: UUID) -> CustomRequest:
    request = await db.get(CustomRequest, request_id)
    if request is None:
        raise NotFoundError("Custom request not found")
    return request


async def submit_request(
    db: AsyncSession,
    *,
    full_name: str,
    email: str | None,
    phone: str | None,
    product_type: str,
    description: str,
    desired_dimensions: str | None,
    materials: str | None,
    colors: str | None,
    finish: str | None,
    quantity: int,
    budget_min_minor: int | None,
    budget_max_minor: int | None,
    wilaya: str | None = None,
    commune: str | None = None,
    address: str | None = None,
    source: str = "website",
    actor_user_id: UUID | None = None,
) -> CustomRequest:
    """Create a customer record (or reuse a match) and the request itself."""
    import app.models.commune as _cm

    # Location security validation imports (use module aliases to avoid parameter name conflicts)
    import app.models.wilaya as _wm
    from app.services.customers_service import find_matching_customer

    Wilaya = _wm.Wilaya
    Commune = _cm.Commune

    customer: Customer | None = await find_matching_customer(db, email=email, phone=phone)

    # Location security validation
    if wilaya is not None:
        # Verify the wilaya code exists in the reference table
        wilaya_obj = (await db.execute(select(Wilaya).where(Wilaya.code == wilaya))).scalar_one_or_none()
        if wilaya_obj is None:
            raise ValidationFailedError(
                f"Invalid wilaya code: {wilaya}",
                details={"wilaya": wilaya, "allowed": "codes from wilayas reference table"},
            )
        # If a commune is provided, verify it belongs to this wilaya
        if commune is not None:
            commune_obj = (await db.execute(select(Commune).where(Commune.code == commune))).scalar_one_or_none()
            if commune_obj is None or commune_obj.wilaya_id != wilaya_obj.id:
                raise ValidationFailedError(
                    f"Commune does not belong to wilaya {wilaya}",
                    details={"commune": commune, "wilaya": wilaya},
                )
    elif commune is not None:
        raise ValidationFailedError(
            "Commune requires a wilaya",
            details={"commune": commune, "wilaya": None},
        )
    if customer is None:
        customer = Customer(
            full_name=full_name,
            email=email.lower() if email else None,
            phone=phone,
        )
        db.add(customer)
        await db.flush()
    elif customer.status == "blocked":
        raise NotFoundError("Custom request not found")  # do not reveal blocked status

    if budget_min_minor is not None and budget_max_minor is not None and budget_min_minor > budget_max_minor:
        raise InvalidStateTransition("budget_min cannot exceed budget_max")

    from app.services.references import run_with_unique_retry

    async def _insert() -> CustomRequest:
        candidate = CustomRequest(
            reference=await next_custom_request_reference(db),
            customer_id=customer.id,
            customer_name=full_name,
            customer_email=email,
            customer_phone=phone,
            product_type=product_type,
            description=description,
            desired_dimensions=desired_dimensions,
            materials=materials,
            colors=colors,
            finish=finish,
            quantity=quantity,
            budget_min_minor=budget_min_minor,
            budget_max_minor=budget_max_minor,
            wilaya=wilaya,
            commune=commune,
            address=address,
            source=source,
        )
        db.add(candidate)
        await db.flush()
        return candidate

    # The public form is the highest-concurrency creation surface; reference
    # collisions regenerate-and-retry instead of failing with a 500.
    return await run_with_unique_retry(db, _insert)


def validate_transition(current: CustomRequestStatus, target: CustomRequestStatus) -> None:
    allowed = CUSTOM_REQUEST_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition custom request from '{current.value}' to '{target.value}'",
            details={"current": current.value, "allowed": sorted(s.value for s in allowed)},
        )


async def change_status(
    db: AsyncSession, request: CustomRequest, target: CustomRequestStatus, *, note: str | None = None
) -> CustomRequest:
    current = CustomRequestStatus(request.status)
    validate_transition(current, target)
    request.status = target
    if note is not None:
        request.notes = note
    await db.flush()
    return request


async def list_requests_for_customer(db: AsyncSession, customer_id: UUID) -> list[CustomRequest]:
    stmt = (
        select(CustomRequest).where(CustomRequest.customer_id == customer_id).order_by(CustomRequest.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_requests_admin(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[list[CustomRequest], int]:
    stmt = select(CustomRequest)
    count_stmt = select(func.count()).select_from(CustomRequest)
    if status:
        stmt = stmt.where(CustomRequest.status == status)
        count_stmt = count_stmt.where(CustomRequest.status == status)
    stmt = stmt.order_by(CustomRequest.created_at.desc())

    total = (await db.execute(count_stmt)).scalar_one()
    requests = list((await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all())
    return requests, total

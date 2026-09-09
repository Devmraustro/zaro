"""Customers service.

Deduplication rule: when creating a customer (staff entry or public custom
request), an existing record is matched by email first, then by phone.
Otherwise a new record is created. This keeps Instagram/phone/walk-in
customers from fragmenting into duplicates while never blocking on
missing contact info.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.customer import Customer


async def get_customer(db: AsyncSession, customer_id: UUID) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer


async def find_matching_customer(db: AsyncSession, *, email: str | None, phone: str | None) -> Customer | None:
    if email:
        existing = (await db.execute(select(Customer).where(Customer.email == email.lower()))).scalar_one_or_none()
        if existing is not None:
            return existing
    if phone:
        existing = (await db.execute(select(Customer).where(Customer.phone == phone))).scalar_one_or_none()
        if existing is not None:
            return existing
    return None


async def create_customer(db: AsyncSession, changes: dict) -> Customer:
    from app.services.references import run_with_unique_retry

    email = changes.get("email")
    phone = changes.get("phone")
    if email:
        clash = (await db.execute(select(Customer).where(Customer.email == str(email).lower()))).scalar_one_or_none()
        if clash is not None:
            raise ConflictError("A customer with this email already exists")

    async def _insert() -> Customer:
        candidate = Customer(
            full_name=changes["full_name"],
            email=str(email).lower() if email else None,
            phone=phone,
            company_name=changes.get("company_name"),
            address=changes.get("address"),
            city=changes.get("city"),
            municipality=changes.get("municipality"),
            notes=changes.get("notes"),
        )
        db.add(candidate)
        await db.flush()
        return candidate

    # A concurrent insert with the same email resolves to 409, never 500.
    return await run_with_unique_retry(db, _insert, conflict_message="A customer with this email already exists")


async def update_customer(db: AsyncSession, customer: Customer, changes: dict) -> Customer:
    if changes.get("email"):
        new_email = str(changes["email"]).lower()
        if new_email != customer.email:
            clash = (await db.execute(select(Customer).where(Customer.email == new_email))).scalar_one_or_none()
            if clash is not None:
                raise ConflictError("A customer with this email already exists")
            customer.email = new_email
    for field_name in ("full_name", "phone", "company_name", "address", "city", "municipality", "notes", "status"):
        if field_name in changes and changes[field_name] is not None:
            setattr(customer, field_name, changes[field_name])
    await db.flush()
    return customer


def escape_like_literal(value: str) -> str:
    """Escape LIKE wildcards so free-text search matches literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_customers(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
) -> tuple[list[Customer], int]:
    stmt = select(Customer)
    count_stmt = select(func.count()).select_from(Customer)
    if search:
        pattern = f"%{escape_like_literal(search.strip())}%"
        condition = or_(
            Customer.full_name.ilike(pattern, escape="\\"),
            Customer.email.ilike(pattern, escape="\\"),
            Customer.phone.ilike(pattern, escape="\\"),
            Customer.company_name.ilike(pattern, escape="\\"),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.order_by(Customer.created_at.desc())

    total = (await db.execute(count_stmt)).scalar_one()
    customers = list((await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all())
    return customers, total

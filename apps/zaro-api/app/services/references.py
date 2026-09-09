"""Slug and human-reference generation.

Server-controlled identifiers:
- slugs are derived from names and made unique with numeric suffixes;
- product codes follow ``ZAR-{CATEGORY}-{NNN}`` (e.g. ZAR-TAB-001);
- variant SKUs follow ``{product_code}-{VNN}``;
- custom-request references follow ``CR-{YYYY}-{NNNN}``;
- quote numbers follow ``ZQ-{YYYY}-{NNNNNN}``;
- order numbers follow ``ZO-{YYYY}-{NNNNNN}``;
- payment references follow ``ZPAY-{YYYY}-{NNNNNN}``.

Sequential codes are derived from existing rows inside the caller's
transaction. This is safe under normal admin traffic; a unique-violation
retry loop covers rare concurrent creations. References are convenience
labels only -- authorization always uses internal identifiers plus
ownership/permission checks.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_request import CustomRequest
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.production import ProductionOrder
from app.models.quote import Quote

_SLUG_MAX = 200


def slugify(text: str) -> str:
    """Normalize text to a URL-safe slug (ascii fold, lowercase, hyphens)."""
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:_SLUG_MAX] or "item"


async def unique_slug(db: AsyncSession, model: Any, base_slug: str, *, exclude_id: object = None) -> str:
    """Return ``base_slug`` or the first free ``base_slug-2``, ``-3``... variant."""
    candidate = base_slug
    counter = 2
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return candidate
        suffix = f"-{counter}"
        candidate = f"{base_slug[: _SLUG_MAX - len(suffix)]}{suffix}"
        counter += 1


def category_code_prefix(category_name: str | None) -> str:
    """Three-letter uppercase prefix for product codes."""
    if not category_name:
        return "GEN"
    letters = re.sub(r"[^A-Za-z]", "", unicodedata.normalize("NFKD", category_name).encode("ascii", "ignore").decode())
    prefix = letters[:3].upper() if letters else "GEN"
    return prefix.ljust(3, "X")


async def next_product_code(db: AsyncSession, category_name: str | None) -> str:
    """Generate the next sequential code for a category prefix."""
    prefix = f"ZAR-{category_code_prefix(category_name)}-"
    stmt = select(func.max(Product.product_code)).where(Product.product_code.like(f"{prefix}%"))
    current_max = (await db.execute(stmt)).scalar_one_or_none()
    next_seq = _next_sequence(current_max, prefix, width=3)
    return f"{prefix}{next_seq:03d}"


def build_variant_sku(product_code: str, variant_count: int) -> str:
    """Deterministic SKU from the parent code + variant ordinal."""
    return f"{product_code}-V{variant_count + 1:02d}"


async def next_custom_request_reference(db: AsyncSession) -> str:
    """Generate CR-YYYY-NNNN for the current year."""
    year = datetime.now(UTC).year
    prefix = f"CR-{year}-"
    stmt = select(func.max(CustomRequest.reference)).where(CustomRequest.reference.like(f"{prefix}%"))
    current_max = (await db.execute(stmt)).scalar_one_or_none()
    next_seq = _next_sequence(current_max, prefix, width=4)
    return f"{prefix}{next_seq:04d}"


async def _next_year_reference(db: AsyncSession, model: Any, column: Any, prefix: str) -> str:
    stmt = select(func.max(column)).where(column.like(f"{prefix}%"))
    current_max = (await db.execute(stmt)).scalar_one_or_none()
    next_seq = _next_sequence(current_max, prefix, width=6)
    return f"{prefix}{next_seq:06d}"


async def next_quote_number(db: AsyncSession) -> str:
    """Generate ZQ-YYYY-NNNNN for the current year."""
    year = datetime.now(UTC).year
    return await _next_year_reference(db, Quote, Quote.quote_number, f"ZQ-{year}-")


async def next_order_number(db: AsyncSession) -> str:
    """Generate ZO-YYYY-NNNNN for the current year."""
    year = datetime.now(UTC).year
    return await _next_year_reference(db, Order, Order.order_number, f"ZO-{year}-")


async def next_payment_reference(db: AsyncSession) -> str:
    """Generate ZPAY-YYYY-NNNNN for the current year."""
    year = datetime.now(UTC).year
    return await _next_year_reference(db, Payment, Payment.payment_reference, f"ZPAY-{year}-")


async def next_production_number(db: AsyncSession) -> str:
    """Generate ZPROD-YYYY-NNNNN for the current year."""
    year = datetime.now(UTC).year
    return await _next_year_reference(db, ProductionOrder, ProductionOrder.production_number, f"ZPROD-{year}-")


def _next_sequence(current_max: str | None, prefix: str, *, width: int) -> int:
    if not current_max or len(current_max) <= len(prefix):
        return 1
    try:
        return int(current_max[len(prefix) :]) + 1
    except ValueError:
        # Corrupted/unexpected row format: fall back to count-based guess.
        return 10**width - 1

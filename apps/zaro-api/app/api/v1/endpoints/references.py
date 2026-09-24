"""Public reference data endpoints.

Read-only endpoints for reference data such as geographical entities.
These endpoints are publicly accessible (no authentication required) and
use the existing ?lang localization mechanism for multilingual support.

All endpoints return deterministic, ordered results with proper validation.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.commune import Commune
from app.models.wilaya import Wilaya

router = APIRouter(tags=["references"])


PUBLIC_LOCALES = ("en", "fr", "ar")


def _resolve_locale(lang: str | None, request: Request) -> str:
    if lang:
        return lang
    header = request.headers.get("accept-language", "")
    for part in header.split(","):
        base = part.strip().split(";")[0].lower().split("-")[0]
        if base in PUBLIC_LOCALES:
            return base
    return "en"


def _serialize_wilaya(wilaya, locale: str) -> dict:
    return {
        "id": wilaya.id,
        "code": wilaya.code,
        "name": wilaya.name_en if locale == "en" else wilaya.name_fr if locale != "ar" else wilaya.name_ar,
        "locale": locale,
    }


def _serialize_commune(commune, locale: str) -> dict:
    return {
        "id": commune.id,
        "wilaya_id": commune.wilaya_id,
        "code": commune.code,
        "name": commune.name_en if locale == "en" else commune.name_fr if locale != "ar" else commune.name_ar,
        "locale": locale,
    }


@router.get("/references/wilayas", summary="List all Algerian wilayas (provinces)")
async def list_wilayas(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str | None, Query(pattern="^(en|fr|ar)$")] = None,
) -> dict[str, Any]:
    """Public endpoint to list all Algerian wilayas with multilingual names.

    The ``lang`` query parameter honors the preferred locale; falling back
    to the ``Accept-Language`` header, then to English.
    """
    locale = _resolve_locale(lang, request)
    stmt = select(Wilaya).order_by(Wilaya.code)
    rows = (await db.execute(stmt)).scalars().all()
    return {"items": [_serialize_wilaya(w, locale) for w in rows], "locale": locale, "total": len(rows)}


@router.get(
    "/references/communes",
    summary="List communes for a given wilaya",
    response_description="Communes filtered by wilaya code",
)
async def list_communes(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str | None, Query(pattern="^(en|fr|ar)$")] = None,
    wilaya: Annotated[str | None, Query(min_length=2, max_length=10)] = None,
) -> dict[str, Any]:
    """Public endpoint to list communes belonging to a specific wilaya.

    The ``wilaya`` query parameter filters communes by the two-digit wilaya
    code (e.g. ``16`` for Algiers, ``19`` for Oran). If not provided, all
    communes are returned (not recommended for production use).

    Names are localized using the existing ?lang mechanism.
    """
    locale = _resolve_locale(lang, request)

    # Explicit join to the parent wilaya so ``order_by(Wilaya.code, ...)`` is
    # unambiguous and never produces an accidental cross join (the parent
    # code is not a column on ``communes``).
    query = select(Commune).join(Wilaya, Commune.wilaya_id == Wilaya.id)

    if wilaya:
        query = query.where(Wilaya.code == wilaya)

    # Order by wilaya code then commune code for deterministic results
    query = query.order_by(Wilaya.code, Commune.code, Commune.name_en)

    rows = (await db.execute(query)).scalars().all()
    return {
        "items": [_serialize_commune(c, locale) for c in rows],
        "locale": locale,
        "total": len(rows),
        "wilaya": wilaya,
    }

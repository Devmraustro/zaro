"""File asset endpoints: uploads, signed access, public media.

Security model (extends the Phase 1.4 storage foundation):

- Storage keys are server-generated; client filenames are display-only.
- Content type is verified by magic bytes against the extension allow-list.
- Private assets (custom-request inspiration) are readable ONLY through a
  short-lived HMAC-signed URL issued after an ownership/permission check.
- Public assets (product media) stream without a token but only when their
  visibility is public AND purpose is product_media.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, get_current_user, require_permission
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.customer import Customer
from app.models.enums import FilePurpose, FileVisibility, Permission
from app.models.file_asset import FileAsset
from app.models.user import User
from app.services import catalog_service, custom_requests_service
from app.services.audit import record_event
from app.services.file_storage import (
    FileValidationError,
    get_storage_backend,
    normalize_filename,
    sign_url,
    verify_signed_url,
)

logger = get_logger("app.api.v1.endpoints.files")

router = APIRouter(tags=["files"])
admin_media_router = APIRouter(prefix="/admin/products", tags=["admin-media"])

_SIGNED_URL_TTL_SECONDS = 300


def _content_disposition(filename: str | None) -> str:
    """Header-safe inline disposition value (never echo raw client input)."""
    safe = filename or "file"
    safe = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in safe)[:100]
    return f'inline; filename="{safe or "file"}"'


async def _load_asset(db: AsyncSession, asset_id: UUID) -> FileAsset:
    asset = await db.get(FileAsset, asset_id)
    if asset is None:
        raise NotFoundError("File not found")
    return asset


def _serialize_asset(asset: FileAsset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "original_filename": asset.original_filename,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "purpose": str(asset.purpose),
        "visibility": str(asset.visibility),
        "media_kind": str(asset.media_kind) if asset.media_kind else None,
        "alt_text": asset.alt_text,
        "sort_order": asset.sort_order,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


async def _save_upload(
    settings: Settings,
    data: bytes,
    *,
    filename: str | None,
    content_type: str | None,
    category: str,
):
    backend = get_storage_backend(settings)
    return await backend.save(data, filename=filename, content_type=content_type, category=category)


# --- Custom-request inspiration uploads ---------------------------------------


@router.post("/custom-requests/{request_id}/files", status_code=201)
async def upload_request_file(
    request_id: UUID,
    request: Request,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    custom_request = await custom_requests_service.get_request(db, request_id)

    # Ownership: the customer who owns the request, or staff with update perm.
    is_staff = user.role != "customer"
    if not is_staff:
        by_email = (await db.execute(select(Customer).where(Customer.email == user.email.lower()))).scalar_one_or_none()
        linked = (await db.execute(select(Customer).where(Customer.user_id == user.id))).scalar_one_or_none()
        owns = (by_email and custom_request.customer_id == by_email.id) or (
            linked and custom_request.customer_id == linked.id
        )
        if not owns:
            raise ForbiddenError("You do not have access to this request")
    # Staff path implicitly allowed (endpoint requires authentication; staff
    # roles without custom_requests access are rejected below).
    from app.core.rbac import has_permission

    if is_staff and not has_permission(user.role, Permission.CUSTOM_REQUESTS_UPDATE):
        raise ForbiddenError("Insufficient permissions")

    data = await file.read()
    try:
        stored = await _save_upload(
            settings,
            data,
            filename=file.filename,
            content_type=file.content_type,
            category="inspiration",
        )
    except FileValidationError as exc:
        raise exc

    asset = FileAsset(
        storage_key=stored.key,
        original_filename=normalize_filename(file.filename) or None,
        content_type=stored.content_type,
        size_bytes=stored.size,
        sha256=stored.sha256,
        purpose=FilePurpose.CUSTOM_REQUEST_INSPIRATION,
        visibility=FileVisibility.PRIVATE,
        customer_id=custom_request.customer_id,
        custom_request_id=custom_request.id,
        uploaded_by_user_id=user.id,
    )
    db.add(asset)
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.FILE_UPLOADED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="file_asset",
        resource_id=str(asset.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"purpose": asset.purpose, "size_bytes": asset.size_bytes},
    )
    await db.commit()
    return _serialize_asset(asset)


# --- Signed private access ----------------------------------------------------


@router.get("/files/{asset_id}/access-url")
async def get_access_url(
    asset_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    asset = await _load_asset(db, asset_id)
    await _authorize_private_access(db, asset, user)
    token = sign_url(settings, asset.storage_key, _SIGNED_URL_TTL_SECONDS)
    expires_at = int(token.split("|")[0])
    return {
        "url_path": f"/api/v1/files/{asset.id}/content?token={token}",
        "expires_in": max(expires_at - int(__import__("time").time()), 0),
    }


async def _authorize_private_access(db: AsyncSession, asset: FileAsset, user: User) -> None:
    from app.core.rbac import has_permission

    if user.role != "customer" and has_permission(user.role, Permission.CUSTOM_REQUESTS_READ):
        return
    if user.role == "customer":
        from app.models.customer import Customer

        linked = (await db.execute(select(Customer).where(Customer.user_id == user.id))).scalar_one_or_none()
        by_email = (await db.execute(select(Customer).where(Customer.email == user.email.lower()))).scalar_one_or_none()
        customer = linked or by_email
        if customer is not None and asset.customer_id == customer.id:
            return
    raise ForbiddenError("You do not have access to this file")


@router.get("/files/{asset_id}/content")
async def stream_file_content(
    asset_id: UUID,
    token: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Token-authorized streaming (the signed URL IS the authorization)."""
    asset = await _load_asset(db, asset_id)
    if asset.visibility != FileVisibility.PRIVATE:
        raise NotFoundError("File not found")
    if not verify_signed_url(settings, asset.storage_key, token):
        raise ForbiddenError("Invalid or expired file token")
    backend = get_storage_backend(settings)
    data = backend.open(asset.storage_key)
    return Response(
        content=data,
        media_type=asset.content_type,
        headers={
            "Content-Disposition": _content_disposition(asset.original_filename),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/files/{asset_id}/public-content")
async def stream_public_file(
    asset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Public product media: no token, but strictly filtered."""
    asset = await _load_asset(db, asset_id)
    if asset.visibility != FileVisibility.PUBLIC or asset.purpose != FilePurpose.PRODUCT_MEDIA:
        raise NotFoundError("File not found")
    backend = get_storage_backend(settings)
    data = backend.open(asset.storage_key)
    return Response(
        content=data,
        media_type=asset.content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


# --- Product media (staff) -----------------------------------------------------


@admin_media_router.post("/{product_id}/media", status_code=201)
async def upload_product_media(
    product_id: UUID,
    request: Request,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_UPDATE))],
    media_kind: Annotated[str, Form(pattern="^(hero|gallery|detail|lifestyle|video)$")] = "gallery",
    alt_text: Annotated[str | None, Form(max_length=300)] = None,
    sort_order: Annotated[int, Form(ge=0, le=10000)] = 0,
) -> dict[str, Any]:
    product = await catalog_service.get_product(db, product_id)
    data = await file.read()
    stored = await _save_upload(
        settings,
        data,
        filename=file.filename,
        content_type=file.content_type,
        category="product_media",
    )
    asset = FileAsset(
        storage_key=stored.key,
        original_filename=normalize_filename(file.filename) or None,
        content_type=stored.content_type,
        size_bytes=stored.size,
        sha256=stored.sha256,
        purpose=FilePurpose.PRODUCT_MEDIA,
        visibility=FileVisibility.PUBLIC,
        product_id=product.id,
        media_kind=media_kind,
        alt_text=alt_text,
        sort_order=sort_order,
        uploaded_by_user_id=user.id,
    )
    db.add(asset)
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.FILE_UPLOADED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="file_asset",
        resource_id=str(asset.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"purpose": "product_media", "product_id": str(product.id), "media_kind": media_kind},
    )
    await db.commit()
    return _serialize_asset(asset)


@admin_media_router.get("/{product_id}/media")
async def list_product_media(
    product_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    stmt = (
        select(FileAsset)
        .where(FileAsset.product_id == product_id, FileAsset.purpose == FilePurpose.PRODUCT_MEDIA)
        .order_by(FileAsset.sort_order, FileAsset.created_at)
    )
    assets = list((await db.execute(stmt)).scalars().all())
    return [_serialize_asset(a) for a in assets]

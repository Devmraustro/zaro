"""Payment endpoints: proof upload, submission, review, configuration.

CCP is a MANUAL payment method: the customer transfers money themselves,
uploads proof, and an authorized ZARO operator confirms or rejects after
human review. Nothing here is automatic or bank-verified.
"""

from time import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, get_current_user, require_permission
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.rbac import has_permission
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import FilePurpose, FileVisibility, PaymentStatus, Permission
from app.models.file_asset import FileAsset
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payments import (
    PaymentConfigurationUpdate,
    PaymentConfirm,
    PaymentReject,
)
from app.services import orders_service, payments_service
from app.services.audit import record_event
from app.services.file_storage import (
    FileValidationError,
    get_storage_backend,
    normalize_filename,
    sign_url,
)

router = APIRouter(tags=["payments"])
admin_router = APIRouter(prefix="/admin/payments", tags=["admin-payments"])

_SIGNED_URL_TTL_SECONDS = 300

_REVIEW_REASONS_PUBLIC = {
    "proof_unreadable": "Proof is unreadable",
    "incorrect_amount": "Incorrect amount",
    "incorrect_recipient": "Incorrect recipient",
    "duplicate_transfer": "Duplicate transfer",
    "invalid_proof": "Invalid proof",
    "other": "Rejected",
}


def serialize_public(payment: Payment) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "payment_reference": payment.payment_reference,
        "order_id": str(payment.order_id),
        "method": str(payment.method),
        "status": str(PaymentStatus(payment.status)),
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        # Snapshot of the instructions shown when this claim was opened:
        # later config changes never rewrite history.
        "ccp_account_holder": payment.ccp_account_holder_snapshot,
        "ccp_account_identifier": payment.ccp_account_identifier_snapshot,
        "rejection_reason_code": payment.rejection_reason_code,
        "rejection_reason_note": payment.rejection_reason_note
        or _REVIEW_REASONS_PUBLIC.get(payment.rejection_reason_code or ""),
        "has_proof": payment.proof_asset_id is not None,
        "submitted_at": payment.submitted_at.isoformat() if payment.submitted_at else None,
        "reviewed_at": payment.reviewed_at.isoformat() if payment.reviewed_at else None,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
    }


def serialize_admin(payment: Payment) -> dict[str, Any]:
    data = serialize_public(payment)
    data.update(
        {
            "customer_id": str(payment.customer_id) if payment.customer_id else None,
            "proof_asset_id": str(payment.proof_asset_id) if payment.proof_asset_id else None,
            "reviewed_by": str(payment.reviewed_by) if payment.reviewed_by else None,
            "proof_uploaded_at": payment.proof_uploaded_at.isoformat() if payment.proof_uploaded_at else None,
        }
    )
    return data


async def _staff_or_owner_payment(db: AsyncSession, payment_id: UUID, user: User) -> Payment:
    payment = await payments_service.get_payment(db, payment_id)
    if user.role == "customer":
        customer = await orders_service.resolve_customer_for_user(db, user)
        if customer is None or payment.customer_id != customer.id:
            raise ForbiddenError("You do not have access to this payment")
        return payment
    if not has_permission(user.role, Permission.PAYMENTS_READ):
        raise ForbiddenError("Insufficient permissions")
    return payment


# --- Customer surface -----------------------------------------------------------


@router.post("/payments/{payment_id}/proof", status_code=200)
async def upload_payment_proof(
    request: Request,
    payment_id: UUID,
    file: UploadFile,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Attach (or replace) proof. Rejected payments may resubmit new proof."""
    payment = await _staff_or_owner_payment(db, payment_id, user)
    # Row-locked: serializes against concurrent confirm/cancel/reject on the
    # same claim, so a stale PROOF_UPLOADED write can never resurrect a
    # settled payment (append-only proof with a lost-update race).
    payment = await payments_service.get_for_update(db, payment_id)

    # Validate the transition BEFORE touching storage so a payment that can
    # no longer accept proof (e.g. already confirmed) does not leave an
    # orphaned file on disk.
    payments_service.validate_transition(PaymentStatus(payment.status), PaymentStatus.PROOF_UPLOADED)

    data = await file.read()
    backend = get_storage_backend(settings)
    try:
        stored = await backend.save(
            data, filename=file.filename, content_type=file.content_type, category="payment_proofs"
        )
    except FileValidationError:
        raise
    asset = FileAsset(
        storage_key=stored.key,
        original_filename=normalize_filename(file.filename) or None,
        content_type=stored.content_type,
        size_bytes=stored.size,
        sha256=stored.sha256,
        purpose=FilePurpose.PAYMENT_PROOF,
        visibility=FileVisibility.PRIVATE,
        customer_id=payment.customer_id,
        uploaded_by_user_id=user.id,
    )
    db.add(asset)
    await db.flush()

    was_rejected = PaymentStatus(payment.status) == PaymentStatus.REJECTED
    payment = await payments_service.attach_proof(db, payment, asset_id=asset.id)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PAYMENT_PROOF_UPLOADED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="payment",
        resource_id=str(payment.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "payment_reference": payment.payment_reference,
            "asset_id": str(asset.id),
            "resubmission": was_rejected,
        },
    )
    await db.commit()
    return serialize_public(payment)


@router.post("/payments/{payment_id}/submit")
async def submit_payment_for_review(
    request: Request,
    payment_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Customer asserts the transfer is done; proof becomes mandatory."""
    payment = await _staff_or_owner_payment(db, payment_id, user)
    # Row-locked so concurrent submissions serialize (exactly-once audit).
    payment = await payments_service.get_for_update(db, payment.id)
    old_status = str(PaymentStatus(payment.status))
    payment = await payments_service.submit_for_review(db, payment)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PAYMENT_SUBMITTED_FOR_REVIEW,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="payment",
        resource_id=str(payment.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "payment_reference": payment.payment_reference,
            "old_status": old_status,
            "new_status": str(PaymentStatus.UNDER_REVIEW),
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
        },
    )
    await db.commit()
    return serialize_public(payment)


@router.get("/payments/{payment_id}/proof-url")
async def get_proof_access_url(
    payment_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Short-lived signed URL for a payment proof.

    Authorization: the owning customer, or staff with ``payments.read``
    (owner/admin/accounting). Workers/content/sales are denied by design.
    """
    payment = await _staff_or_owner_payment(db, payment_id, user)
    if payment.proof_asset_id is None:
        raise NotFoundError("No proof uploaded for this payment")
    asset = await db.get(FileAsset, payment.proof_asset_id)
    if asset is None or asset.purpose != FilePurpose.PAYMENT_PROOF:
        raise NotFoundError("No proof uploaded for this payment")
    token = sign_url(settings, asset.storage_key, _SIGNED_URL_TTL_SECONDS)
    expires_at = int(token.split("|")[0])

    return {
        "url_path": f"/api/v1/files/{asset.id}/content?token={token}",
        "expires_in": max(expires_at - int(time()), 0),
    }


# --- Admin surface --------------------------------------------------------------


@admin_router.get("")
async def list_payments_admin_endpoint(
    _user: Annotated[User, Depends(require_permission(Permission.PAYMENTS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[
        str | None,
        Query(pattern=r"^(pending|proof_uploaded|under_review|confirmed|rejected|cancelled)$"),
    ] = None,
) -> dict[str, Any]:
    payments_list, total = await payments_service.list_payments_admin(db, page=page, page_size=page_size, status=status)
    return {
        "items": [serialize_admin(p) for p in payments_list],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@admin_router.post("/{payment_id}/confirm")
async def confirm_payment(
    request: Request,
    payment_id: UUID,
    user: Annotated[User, Depends(require_permission(Permission.PAYMENTS_CONFIRM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    _payload: PaymentConfirm | None = None,
) -> dict[str, Any]:
    """Confirm a deposit after human review of the proof.

    The whole operation runs in ONE transaction with row locks: payment and
    order are locked, verified against authoritative amounts, then updated
    together. A concurrent second confirmation fails safely with 409.
    """
    try:
        payment, order = await payments_service.confirm_payment(db, payment_id, reviewer_user_id=user.id)
    except Exception:
        await db.rollback()
        raise

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PAYMENT_CONFIRMED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="payment",
        resource_id=str(payment.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "payment_reference": payment.payment_reference,
            "order_number": order.order_number,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "old_status": str(PaymentStatus.UNDER_REVIEW),
            "new_status": str(PaymentStatus.CONFIRMED),
            "order_status": str(order.status),
        },
    )
    await db.commit()
    return serialize_admin(payment)


@admin_router.post("/{payment_id}/reject")
async def reject_payment(
    request: Request,
    payment_id: UUID,
    payload: PaymentReject,
    user: Annotated[User, Depends(require_permission(Permission.PAYMENTS_REJECT))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    # Row-locked: a concurrent confirmation holds the same lock, so exactly
    # one of confirm/reject wins. Without the lock a reject could overwrite
    # an already-CONFIRMED payment after its deposit was applied to the order.
    try:
        payment = await payments_service.get_for_update(db, payment_id)
    except Exception:
        await db.rollback()
        raise
    old_status = str(PaymentStatus(payment.status))
    try:
        payment = await payments_service.reject_payment(
            db,
            payment,
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            reviewer_user_id=user.id,
        )
    except Exception:
        await db.rollback()
        raise
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PAYMENT_REJECTED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="payment",
        resource_id=str(payment.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "payment_reference": payment.payment_reference,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "old_status": old_status,
            "new_status": str(PaymentStatus.REJECTED),
            "reason_code": payment.rejection_reason_code,
        },
    )
    await db.commit()
    return serialize_admin(payment)


# --- CCP configuration ----------------------------------------------------------


@admin_router.get("/config", response_model=None)
async def get_payment_configuration(
    _user: Annotated[User, Depends(require_permission(Permission.FINANCE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    config = await payments_service.get_configuration(db)
    return {
        "account_holder": config.account_holder,
        "account_identifier": config.account_identifier,
        "instructions": config.instructions,
        "default_deposit_percentage": config.default_deposit_percentage,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@admin_router.put("/config")
async def update_payment_configuration(
    request: Request,
    payload: PaymentConfigurationUpdate,
    user: Annotated[User, Depends(require_permission(Permission.FINANCE_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    old_percentage = (await payments_service.get_configuration(db)).default_deposit_percentage
    config = await payments_service.update_configuration(
        db,
        account_holder=payload.account_holder,
        account_identifier=payload.account_identifier,
        instructions=payload.instructions,
        default_deposit_percentage=payload.default_deposit_percentage,
        updated_by=user.id,
    )
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PAYMENT_CONFIGURATION_CHANGED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="payment_configuration",
        resource_id=str(config.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "changed_fields": [k for k, v in payload.model_dump().items() if v is not None],
            "old_default_deposit_percentage": old_percentage,
            "new_default_deposit_percentage": config.default_deposit_percentage,
        },
    )
    await db.commit()
    return {
        "account_holder": config.account_holder,
        "account_identifier": config.account_identifier,
        "instructions": config.instructions,
        "default_deposit_percentage": config.default_deposit_percentage,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }

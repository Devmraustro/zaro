"""Authentication endpoints.

Security behaviour summary:

- Login failures are generic (no account-existence disclosure) and timing-equalized.
- Refresh credentials rotate on every use; reuse of a rotated credential revokes
  the whole session family and raises AUTH_REFRESH_REUSE_DETECTED.
- Browser clients receive the refresh credential in an HttpOnly cookie scoped to
  /api/v1/auth plus a readable CSRF token cookie; cookie-sourced refreshes must
  present the matching X-CSRF-Token header (double-submit pattern).
- GET /auth/session is a read-only bootstrapping probe for cold page loads: it
  confirms the refresh cookie is live and returns a fresh CSRF value so the SPA
  can run the normal (rotating, reuse-detecting) refresh once. It mints no
  access token and never rotates the refresh credential.
- Every authentication event is written to the immutable audit log.
"""

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, get_current_session_id, get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
)
from app.core.rate_limit import get_client_ip, get_rate_limiter
from app.core.rbac import get_permissions_for_role
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.auth_session import REVOKE_REASON_LOGOUT
from app.models.enums import Role
from app.models.user import User
from app.schemas.auth import (
    BootstrapResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    RevokeSessionRequest,
    SessionInfo,
    SessionListResponse,
    TokenResponse,
    UserMeResponse,
    UserResponse,
)
from app.services import auth_service
from app.services.audit import record_event
from app.services.email import EmailMessage, get_email_sender

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_PATH = "/api/v1/auth"
_GENERIC_INVALID_CREDENTIALS = "Invalid email or password"
_GENERIC_INVALID_REFRESH = "Invalid or expired refresh token"
_GENERIC_RESET_RESPONSE = "If an account exists for that email, password reset instructions have been sent."
_GENERIC_RESET_RESULT = "If the reset token is valid, the password has been updated."


def _cookie_secure(settings: Settings) -> bool:
    # Single source of truth: Secure cookies in staging AND production.
    # (A local divergent check previously dropped Secure in staging.)
    return settings.cookie_secure


def _set_auth_cookies(response: Response, settings: Settings, refresh_secret: str) -> str:
    """Set the HttpOnly refresh cookie plus readable CSRF cookie.

    Returns the CSRF token written to the cookie so it can be echoed in the
    response body — the cookie is path-scoped to /api/v1/auth on the API
    origin, so a cross-origin SPA cannot read it from document.cookie and
    needs the value delivered as JSON to build the X-CSRF-Token header.
    """
    common: dict[str, Any] = {
        "secure": _cookie_secure(settings),
        "samesite": settings.cookie_samesite,
        "path": _COOKIE_PATH,
    }
    csrf_token = secrets.token_urlsafe(32)
    max_age = settings.refresh_token_expire_days * 86400
    response.set_cookie(settings.refresh_cookie_name, refresh_secret, httponly=True, max_age=max_age, **common)
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=False,
        max_age=max_age,
        **common,
    )
    return csrf_token


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.refresh_cookie_name, path=_COOKIE_PATH)
    response.delete_cookie(settings.csrf_cookie_name, path=_COOKIE_PATH)


def _validate_csrf(request: Request, settings: Settings) -> None:
    header = request.headers.get("X-CSRF-Token")
    cookie = request.cookies.get(settings.csrf_cookie_name)
    if not header or not cookie or not secrets.compare_digest(header, cookie):
        raise ForbiddenError("CSRF validation failed")


async def _audit(db: AsyncSession, request: Request, **kwargs) -> None:
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(db, request_id=request_id, ip_address=ip_address, user_agent=user_agent, **kwargs)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    limiter = get_rate_limiter(settings)
    ip_address = get_client_ip(request, settings)
    user_agent = request.headers.get("User-Agent")
    email = body.email.strip().lower()

    await limiter.hit("login_ip", ip_address or "unknown", settings.login_ip_limit, settings.auth_window_seconds)
    await limiter.hit("login_email", email, settings.login_email_limit, settings.auth_window_seconds)

    # Credential-stuffing guard: block once the failure counter for this email
    # reaches its long-window limit (checked before verification).
    failures = await limiter.hit(
        "login_fail_email",
        email,
        settings.login_failure_email_limit,
        settings.login_failure_window_seconds,
        count_only=True,
    )
    if failures >= settings.login_failure_email_limit:
        raise RateLimitError("Too many failed attempts. Try again later.")

    try:
        user, session, refresh_secret = await auth_service.authenticate_login(
            db,
            settings,
            email=email,
            password=body.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except auth_service.LoginFailure as exc:
        await limiter.hit(
            "login_fail_email", email, settings.login_failure_email_limit, settings.login_failure_window_seconds
        )
        await _audit(
            db,
            request,
            action=AuditAction.AUTH_LOGIN_FAILURE,
            result=AuditResult.FAILURE,
            actor_user_id=None,
            resource_type="user",
            metadata={"reason": exc.reason, "email": email},
        )
        await db.commit()
        raise UnauthorizedError(_GENERIC_INVALID_CREDENTIALS) from None

    access_token, expires_in = create_access_token(settings, str(user.id), session_id=str(session.id))
    await _audit(
        db,
        request,
        action=AuditAction.AUTH_LOGIN_SUCCESS,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="session",
        resource_id=str(session.id),
    )
    await db.commit()

    csrf_token = _set_auth_cookies(response, settings, refresh_secret)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_secret,
        token_type="bearer",
        expires_in=expires_in,
        csrf_token=csrf_token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=str(user.role.value if hasattr(user.role, "value") else user.role),
            is_active=user.is_active,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: RefreshRequest | None = None,
) -> TokenResponse:
    secret = (body.refresh_token if body else None) or None
    from_cookie = False
    if not secret:
        secret = request.cookies.get(settings.refresh_cookie_name)
        from_cookie = secret is not None
    if not secret:
        raise UnauthorizedError(_GENERIC_INVALID_REFRESH)

    if from_cookie:
        _validate_csrf(request, settings)

    ip_address = get_client_ip(request, settings)
    user_agent = request.headers.get("User-Agent")

    try:
        user, session, new_secret = await auth_service.rotate_refresh_token(
            db, settings, refresh_secret=secret, ip_address=ip_address, user_agent=user_agent
        )
    except auth_service.RefreshReuseDetected as exc:
        await _audit(
            db,
            request,
            action=AuditAction.AUTH_REFRESH_REUSE_DETECTED,
            result=AuditResult.FAILURE,
            actor_user_id=getattr(exc, "user_id", None),
            resource_type="session_family",
            metadata={"reason": "rotated_credential_reuse"},
        )
        await db.commit()
        raise UnauthorizedError(_GENERIC_INVALID_REFRESH) from None
    except auth_service.InvalidRefreshToken:
        # Invalid refresh attempts are logged (not audited) to avoid audit-table
        # noise from scanners; reuse detection is the audited security signal.
        await db.commit()
        raise UnauthorizedError(_GENERIC_INVALID_REFRESH) from None

    access_token, expires_in = create_access_token(settings, str(user.id), session_id=str(session.id))
    await _audit(
        db,
        request,
        action=AuditAction.AUTH_REFRESH,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="session",
        resource_id=str(session.id),
    )
    await db.commit()

    csrf_token = _set_auth_cookies(response, settings, new_secret)
    return TokenResponse(
        access_token=access_token, refresh_token=new_secret, expires_in=expires_in, csrf_token=csrf_token
    )


@router.get("/session", response_model=BootstrapResponse)
async def session_bootstrap(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BootstrapResponse:
    """Cold-page-load session probe (secure refresh-on-load).

    Read-only check of the HttpOnly refresh cookie. When live, issues the CSRF
    double-submit value (matching the readable ``zaro_csrf`` cookie on the API
    origin) so the cross-origin SPA can immediately perform the normal
    cookie-sourced refresh. No access token is minted and the refresh credential
    is NOT rotated, so a reload cannot trip the reuse-detection family
    revocation. GET is safe here because the probe is a pure read with no
    auth-related state change; the double-submit CSRF gate remains on /refresh.
    """
    secret = request.cookies.get(settings.refresh_cookie_name)
    if not secret or not await auth_service.is_refresh_session_live(db, refresh_secret=secret):
        return BootstrapResponse(session_active=False)

    csrf_token = secrets.token_urlsafe(32)
    max_age = settings.refresh_token_expire_days * 86400
    common: dict[str, Any] = {
        "secure": _cookie_secure(settings),
        "samesite": settings.cookie_samesite,
        "path": _COOKIE_PATH,
    }
    # Same cookie flags as _set_auth_cookies (readable CSRF half of the
    # double-submit pair); the HttpOnly refresh cookie is left untouched.
    response.set_cookie(settings.csrf_cookie_name, csrf_token, httponly=False, max_age=max_age, **common)
    response.headers["Cache-Control"] = "no-store, private"
    return BootstrapResponse(session_active=True, csrf_token=csrf_token)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: LogoutRequest | None = None,
) -> Response:
    target_session_id = get_current_session_id(request)

    body_session_id = body.session_id if body else None
    if body_session_id is not None:
        ok = await auth_service.revoke_session_by_id(
            db, user_id=current_user.id, session_id=body_session_id, reason=REVOKE_REASON_LOGOUT
        )
        if not ok:
            await db.rollback()
            raise NotFoundError("Session not found")
        target_session_id = body_session_id

    secret = (body.refresh_token if body else None) or request.cookies.get(settings.refresh_cookie_name)
    if secret and body_session_id is None:
        ok = await auth_service.revoke_session_by_secret(
            db, user_id=current_user.id, refresh_secret=secret, reason=REVOKE_REASON_LOGOUT
        )
        if ok:
            target_session_id = None  # resolved inside service; sid claim may differ

    if target_session_id is not None:
        await auth_service.revoke_session_by_id(
            db, user_id=current_user.id, session_id=target_session_id, reason=REVOKE_REASON_LOGOUT
        )

    await _audit(
        db,
        request,
        action=AuditAction.AUTH_LOGOUT,
        result=AuditResult.SUCCESS,
        actor_user_id=current_user.id,
        resource_type="session",
        resource_id=str(target_session_id) if target_session_id else None,
    )
    await db.commit()
    _clear_auth_cookies(response, settings)
    response.status_code = 204
    return response


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    keep_session_id = get_current_session_id(request)
    try:
        await auth_service.change_password(
            db,
            settings,
            user=current_user,
            current_password=body.current_password,
            new_password=body.new_password,
            keep_session_id=keep_session_id,
        )
    except auth_service.LoginFailure:
        await _audit(
            db,
            request,
            action=AuditAction.AUTH_PASSWORD_CHANGE,
            result=AuditResult.FAILURE,
            actor_user_id=current_user.id,
            resource_type="user",
            resource_id=str(current_user.id),
            metadata={"reason": "invalid_current_password"},
        )
        await db.commit()
        raise UnauthorizedError("Current password is incorrect") from None

    await _audit(
        db,
        request,
        action=AuditAction.AUTH_PASSWORD_CHANGE,
        result=AuditResult.SUCCESS,
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
    )
    await db.commit()
    return MessageResponse(message="Password updated")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    limiter = get_rate_limiter(settings)
    ip_address = get_client_ip(request, settings)
    email = body.email.strip().lower()

    await limiter.hit(
        "reset_req_ip", ip_address or "unknown", settings.password_reset_request_limit, settings.reset_window_seconds
    )
    await limiter.hit("reset_req_email", email, settings.password_reset_request_limit, settings.reset_window_seconds)

    token = await auth_service.create_password_reset_request(db, settings, email=email, ip_address=ip_address)

    if token is not None:
        sender = get_email_sender()
        await sender.send(
            EmailMessage(
                to_address=email,
                subject="ZARO password reset",
                body=(
                    "A password reset was requested for your ZARO account.\n\n"
                    f"Reset token (valid for {settings.password_reset_token_expire_minutes} minutes):\n"
                    f"{token}\n\n"
                    "If you did not request this, ignore this message."
                ),
            )
        )
        user = await auth_service.get_user_by_email(db, email)
        await _audit(
            db,
            request,
            action=AuditAction.AUTH_PASSWORD_RESET_REQUESTED,
            result=AuditResult.SUCCESS,
            actor_user_id=user.id if user else None,
            resource_type="user",
            metadata={"email": email},
        )
    else:
        await _audit(
            db,
            request,
            action=AuditAction.AUTH_PASSWORD_RESET_REQUESTED,
            result=AuditResult.FAILURE,
            actor_user_id=None,
            resource_type="user",
            metadata={"email": email, "reason": "unknown_or_disabled_account"},
        )

    await db.commit()
    return MessageResponse(message=_GENERIC_RESET_RESPONSE)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    limiter = get_rate_limiter(settings)
    ip_address = get_client_ip(request, settings)
    await limiter.hit(
        "reset_confirm_ip",
        ip_address or "unknown",
        settings.password_reset_confirm_limit,
        settings.reset_window_seconds,
    )

    user = await auth_service.consume_password_reset_token(
        db, settings, raw_token=body.token, new_password=body.new_password
    )
    if user is None:
        await db.commit()
        raise UnauthorizedError("Invalid or expired reset token")

    await _audit(
        db,
        request,
        action=AuditAction.AUTH_PASSWORD_RESET_COMPLETED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
    )
    await db.commit()
    return MessageResponse(message=_GENERIC_RESET_RESULT)


@router.get("/me", response_model=UserMeResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserMeResponse:
    role = Role(current_user.role) if isinstance(current_user.role, str) else current_user.role
    permissions = sorted(p.value for p in get_permissions_for_role(role))
    return UserMeResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=role.value,
        permissions=permissions,
        status="ACTIVE" if current_user.is_active else "DISABLED",
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionListResponse:
    current_session_id = get_current_session_id(request)
    sessions = await auth_service.list_user_sessions(db, user_id=current_user.id)
    return SessionListResponse(
        sessions=[SessionInfo(**auth_service.session_to_dict(s, current_session_id)) for s in sessions]
    )


@router.post("/sessions/revoke", response_model=MessageResponse)
async def revoke_session(
    body: RevokeSessionRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    ok = await auth_service.revoke_session_by_id(
        db, user_id=current_user.id, session_id=body.session_id, reason=REVOKE_REASON_LOGOUT
    )
    if not ok:
        await db.rollback()
        raise NotFoundError("Session not found")
    await _audit(
        db,
        request,
        action=AuditAction.AUTH_SESSION_REVOKED,
        result=AuditResult.SUCCESS,
        actor_user_id=current_user.id,
        resource_type="session",
        resource_id=str(body.session_id),
    )
    await db.commit()
    return MessageResponse(message="Session revoked")


@router.post("/sessions/revoke-all", response_model=MessageResponse)
async def revoke_all_sessions(
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    count = await auth_service.revoke_all_user_sessions(db, user_id=current_user.id, reason=REVOKE_REASON_LOGOUT)
    await _audit(
        db,
        request,
        action=AuditAction.AUTH_ALL_SESSIONS_REVOKED,
        result=AuditResult.SUCCESS,
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        metadata={"count": count},
    )
    await db.commit()
    _clear_auth_cookies(response, settings)
    return MessageResponse(message=f"Revoked {count} session(s)")

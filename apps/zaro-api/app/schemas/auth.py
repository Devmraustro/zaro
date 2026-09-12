from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    # Mirrors the readable zaro_csrf cookie so a cross-origin SPA can echo it in
    # the X-CSRF-Token header (the cookie itself is path-scoped to /api/v1/auth
    # and lives on the API origin, so it is not readable by page JavaScript).
    # Never the HttpOnly refresh credential; validates against the cookie as-is.
    csrf_token: str
    user: UserResponse


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    # Same double-submit contract as LoginResponse.csrf_token.
    csrf_token: str


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional: browser clients rely on the HttpOnly cookie instead.
    refresh_token: str | None = Field(default=None, max_length=512)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = Field(default=None, max_length=512)
    session_id: UUID | None = None


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=512)
    new_password: str = Field(min_length=1, max_length=128)


class RevokeSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID


class MessageResponse(BaseModel):
    message: str


class UserMeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    permissions: list[str]
    status: str


class SessionInfo(BaseModel):
    id: str
    created_at: datetime | None
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked: bool
    revoked_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    current: bool


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]


class BootstrapResponse(BaseModel):
    """Cold-page-load session bootstrap (GET /auth/session).

    Read-only probe of the HttpOnly refresh cookie. When it is live, returns a
    fresh CSRF double-submit value (and re-sets the readable ``zaro_csrf``
    cookie on the API origin) so a cross-origin SPA can then perform the normal
    cookie-sourced refresh. Deliberately issues no access token and performs no
    refresh rotation, so a reload cannot trip the reuse-detection family
    revocation or mint tokens silently.
    """

    session_active: bool
    csrf_token: str | None = None

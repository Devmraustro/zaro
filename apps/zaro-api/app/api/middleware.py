import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.exceptions import PayloadTooLargeError, RateLimitError
from app.core.logging import get_logger
from app.core.rate_limit import RateLimiter, get_client_ip, get_rate_limiter

logger = get_logger("app.api.middleware")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")

# Paths exempt from the global IP rate limit (health probes must never be
# throttled; CORS preflight is browser-driven and unauthenticated).
_RATE_LIMIT_EXEMPT_PATHS = {"/health/live", "/health/ready"}
_RATE_LIMIT_EXEMPT_METHODS = {"OPTIONS"}


def _sanitize_request_id(candidate: str | None) -> str:
    """Accept client correlation ids only in a strict format (log-injection guard)."""
    if candidate and _REQUEST_ID_RE.match(candidate):
        return candidate
    return str(uuid.uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a request id, binds structured logging context and records duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _sanitize_request_id(request.headers.get("X-Request-ID"))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        structlog.contextvars.clear_contextvars()
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response.

    The API serves only JSON: a restrictive CSP with no origins permitted is
    both correct here and a hard backstop against any future HTML injection.
    HSTS is emitted for staging/production where TLS terminates upstream.
    """

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; sandbox"
        if self._settings.is_staging_or_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects oversized request bodies before any parsing happens (413).

    Content-Length is checked when present; streamed/chunked bodies are
    additionally capped while being buffered by the framework.
    """

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._max_bytes = settings.max_request_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_bytes:
                    return self._too_large()
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": {"code": "bad_request", "message": "Invalid Content-Length header"}},
                )

        body = await request.body()
        if len(body) > self._max_bytes:
            return self._too_large()

        request._body = body
        return await call_next(request)

    @staticmethod
    def _too_large() -> JSONResponse:
        error = PayloadTooLargeError("Request body exceeds the maximum allowed size")
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": str(error)}},
        )


class AllowedHostsMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose Host header is not explicitly allowed (421).

    Empty ``allowed_hosts`` disables validation — appropriate for local
    development. Production templates set an explicit list.
    """

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._allowed = {host.strip().lower() for host in settings.allowed_hosts if host.strip()}

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._allowed:
            raw_host = (request.headers.get("host") or "").strip().lower()
            host_without_port = raw_host.rsplit(":", 1)[0] if raw_host.count(":") == 1 else raw_host
            if raw_host not in self._allowed and host_without_port not in self._allowed:
                logger.warning("rejected_disallowed_host", host=host_without_port)
                return JSONResponse(
                    status_code=421,
                    content={"error": {"code": "misdirected_request", "message": "Unrecognized Host header"}},
                )
        return await call_next(request)


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP fixed-window limit across all API routes.

    Uses the shared RateLimiter (Redis primary, per-process memory fallback).
    Health probes and CORS preflight are exempt. Disable entirely with
    ``ZARO_RATE_LIMIT_ENABLED=false`` (used by focused tests).
    """

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._limiter: RateLimiter | None = None

    def _get_limiter(self) -> RateLimiter:
        if self._limiter is None:
            self._limiter = get_rate_limiter(self._settings)
        return self._limiter

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = self._settings
        if (
            not settings.rate_limit_enabled
            or request.method in _RATE_LIMIT_EXEMPT_METHODS
            or request.url.path in _RATE_LIMIT_EXEMPT_PATHS
        ):
            return await call_next(request)

        ip = get_client_ip(request, settings) or "unknown"
        try:
            await self._get_limiter().hit(
                "global_ip", ip, settings.rate_limit_requests, settings.rate_limit_window_seconds
            )
        except RateLimitError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": exc.code, "message": str(exc)}},
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )
        return await call_next(request)

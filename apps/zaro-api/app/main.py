from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import (
    AllowedHostsMiddleware,
    BodySizeLimitMiddleware,
    GlobalRateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.events import lifespan
from app.core.exceptions import register_exception_handlers

# Explicit allow-list: never echo arbitrary client headers back via CORS.
_CORS_ALLOW_HEADERS = ["Content-Type", "Authorization", "X-Request-ID", "X-CSRF-Token"]


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.version,
        debug=cfg.debug,
        docs_url=cfg.docs_url if not cfg.is_production else None,
        openapi_url=cfg.openapi_url if not cfg.is_production else None,
        lifespan=lifespan,
    )
    app.state.settings = cfg

    # Starlette executes middleware outside-in in reverse registration order:
    # RequestContext -> SecurityHeaders -> GlobalRateLimit -> BodySizeLimit
    # -> AllowedHosts -> CORS -> routes.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=_CORS_ALLOW_HEADERS,
    )
    app.add_middleware(AllowedHostsMiddleware, settings=cfg)
    app.add_middleware(BodySizeLimitMiddleware, settings=cfg)
    app.add_middleware(GlobalRateLimitMiddleware, settings=cfg)
    app.add_middleware(SecurityHeadersMiddleware, settings=cfg)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    @app.get("/health/live", include_in_schema=False, tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix=cfg.api_v1_prefix)

    return app


app = create_app()

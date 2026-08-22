from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.db.redis import get_redis_client
from app.db.session import create_db_engine
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Readiness probe reporting database and Redis reachability."""
    database = "up"
    redis_status = "up"

    try:
        engine = create_db_engine(settings)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        database = "down"

    try:
        client = get_redis_client(settings)
        await client.ping()
    except Exception:
        redis_status = "down"

    status = "ok" if database == "up" and redis_status == "up" else "degraded"
    return HealthResponse(
        status=status,
        version=settings.version,
        services={"database": database, "redis": redis_status},
    )

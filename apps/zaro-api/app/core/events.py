from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.exceptions import RedisError

from app.core.logging import configure_logging, get_logger
from app.db.redis import dispose_redis, get_redis_client
from app.db.session import dispose_db_engines

logger = get_logger("app.core.events")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    configure_logging(settings)
    logger.info("starting up", app=settings.app_name, environment=settings.environment)

    redis = get_redis_client(settings)
    try:
        await redis.ping()
        logger.info("redis connection verified")
    except RedisError:
        logger.warning("redis unavailable at startup; will retry on demand")

    yield

    await dispose_redis()
    await dispose_db_engines()
    logger.info("shutdown complete")

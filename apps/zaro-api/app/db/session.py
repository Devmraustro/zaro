from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings

_created_engines: set[AsyncEngine] = set()


@lru_cache
def _engine_for(database_url: str, echo: bool) -> AsyncEngine:
    engine = create_async_engine(database_url, echo=echo, pool_pre_ping=True)
    _created_engines.add(engine)
    return engine


@lru_cache
def _factory_for(database_url: str, echo: bool) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(_engine_for(database_url, echo), expire_on_commit=False, autoflush=False)


def create_db_engine(settings: Settings) -> AsyncEngine:
    return _engine_for(settings.database_url, settings.debug)


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    return _factory_for(settings.database_url, settings.debug)


async def get_db() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    async with create_session_factory(settings)() as session:
        yield session


async def dispose_db_engines() -> None:
    for engine in list(_created_engines):
        await engine.dispose()
    _created_engines.clear()
    _engine_for.cache_clear()
    _factory_for.cache_clear()

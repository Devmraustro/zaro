from collections.abc import AsyncIterator
from functools import lru_cache

import redis.asyncio as aioredis

from app.core.config import Settings, get_settings

_created_clients: set[aioredis.Redis] = set()


@lru_cache
def _redis_for(redis_url: str) -> aioredis.Redis:
    client = aioredis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    _created_clients.add(client)
    return client


def get_redis_client(settings: Settings) -> aioredis.Redis:
    return _redis_for(settings.redis_url)


async def get_redis() -> AsyncIterator[aioredis.Redis]:
    settings = get_settings()
    yield get_redis_client(settings)


async def dispose_redis() -> None:
    for client in list(_created_clients):
        await client.aclose()
    _created_clients.clear()
    _redis_for.cache_clear()

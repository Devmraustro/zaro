"""Fixed-window rate limiting for authentication endpoints.

Primary backend is Redis (shared across workers). If Redis is unreachable the
limiter degrades to a per-process in-memory store so availability is preserved;
this fallback is documented as unsuitable for multi-worker production
deployments and exists mainly for tests and local development.

Client IP extraction only honours X-Forwarded-For when the direct peer address
is an explicitly configured trusted proxy.
"""

import ipaddress
import time
from dataclasses import dataclass, field

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.exceptions import RateLimitError
from app.core.logging import get_logger

logger = get_logger("app.core.rate_limit")

_KEY_PREFIX = "zaro:rl"


@dataclass
class _MemoryWindow:
    count: int = 0


@dataclass
class _MemoryStore:
    windows: dict[str, _MemoryWindow] = field(default_factory=dict)

    def _prune(self, now: float) -> None:
        stale = [k for k, v in self.windows.items() if v.count <= 0 or _window_expired(k, now)]
        for k in stale:
            self.windows.pop(k, None)


def _window_expired(key: str, now: float) -> bool:
    # Key format: zaro:rl:<scope>:<identity>:<window_start>:<window_seconds>
    try:
        _, window_seconds_s = key.rsplit(":", 1)
        window_start_s = key.rsplit(":", 2)[-2]
        return now > int(window_start_s) + int(window_seconds_s)
    except (ValueError, IndexError):
        return True


class RateLimiter:
    """Fixed-window counter limiter with Redis primary and in-memory fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._memory = _MemoryStore()
        self._redis: aioredis.Redis | None = None
        self._redis_failed = False

    def _get_redis(self) -> aioredis.Redis | None:
        if self._redis_failed:
            return None
        if self._redis is None:
            from app.db.redis import get_redis_client

            try:
                self._redis = get_redis_client(self._settings)
            except Exception:  # pragma: no cover - defensive
                self._redis_failed = True
                return None
        return self._redis

    def mark_redis_unavailable(self) -> None:
        self._redis_failed = True

    async def hit(
        self,
        scope: str,
        identifier: str,
        limit: int,
        window_seconds: int,
        *,
        count_only: bool = False,
    ) -> int:
        """Increment the counter for (scope, identifier) and enforce the limit.

        Returns the current count. Raises RateLimitError when the limit is
        exceeded. With ``count_only=True`` the counter is read without
        incrementing (used for pre-checks such as failure counters).
        """
        now = time.time()
        window_start = int(now // window_seconds) * window_seconds
        key = f"{_KEY_PREFIX}:{scope}:{identifier}:{window_start}:{window_seconds}"

        count = await self._hit_redis(key, limit, window_seconds, count_only)
        if count is None:
            count = self._hit_memory(key, count_only)
            self._memory._prune(now)

        if not count_only and count > limit:
            retry_after = max(1, int(window_start + window_seconds - now))
            raise RateLimitError(f"Too many requests. Retry after {retry_after} seconds")
        return count

    async def _hit_redis(self, key: str, limit: int, window_seconds: int, count_only: bool) -> int | None:
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            if count_only:
                value = await redis.get(key)
                return int(value) if value is not None else 0
            pipe = redis.pipeline(transaction=True)
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            result = await pipe.execute()
            return int(result[0])
        except (RedisError, OSError) as exc:
            logger.warning("rate_limiter_redis_unavailable", error=str(exc))
            self._redis_failed = True
            return None

    def _hit_memory(self, key: str, count_only: bool) -> int:
        entry = self._memory.windows.get(key)
        if entry is None:
            entry = _MemoryWindow()
            self._memory.windows[key] = entry
        if not count_only:
            entry.count += 1
        return entry.count

    def reset_memory(self) -> None:
        """Clear the in-memory fallback store (used by tests)."""
        self._memory.windows.clear()


_limiter: RateLimiter | None = None


def get_rate_limiter(settings: Settings) -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(settings)
    return _limiter


def reset_rate_limiter() -> None:
    """Reset the singleton (used by tests to avoid cross-test pollution)."""
    global _limiter
    if _limiter is not None:
        _limiter.reset_memory()
    _limiter = None


def get_client_ip(request, settings: Settings) -> str | None:
    """Return the best-effort client IP, honouring X-Forwarded-For only from trusted proxies."""
    peer = request.client.host if request.client else None
    forwarded = request.headers.get("X-Forwarded-For")
    if not forwarded or not peer:
        return peer
    if not _peer_is_trusted(peer, settings):
        return peer
    first_hop = forwarded.split(",")[0].strip()
    return first_hop or peer


def _peer_is_trusted(peer: str, settings: Settings) -> bool:
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for entry in settings.trusted_proxies:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if peer_addr in network:
            return True
    return False

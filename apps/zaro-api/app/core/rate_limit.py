"""Fixed-window rate limiting for authentication endpoints.

Primary backend is Redis (shared across workers). If Redis is unreachable the
limiter degrades to a per-process in-memory store so availability is preserved;
this fallback is documented as unsuitable for multi-worker production
deployments and exists mainly for tests and local development.

Redis failures open a short circuit breaker (``breaker_open_seconds``). While
open, every request uses the in-memory store without touching Redis. The
breaker automatically half-opens after the window: the next request re-probes
Redis, and if it responds the limiter returns to the shared backend -- so
counts synchronize again shortly after a Redis recovery instead of being
permanently stuck on per-process counters.

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

# How long Redis failures keep the circuit breaker open before a re-probe.
# Chosen so transient blips do not hammer a down Redis while recovery still
# re-arms the shared counters within a minute.
_BREAKER_OPEN_SECONDS = 30.0


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
    """Fixed-window counter limiter with Redis primary and in-memory fallback.

    The breaker guarantees bounded Redis outage: failures open it for
    ``breaker_open_seconds`` (in-memory fallback), then a re-probe decides
    whether to re-arm the shared Redis backend (half-open -> closed).
    """

    def __init__(self, settings: Settings, *, breaker_open_seconds: float = _BREAKER_OPEN_SECONDS) -> None:
        self._settings = settings
        self._breaker_open_seconds = breaker_open_seconds
        self._memory = _MemoryStore()
        self._redis: aioredis.Redis | None = None
        self._breaker_open_until = 0.0
        self._time = time.time

    def _set_breaker_open(self) -> None:
        self._breaker_open_until = self._time() + self._breaker_open_seconds

    def _get_redis(self) -> aioredis.Redis | None:
        if self._time() < self._breaker_open_until:
            return None
        if self._redis is None:
            from app.db.redis import get_redis_client

            try:
                self._redis = get_redis_client(self._settings)
            except Exception:  # pragma: no cover - defensive
                self._set_breaker_open()
                return None
        return self._redis

    def mark_redis_unavailable(self) -> None:
        """Force the breaker open (used by tests to simulate an outage)."""
        self._set_breaker_open()

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
        now = self._time()
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
            self._set_breaker_open()
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

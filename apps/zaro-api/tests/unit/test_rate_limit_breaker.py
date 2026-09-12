"""Circuit-breaker re-arming for the rate limiter's Redis backend.

Regression for RP-01: the limiter used a sticky one-way latch so a single
Redis blip permanently dropped the process onto per-process memory counters
(a fresh bypass window after Redis recovery). The breaker must half-open after
``breaker_open_seconds`` and re-probe Redis, so the shared backend re-arms.
"""

import pytest
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.exceptions import RateLimitError
from app.core.rate_limit import RateLimiter


class _FakeRedis:
    """Minimal stand-in for aioredis: fails until ``fail`` flips to False."""

    def __init__(self) -> None:
        self.fail = True
        self.counts: dict[str, int] = {}
        self.hits = 0

    async def get(self, key: str) -> str | None:
        if self.fail:
            raise RedisError("connection refused")
        value = self.counts.get(key)
        return str(value) if value is not None else None

    def pipeline(self, transaction: bool = True):
        return _FakePipeline(self)

    async def _incr(self, key: str) -> int:
        if self.fail:
            raise RedisError("connection refused")
        self.hits += 1
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class _FakePipeline:
    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis
        self._keys: list[str] = []

    def incr(self, key: str):
        self._keys.append(key)
        return self

    def expire(self, key: str, *args, **kwargs):
        return self

    async def execute(self) -> list[object]:
        result = await self._redis._incr(self._keys[0])
        return [result]


def _build(now: float, *, breaker_open_seconds: float = 30.0) -> tuple[RateLimiter, _FakeRedis]:
    limiter = RateLimiter(Settings(_env_file=None), breaker_open_seconds=breaker_open_seconds)
    fake = _FakeRedis()
    limiter._redis = fake  # inject the fake client so no real connection is attempted
    limiter._time = lambda: now
    return limiter, fake


class TestBreakerLifecycle:
    @pytest.mark.asyncio
    async def test_failure_opens_breaker_and_degrades_to_memory(self):
        limiter, fake = _build(now=100.0)
        assert fake.fail is True

        # First hit opens the breaker after the Redis error, counts in memory.
        assert await limiter.hit("scope", "id-1", limit=10, window_seconds=60) == 1

        # Once open, no further Redis calls are attempted.
        assert await limiter.hit("scope", "id-1", limit=10, window_seconds=60) == 2
        assert fake.hits == 0

        # The in-memory fallback still enforces the limit.
        with pytest.raises(RateLimitError):
            for _ in range(9):
                await limiter.hit("scope", "id-1", limit=10, window_seconds=60)

    @pytest.mark.asyncio
    async def test_breaker_requests_no_redis_while_open(self):
        limiter, fake = _build(now=100.0)
        fake.fail = True
        await limiter.hit("s", "x", limit=5, window_seconds=60)

        assert await limiter.hit("s", "x", limit=5, window_seconds=60) == 2
        assert fake.hits == 0

    @pytest.mark.asyncio
    async def test_breaker_rearms_and_redis_counters_resume(self):
        limiter, fake = _build(now=100.0)
        fake.fail = True
        await limiter.hit("s", "x", limit=5, window_seconds=60)  # opens breaker until t=130

        # Inside the window: memory only.
        assert await limiter.hit("s", "x", limit=5, window_seconds=60) == 2
        assert fake.hits == 0

        # Redis recovers; after the window the next hit re-probes and re-arms.
        fake.fail = False
        limiter._time = lambda: 130.0
        assert await limiter.hit("s", "x", limit=5, window_seconds=60) == 1  # fresh Redis counter
        assert fake.hits == 1

    @pytest.mark.asyncio
    async def test_breaker_reopens_when_recovery_fails(self):
        limiter, fake = _build(now=100.0)
        fake.fail = True
        # Wide window so hits at t=100..131 share one fixed window (count 1,2,3).
        await limiter.hit("s", "x", limit=5, window_seconds=3600)  # opens breaker until t=130
        fake.fail = True  # Redis still down at the re-probe
        limiter._time = lambda: 130.0

        # Re-probe fails again -> back to memory, breaker open for another window.
        assert await limiter.hit("s", "x", limit=5, window_seconds=3600) == 2
        assert fake.hits == 0

        limiter._time = lambda: 131.0
        assert await limiter.hit("s", "x", limit=5, window_seconds=3600) == 3
        assert fake.hits == 0

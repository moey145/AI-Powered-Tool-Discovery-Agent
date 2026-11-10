"""Abuse limits. In memory they apply per instance; with Redis they are shared."""

import math
import time
from collections import deque
from collections.abc import Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import Settings
from .logger import get_logger

logger = get_logger("rate_limit")

_WINDOW_SECONDS = 60.0
_DAY_SECONDS = 86_400.0
_MAX_TRACKED_CLIENTS = 10_000


class RateLimiter:
    def __init__(
        self,
        per_minute: int,
        daily_budget: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.per_minute = per_minute
        self.daily_budget = daily_budget
        self.clock = clock
        self._clients: dict[str, deque[float]] = {}
        self._day: deque[float] = deque()

    async def check(self, client: str) -> int | None:
        """Record a request and return None, or return seconds to wait if it is over a limit."""
        now = self.clock()
        while self._day and now - self._day[0] >= _DAY_SECONDS:
            self._day.popleft()
        if len(self._day) >= self.daily_budget:
            return math.ceil(_DAY_SECONDS - (now - self._day[0]))

        if len(self._clients) >= _MAX_TRACKED_CLIENTS:
            self._clients = {
                key: hits
                for key, hits in self._clients.items()
                if hits and now - hits[-1] < _WINDOW_SECONDS
            }
        hits = self._clients.setdefault(client, deque())
        while hits and now - hits[0] >= _WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return math.ceil(_WINDOW_SECONDS - (now - hits[0]))

        hits.append(now)
        self._day.append(now)
        return None


class RedisRateLimiter:
    """Limits shared by every instance. Falls back to memory so an outage can't remove them."""

    def __init__(
        self,
        redis: Redis,
        per_minute: int,
        daily_budget: int,
        clock: Callable[[], float] = time.time,
    ):
        self.redis = redis
        self.per_minute = per_minute
        self.daily_budget = daily_budget
        self.clock = clock
        self.fallback = RateLimiter(per_minute, daily_budget)

    async def _increment(self, key: str, ttl: int) -> int:
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, ttl)
        return count

    async def check(self, client: str) -> int | None:
        now = int(self.clock())
        try:
            minute_key = f"rate:client:{client}:{now // 60}"
            if await self._increment(minute_key, 120) > self.per_minute:
                return 60 - now % 60 or 60
            if await self._increment(f"rate:day:{now // 86_400}", 90_000) > self.daily_budget:
                return 86_400 - now % 86_400 or 86_400
            return None
        except (RedisError, OSError) as exc:
            logger.warning("Redis unavailable for rate limiting: %s", type(exc).__name__)
            return await self.fallback.check(client)


def create_rate_limiter(settings: Settings, redis: Redis | None) -> RateLimiter | RedisRateLimiter:
    if redis is not None:
        return RedisRateLimiter(redis, settings.rate_limit_per_minute, settings.daily_search_budget)
    return RateLimiter(settings.rate_limit_per_minute, settings.daily_search_budget)

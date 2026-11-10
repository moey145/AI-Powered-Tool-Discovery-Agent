"""Result caching: in memory by default, or shared through Redis when REDIS_URL is set."""

import hashlib
import time
from collections import OrderedDict

from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from .config import Settings
from .logger import get_logger
from .models import ResearchResult

logger = get_logger("store")


class ResultCache:
    def __init__(self, ttl_seconds: int, max_entries: int = 128):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, ResearchResult]] = OrderedDict()

    async def get(self, key: str) -> ResearchResult | None:
        item = self._items.get(key)
        if item is None:
            return None
        if time.monotonic() - item[0] >= self.ttl:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return item[1]

    async def set(self, key: str, value: ResearchResult) -> None:
        self._items[key] = (time.monotonic(), value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)


class RedisResultCache:
    """A cache outage only costs a repeat search, so errors are treated as a miss."""

    def __init__(self, redis: Redis, ttl_seconds: int):
        self.redis = redis
        self.ttl = ttl_seconds

    @staticmethod
    def _key(key: str) -> str:
        return f"result:{hashlib.sha256(key.encode()).hexdigest()}"

    async def get(self, key: str) -> ResearchResult | None:
        try:
            raw = await self.redis.get(self._key(key))
        except (RedisError, OSError) as exc:
            logger.warning("Redis read failed: %s", type(exc).__name__)
            return None
        return ResearchResult.model_validate_json(raw) if raw else None

    async def set(self, key: str, value: ResearchResult) -> None:
        try:
            await self.redis.set(self._key(key), value.model_dump_json(), ex=self.ttl)
        except (RedisError, OSError) as exc:
            logger.warning("Redis write failed: %s", type(exc).__name__)


def create_redis(settings: Settings) -> Redis | None:
    if not settings.redis_url:
        return None
    return from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_timeout=1.5,
        socket_connect_timeout=1.5,
    )


def create_cache(settings: Settings, redis: Redis | None) -> ResultCache | RedisResultCache:
    if redis is not None:
        return RedisResultCache(redis, settings.cache_ttl_seconds)
    return ResultCache(settings.cache_ttl_seconds)

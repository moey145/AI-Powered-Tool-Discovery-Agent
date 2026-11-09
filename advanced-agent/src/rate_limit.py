"""In-memory abuse limits. They apply per server instance, so scale the numbers accordingly."""

import math
import time
from collections import deque
from collections.abc import Callable

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

    def check(self, client: str) -> int | None:
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

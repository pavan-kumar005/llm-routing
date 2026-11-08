import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window limiter, kept in memory (fine for a single server)."""

    def __init__(self, window: float = 60.0):
        self.window = window
        self._hits = defaultdict(deque)

    def check(self, key: str, limit: int) -> int:
        """Returns 0 if the request is allowed, else seconds to wait."""
        now = time.monotonic()
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= limit:
            return max(1, int(self.window - (now - q[0])) + 1)
        q.append(now)
        return 0

    def clear(self) -> None:
        self._hits.clear()
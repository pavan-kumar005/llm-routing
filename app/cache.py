import hashlib
import time
from collections import OrderedDict


class TTLCache:
    """Small in-memory cache: entries expire after ttl seconds, oldest evicted first."""

    def __init__(self, ttl: int = 3600, max_items: int = 1000):
        self.ttl = ttl
        self.max_items = max_items
        self._data: OrderedDict = OrderedDict()

    @staticmethod
    def make_key(*parts) -> str:
        return hashlib.sha256("\x00".join(str(p) for p in parts).encode()).hexdigest()

    def get(self, key: str):
        item = self._data.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < time.time():
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value) -> None:
        self._data[key] = (time.time() + self.ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()
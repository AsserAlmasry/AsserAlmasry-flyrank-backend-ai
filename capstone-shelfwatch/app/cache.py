"""A tiny thread-safe TTL cache for expensive read results (the dashboard stats query)."""
import threading
import time
from typing import Any, Callable


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> tuple[Any, bool]:
        """Returns (value, was_cached)."""
        with self._lock:
            entry = self._data.get(key)
            if entry and entry[0] > time.monotonic():
                self.hits += 1
                return entry[1], True
        value = compute()  # outside the lock: a slow query must not block other readers
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self.misses += 1
        return value, False

    def clear(self) -> None:
        """Invalidate: called after every scan, so cached numbers are never older than the data."""
        with self._lock:
            self._data.clear()


stats_cache = TTLCache(ttl_seconds=300)

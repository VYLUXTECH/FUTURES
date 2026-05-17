# ============================================================
# FuturesBrain v1.0 – Thread-Safe In-Memory Cache
# Used by copilot endpoint (5-min TTL per spec).
# ============================================================
from __future__ import annotations

import threading
import time
from typing import Any


class CacheManager:
    """Simple TTL key-value store. Thread-safe via RLock."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            data, ts = entry
            if time.monotonic() - ts > self.ttl:
                del self._store[key]
                return None
            return data

    def set(self, key: str, data: Any) -> None:
        with self._lock:
            self._store[key] = (data, time.monotonic())

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)

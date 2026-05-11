"""
URL Result Cache for ViFake Analytics.

Thread-safe in-memory cache with TTL (time-to-live) expiry.
Prevents re-crawling the same URL within the TTL window.

Spec:
  - TTL: 300 seconds (configurable)
  - Max entries: 1000 (LRU eviction)
  - Thread-safe via threading.Lock
  - Key: URL string
  - Value: Any serialisable result dict
"""
import time
import threading
import logging
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class URLCache:
    """Thread-safe LRU cache with per-entry TTL."""

    def __init__(self, ttl: int = 300, max_size: int = 1000):
        self._ttl      = ttl
        self._max_size = max_size
        self._store: OrderedDict = OrderedDict()  # url → (expires_at, value)
        self._lock  = threading.Lock()
        self._hits  = 0
        self._misses = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def get(self, url: str) -> Optional[Any]:
        """Return cached value or None if missing / expired."""
        with self._lock:
            entry = self._store.get(url)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                # Expired — remove and miss
                del self._store[url]
                self._misses += 1
                return None
            # LRU: move to end
            self._store.move_to_end(url)
            self._hits += 1
            return value

    def set(self, url: str, value: Any) -> None:
        """Store value for URL with TTL."""
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            if url in self._store:
                self._store.move_to_end(url)
            self._store[url] = (expires_at, value)
            # Evict oldest entries if over capacity
            while len(self._store) > self._max_size:
                oldest_url, _ = next(iter(self._store.items()))
                del self._store[oldest_url]
                logger.debug(f"Cache evicted: {oldest_url[:60]}")

    def invalidate(self, url: str) -> bool:
        """Remove a specific URL from cache. Returns True if it existed."""
        with self._lock:
            if url in self._store:
                del self._store[url]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._store.clear()
            logger.info("URLCache cleared")

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries":    len(self._store),
                "max_size":   self._max_size,
                "ttl_seconds": self._ttl,
                "hits":       self._hits,
                "misses":     self._misses,
                "hit_rate":   round(self._hits / total, 3) if total > 0 else 0.0,
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# ── Module-level singleton ───────────────────────────────────────────────────
# Used by main.py: `from backend_services.cache_manager import url_cache`
url_cache = URLCache(ttl=300, max_size=1000)

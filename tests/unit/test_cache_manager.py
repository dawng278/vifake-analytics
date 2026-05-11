"""Unit tests for URL result cache (cache_manager)."""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from backend_services.cache_manager import URLCache


@pytest.mark.unit
class TestURLCache:
    def setup_method(self):
        self.cache = URLCache(ttl=2, max_size=5)

    def test_miss_on_empty_cache(self):
        assert self.cache.get("https://example.com") is None

    def test_set_and_get(self):
        self.cache.set("https://example.com", {"label": "SAFE"})
        result = self.cache.get("https://example.com")
        assert result == {"label": "SAFE"}

    def test_ttl_expiry(self):
        self.cache.set("https://ttl-test.com", {"label": "FAKE_SCAM"})
        time.sleep(2.1)
        assert self.cache.get("https://ttl-test.com") is None

    def test_lru_eviction(self):
        for i in range(6):
            self.cache.set(f"https://url{i}.com", {"i": i})
        # max_size=5, so oldest should be evicted
        assert len(self.cache) == 5

    def test_invalidate(self):
        self.cache.set("https://x.com", {"label": "SUSPICIOUS"})
        removed = self.cache.invalidate("https://x.com")
        assert removed is True
        assert self.cache.get("https://x.com") is None

    def test_invalidate_missing_returns_false(self):
        assert self.cache.invalidate("https://not-cached.com") is False

    def test_clear(self):
        self.cache.set("https://a.com", {})
        self.cache.set("https://b.com", {})
        self.cache.clear()
        assert len(self.cache) == 0

    def test_stats(self):
        self.cache.set("https://stat.com", {"x": 1})
        self.cache.get("https://stat.com")  # hit
        self.cache.get("https://missing.com")  # miss
        stats = self.cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

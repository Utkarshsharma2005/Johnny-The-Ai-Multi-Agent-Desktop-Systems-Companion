import time
from backend.core.cache import LRUTTLCache, make_cache_key


def test_lru_cache_operations():
    cache = LRUTTLCache(capacity=3, default_ttl_s=10.0)

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3

    # Add 4th item -> should evict least recently used ("a" was accessed, "b" was accessed, so "c" was accessed least or "a" was accessed first)
    cache.set("d", 4)
    stats = cache.stats()
    assert stats["size"] == 3
    assert stats["hits"] >= 3


def test_lru_cache_ttl_expiration():
    cache = LRUTTLCache(capacity=5, default_ttl_s=0.1)
    cache.set("temp", "value", ttl_s=0.05)

    assert cache.get("temp") == "value"
    time.sleep(0.06)
    assert cache.get("temp") is None


def test_make_cache_key():
    k1 = make_cache_key("test", {"a": 1, "b": 2})
    k2 = make_cache_key("test", {"a": 1, "b": 2})
    k3 = make_cache_key("test", {"a": 2, "b": 1})

    assert k1 == k2
    assert k1 != k3


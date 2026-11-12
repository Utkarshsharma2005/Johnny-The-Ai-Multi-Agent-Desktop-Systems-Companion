"""
backend/core/cache.py — High-Performance In-Memory LRU Cache with TTL.

Provides sub-millisecond in-memory caching for LLM responses, memory queries,
and visual hashes, drastically reducing downstream latency and token burn.
Optimized with O(1) hash map + doubly linked list eviction.
"""

import time
import hashlib
import threading
from typing import Any, Optional, Dict


class CacheNode:
    def __init__(self, key: str, value: Any, expires_at: float):
        self.key = key
        self.value = value
        self.expires_at = expires_at
        self.prev: Optional['CacheNode'] = None
        self.next: Optional['CacheNode'] = None


class LRUTTLCache:
    """
    Thread-safe, high-efficiency O(1) LRU cache with TTL expiration.
    """
    def __init__(self, capacity: int = 500, default_ttl_s: float = 300.0):
        self.capacity = capacity
        self.default_ttl_s = default_ttl_s
        self.cache: Dict[str, CacheNode] = {}
        self._lock = threading.Lock()
        
        # Doubly linked list sentinel nodes
        self.head = CacheNode("__head__", None, 0)
        self.tail = CacheNode("__tail__", None, 0)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.hits = 0
        self.misses = 0

    def _remove(self, node: CacheNode):
        prev = node.prev
        nxt = node.next
        if prev:
            prev.next = nxt
        if nxt:
            nxt.prev = prev

    def _add_to_front(self, node: CacheNode):
        node.next = self.head.next
        node.prev = self.head
        if self.head.next:
            self.head.next.prev = node
        self.head.next = node

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self.cache:
                self.misses += 1
                return None

            node = self.cache[key]
            now = time.time()
            if now > node.expires_at:
                # Expired
                self._remove(node)
                del self.cache[key]
                self.misses += 1
                return None

            # Move to front (most recently used)
            self._remove(node)
            self._add_to_front(node)
            self.hits += 1
            return node.value

    def set(self, key: str, value: Any, ttl_s: Optional[float] = None) -> None:
        ttl = ttl_s if ttl_s is not None else self.default_ttl_s
        expires_at = time.time() + ttl

        with self._lock:
            if key in self.cache:
                node = self.cache[key]
                node.value = value
                node.expires_at = expires_at
                self._remove(node)
                self._add_to_front(node)
                return

            if len(self.cache) >= self.capacity:
                # Evict least recently used (node before tail)
                lru = self.tail.prev
                if lru and lru != self.head:
                    self._remove(lru)
                    if lru.key in self.cache:
                        del self.cache[lru.key]

            new_node = CacheNode(key, value, expires_at)
            self.cache[key] = new_node
            self._add_to_front(new_node)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100.0) if total > 0 else 0.0
            return {
                "size": len(self.cache),
                "capacity": self.capacity,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_pct": round(hit_rate, 1)
            }

    def clear(self):
        with self._lock:
            self.cache.clear()
            self.head.next = self.tail
            self.tail.prev = self.head


def make_cache_key(prefix: str, payload: Any) -> str:
    """Generates a consistent MD5 hash cache key."""
    raw = f"{prefix}:{repr(payload)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# Global Singleton Cache Instance
system_cache = LRUTTLCache(capacity=500, default_ttl_s=300.0)


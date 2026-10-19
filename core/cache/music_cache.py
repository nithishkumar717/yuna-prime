"""
High-Performance Multi-Tier Music Resolution Cache and In-Flight Coalescer for YUNA.
"""
import time
import copy
import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable
from collections import OrderedDict

class MusicResolutionCache:
    _instance: Optional["MusicResolutionCache"] = None

    def __init__(self):
        self._query_cache: OrderedDict[str, tuple[List[Dict[str, Any]], float, float]] = OrderedDict()
        self._max_query_cache: int = 1500
        self._default_query_ttl: float = 14400.0  # 4 hours
        self._stream_cache: OrderedDict[str, tuple[Dict[str, Any], float, float]] = OrderedDict()
        self._max_stream_cache: int = 500
        self._default_stream_ttl: float = 1800.0  # 30 minutes
        self._negative_cache: Dict[str, float] = {}
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "MusicResolutionCache":
        if cls._instance is None:
            cls._instance = MusicResolutionCache()
        return cls._instance

    @staticmethod
    def _normalize_key(query: str) -> str:
        if not query:
            return ""
        q = str(query).strip().lower()
        if q.startswith("ytsearch:"):
            q = q[9:].strip()
        elif q.startswith("ytsearch5:"):
            q = q[10:].strip()
        return q

    def get_query(self, query: str) -> Optional[List[Dict[str, Any]]]:
        key = self._normalize_key(query)
        if not key:
            return None
        now = time.time()
        neg_expiry = self._negative_cache.get(key)
        if neg_expiry:
            if now < neg_expiry:
                return []
            else:
                self._negative_cache.pop(key, None)
        entry = self._query_cache.get(key)
        if not entry:
            return None
        tracks, ts, ttl = entry
        if now - ts > ttl:
            self._query_cache.pop(key, None)
            return None
        self._query_cache.move_to_end(key)
        return copy.deepcopy(tracks)

    def set_query(self, query: str, tracks: List[Dict[str, Any]], ttl: Optional[float] = None) -> None:
        key = self._normalize_key(query)
        if not key:
            return
        if not tracks:
            self._negative_cache[key] = time.time() + 300.0
            return
        ttl = ttl or self._default_query_ttl
        now = time.time()
        if key in self._query_cache:
            self._query_cache.move_to_end(key)
        self._query_cache[key] = (copy.deepcopy(tracks), now, ttl)
        while len(self._query_cache) > self._max_query_cache:
            self._query_cache.popitem(last=False)

    def get_stream(self, url: str) -> Optional[Dict[str, Any]]:
        key = str(url).strip()
        if not key:
            return None
        entry = self._stream_cache.get(key)
        if not entry:
            return None
        stream_info, ts, ttl = entry
        now = time.time()
        if now - ts > ttl:
            self._stream_cache.pop(key, None)
            return None
        self._stream_cache.move_to_end(key)
        return copy.deepcopy(stream_info)

    def set_stream(self, url: str, stream_info: Dict[str, Any], ttl: Optional[float] = None) -> None:
        key = str(url).strip()
        if not key or not stream_info or not stream_info.get("stream_url"):
            return
        ttl = ttl or self._default_stream_ttl
        now = time.time()
        if key in self._stream_cache:
            self._stream_cache.move_to_end(key)
        self._stream_cache[key] = (copy.deepcopy(stream_info), now, ttl)
        while len(self._stream_cache) > self._max_stream_cache:
            self._stream_cache.popitem(last=False)

    async def coalesce(self, key_prefix: str, query: str, coro_fn: Callable[[], Awaitable[Any]]) -> Any:
        norm_key = f"{key_prefix}:{self._normalize_key(query)}"
        loop = asyncio.get_running_loop()
        async with self._lock:
            if norm_key in self._in_flight:
                future = self._in_flight[norm_key]
                return await asyncio.shield(future)
            future = loop.create_future()
            self._in_flight[norm_key] = future
        try:
            result = await coro_fn()
            if not future.done():
                future.set_result(result)
            return result
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
            raise
        finally:
            async with self._lock:
                self._in_flight.pop(norm_key, None)

    def clear(self) -> None:
        """Clears all query and stream caches."""
        self._query_cache.clear()
        self._stream_cache.clear()
        self._negative_cache.clear()

    def evict_query(self, query: str) -> None:
        """Evicts a specific query from the cache."""
        key = self._normalize_key(query)
        self._query_cache.pop(key, None)
        self._negative_cache.pop(key, None)

music_cache = MusicResolutionCache.get_instance()

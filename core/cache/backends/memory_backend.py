import time
from typing import Dict, Tuple, Optional
from core.cache.backend import CacheBackend


class MemoryBackend(CacheBackend):
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[str, Optional[float]]] = {}

    async def get(self, key: str) -> Optional[str]:
        if key not in self._store:
            return None
        value, expire_at = self._store[key]
        if expire_at and time.time() > expire_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        expire_at = time.time() + ttl if ttl else None
        self._store[key] = (value, expire_at)

    async def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> None:
        self._store.clear()

    async def expire(self, key: str, ttl: int) -> bool:
        if key in self._store:
            value, _ = self._store[key]
            self._store[key] = (value, time.time() + ttl)
            return True
        return False

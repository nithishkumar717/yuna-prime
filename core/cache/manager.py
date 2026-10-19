from typing import Any, Optional, Type, TypeVar
from core.cache.backend import CacheBackend
from core.cache.serializers import JsonSerializer

T = TypeVar("T")


class CacheManager:
    def __init__(self, backend: CacheBackend) -> None:
        self.backend = backend

    async def get(self, key: str, model: Optional[Type[T]] = None) -> Optional[Any]:
        data = await self.backend.get(key)
        if not data:
            return None
        return JsonSerializer.deserialize(data, model)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        serialized = JsonSerializer.serialize(value)
        await self.backend.set(key, serialized, ttl)

    async def delete(self, key: str) -> bool:
        return await self.backend.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.backend.exists(key)

    async def clear(self) -> None:
        await self.backend.clear()

    async def expire(self, key: str, ttl: int) -> bool:
        return await self.backend.expire(key, ttl)

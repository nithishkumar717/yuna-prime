import os

files = {}

files["core/cache/__init__.py"] = '''from .manager import CacheManager
from .keys import KeyBuilder
from .ttl import CacheTTL
from .exceptions import CacheError

__all__ = ["CacheManager", "KeyBuilder", "CacheTTL", "CacheError"]
'''

files["core/cache/exceptions.py"] = '''class CacheError(Exception):
    """Base exception for cache layer."""
class SerializationError(CacheError):
    """Raised when serialization fails."""
'''

files["core/cache/ttl.py"] = '''from enum import Enum

class CacheTTL(Enum):
    GUILD_SETTINGS = 1800
    MEMBER_PROFILE = 600
    PERMISSION = 300
    AI_RESPONSE = 900
    DASHBOARD_SESSION = 3600
    MODERATION_STATE = 300
    DEFAULT = 300
'''

files["core/cache/keys.py"] = '''class KeyBuilder:
    @staticmethod
    def guild(guild_id: str | int) -> str:
        return f"guild:{guild_id}"
        
    @staticmethod
    def member(guild_id: str | int, user_id: str | int) -> str:
        return f"member:{guild_id}:{user_id}"
        
    @staticmethod
    def settings(guild_id: str | int) -> str:
        return f"settings:{guild_id}"
'''

files["core/cache/backend.py"] = '''from typing import Protocol, Optional

class CacheBackend(Protocol):
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None: ...
    async def delete(self, key: str) -> bool: ...
    async def exists(self, key: str) -> bool: ...
    async def clear(self) -> None: ...
    async def expire(self, key: str, ttl: int) -> bool: ...
'''

files["core/cache/backends/__init__.py"] = ""

files["core/cache/backends/memory_backend.py"] = '''import time
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
'''

files["core/cache/serializers.py"] = '''import json
from typing import Any, TypeVar, Type, Optional
from pydantic import BaseModel
from core.cache.exceptions import SerializationError

T = TypeVar('T')

class JsonSerializer:
    @staticmethod
    def serialize(data: Any) -> str:
        try:
            if isinstance(data, BaseModel):
                return data.model_dump_json()
            return json.dumps(data)
        except Exception as e:
            raise SerializationError(f"Failed to serialize data: {e}")

    @staticmethod
    def deserialize(data: str, model: Optional[Type[T]] = None) -> Any:
        try:
            parsed = json.loads(data)
            if model and issubclass(model, BaseModel):
                return model(**parsed)
            return parsed
        except Exception as e:
            raise SerializationError(f"Failed to deserialize data: {e}")
'''

files["core/cache/manager.py"] = '''from typing import Any, Optional, Type, TypeVar
from core.cache.backend import CacheBackend
from core.cache.serializers import JsonSerializer

T = TypeVar('T')

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
'''

files["core/cache/tests/test_cache.py"] = '''import pytest
import asyncio
from pydantic import BaseModel
from core.cache.backends.memory_backend import MemoryBackend
from core.cache.manager import CacheManager
from core.cache.keys import KeyBuilder
from core.cache.ttl import CacheTTL

class DummyUser(BaseModel):
    id: int
    name: str

@pytest.mark.asyncio
async def test_cache_set_and_get():
    backend = MemoryBackend()
    cache = CacheManager(backend)
    
    key = KeyBuilder.guild(123)
    await cache.set(key, {"settings": True})
    
    val = await cache.get(key)
    assert val == {"settings": True}

@pytest.mark.asyncio
async def test_cache_pydantic_serialization():
    backend = MemoryBackend()
    cache = CacheManager(backend)
    
    user = DummyUser(id=1, name="Alice")
    await cache.set("user:1", user)
    
    fetched = await cache.get("user:1", DummyUser)
    assert isinstance(fetched, DummyUser)
    assert fetched.name == "Alice"

@pytest.mark.asyncio
async def test_cache_expiration():
    backend = MemoryBackend()
    cache = CacheManager(backend)
    
    await cache.set("expiring", "value", ttl=1)
    
    # Should exist immediately
    assert await cache.exists("expiring") is True
    
    # Wait for expiration
    await asyncio.sleep(1.1)
    
    assert await cache.exists("expiring") is False
'''

base_path = r"d:\server\Yuna V 1.00"
for filepath, content in files.items():
    full_path = os.path.join(base_path, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

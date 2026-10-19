import pytest
import asyncio
from pydantic import BaseModel
from core.cache.backends.memory_backend import MemoryBackend
from core.cache.manager import CacheManager
from core.cache.keys import KeyBuilder


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

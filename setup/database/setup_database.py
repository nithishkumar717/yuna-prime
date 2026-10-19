import os

files = {}

files["database/__init__.py"] = ""
files["database/clients/__init__.py"] = ""
files["database/repositories/__init__.py"] = ""

files["database/exceptions.py"] = '''class InfrastructureError(Exception):
    """Base exception for infrastructure layer."""
    pass

class DatabaseConnectionError(InfrastructureError):
    """Raised when the database connection fails."""
    pass

class DatabaseQueryError(InfrastructureError):
    """Raised when a database query fails."""
    pass

class DocumentNotFoundError(InfrastructureError):
    """Raised when a requested document is not found."""
    pass
'''

files["database/models.py"] = '''from pydantic import BaseModel, Field
from typing import Optional

class BaseDocument(BaseModel):
    """Base Pydantic model for MongoDB documents."""
    id: Optional[str] = Field(alias="_id", default=None)
    
    class Config:
        populate_by_name = True
'''

files["database/clients/mongo_client.py"] = '''import asyncio
from typing import Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from core.config.manager import ConfigManager
from core.logging import DatabaseLogger
from database.exceptions import DatabaseConnectionError

class MongoDBClient:
    """Manages the MongoDB connection pool asynchronously."""
    
    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient[Any]] = None
        self.db: Any = None

    async def connect(self, retries: int = 3, delay: int = 2) -> None:
        config = ConfigManager.get_config()
        uri = str(config.database.mongodb_uri)
        
        for attempt in range(1, retries + 1):
            DatabaseLogger.info(f"Connecting to MongoDB (Attempt {attempt}/{retries})...", event="Connecting")
            try:
                self.client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
                self.db = self.client.get_database("yuna_db")
                await self.client.server_info()
                DatabaseLogger.info("MongoDB connected successfully.", event="Connected")
                return
            except Exception as e:
                DatabaseLogger.warning(f"Failed to connect to MongoDB: {e}", event="ConnectionWarning")
                if attempt < retries:
                    await asyncio.sleep(delay)
                else:
                    DatabaseLogger.error("Exhausted all MongoDB connection retries.", event="ConnectionFailed")
                    raise DatabaseConnectionError(f"Failed to connect to MongoDB after {retries} attempts.") from e

    async def disconnect(self) -> None:
        if self.client:
            self.client.close()
            DatabaseLogger.info("MongoDB connection closed.", event="Disconnected")

    async def health_check(self) -> bool:
        """Pings the MongoDB cluster to verify health."""
        if not self.client:
            return False
        try:
            await self.client.admin.command('ping')
            return True
        except Exception:
            return False
'''

files["database/repositories/base.py"] = '''from typing import TypeVar, Generic, Type, Any, Optional, List, Dict
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorCollection
from database.exceptions import DatabaseQueryError

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T]):
    """Generic repository for MongoDB CRUD operations mapped to Pydantic models."""

    def __init__(self, collection: AsyncIOMotorCollection[Any], model: Type[T]) -> None:
        self.collection = collection
        self.model = model

    async def find_by_id(self, doc_id: Any) -> Optional[T]:
        try:
            doc = await self.collection.find_one({"_id": doc_id})
            return self.model(**doc) if doc else None
        except Exception as e:
            raise DatabaseQueryError(f"Failed to find document by id: {e}") from e

    async def find_one(self, query: Dict[str, Any]) -> Optional[T]:
        try:
            doc = await self.collection.find_one(query)
            return self.model(**doc) if doc else None
        except Exception as e:
            raise DatabaseQueryError(f"Failed to execute find_one: {e}") from e

    async def find_many(self, query: Dict[str, Any], limit: int = 100) -> List[T]:
        try:
            cursor = self.collection.find(query).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [self.model(**doc) for doc in docs]
        except Exception as e:
            raise DatabaseQueryError(f"Failed to execute find_many: {e}") from e

    async def insert(self, entity: T) -> Any:
        try:
            data = entity.model_dump(by_alias=True, exclude_none=True)
            result = await self.collection.insert_one(data)
            return result.inserted_id
        except Exception as e:
            raise DatabaseQueryError(f"Failed to insert document: {e}") from e

    async def update(self, doc_id: Any, entity: T) -> bool:
        try:
            data = entity.model_dump(by_alias=True, exclude_none=True)
            if "_id" in data:
                del data["_id"]
            result = await self.collection.update_one({"_id": doc_id}, {"$set": data})
            return result.modified_count > 0
        except Exception as e:
            raise DatabaseQueryError(f"Failed to update document: {e}") from e

    async def delete(self, doc_id: Any) -> bool:
        try:
            result = await self.collection.delete_one({"_id": doc_id})
            return result.deleted_count > 0
        except Exception as e:
            raise DatabaseQueryError(f"Failed to delete document: {e}") from e
'''

files["database/README.md"] = '''# Yuna Database Layer

Handles MongoDB connectivity and provides an abstract `BaseRepository` mapping BSON data to Pydantic objects.

## Resiliency
The `MongoDBClient` automatically retries connection drops across multiple attempts. Use `health_check()` to trace connection liveness.

## Repositories
Repositories must extend `BaseRepository` and supply the explicit Pydantic model:
```python
class UserRepository(BaseRepository[UserModel]):
    def __init__(self, db: MongoDBClient):
        super().__init__(db.client.get_database("yuna_db")["users"], UserModel)
```
'''

files["database/tests/test_database.py"] = '''import pytest
from unittest.mock import AsyncMock
from pydantic import BaseModel
from database.clients.mongo_client import MongoDBClient
from database.repositories.base import BaseRepository

class DummyModel(BaseModel):
    id: str | None = None
    name: str

@pytest.mark.asyncio
async def test_repository_find_by_id():
    mock_collection = AsyncMock()
    mock_collection.find_one.return_value = {"_id": "123", "name": "Test"}
    
    repo = BaseRepository(mock_collection, DummyModel)
    result = await repo.find_by_id("123")
    
    assert result is not None
    assert result.name == "Test"
    mock_collection.find_one.assert_called_once_with({"_id": "123"})

@pytest.mark.asyncio
async def test_mongo_client_health_check_fail():
    client = MongoDBClient()
    assert await client.health_check() is False
'''

base_path = r"d:\server\Yuna V 1.00"
for filepath, content in files.items():
    full_path = os.path.join(base_path, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

import os

files = {}

files["core/database/__init__.py"] = '''"""
Database Architecture domain providing repository abstractions and transaction management.
"""
'''

files["core/database/repository.py"] = '''from typing import Generic, TypeVar, List, Optional, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase

T = TypeVar("T")

class AbstractRepository(Generic[T]):
    """Generic repository interface for database CRUD operations."""
    
    async def add(self, entity: T, session: Optional[Any] = None) -> None:
        raise NotImplementedError
        
    async def get(self, id: str, session: Optional[Any] = None) -> Optional[T]:
        raise NotImplementedError
        
    async def update(self, id: str, updates: Dict[str, Any], session: Optional[Any] = None) -> None:
        raise NotImplementedError
        
    async def delete(self, id: str, session: Optional[Any] = None) -> None:
        raise NotImplementedError
        
    async def list_all(self, session: Optional[Any] = None) -> List[T]:
        raise NotImplementedError


class MongoRepository(AbstractRepository[Dict[str, Any]]):
    """Concrete repository implementing Mongo/Motor CRUD operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str) -> None:
        self.collection = db[collection_name]
        
    async def add(self, entity: Dict[str, Any], session: Optional[Any] = None) -> None:
        await self.collection.insert_one(entity, session=session)
        
    async def get(self, id: str, session: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"id": id}, session=session)
        
    async def update(self, id: str, updates: Dict[str, Any], session: Optional[Any] = None) -> None:
        await self.collection.update_one({"id": id}, {"$set": updates}, session=session)
        
    async def delete(self, id: str, session: Optional[Any] = None) -> None:
        await self.collection.delete_one({"id": id}, session=session)
        
    async def list_all(self, session: Optional[Any] = None) -> List[Dict[str, Any]]:
        cursor = self.collection.find({}, session=session)
        return await cursor.to_list(length=1000)
'''

files["core/database/unit_of_work.py"] = '''import logging
from typing import Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

class AbstractUnitOfWork:
    """Coordinates transaction boundaries across multiple repositories."""
    
    async def __aenter__(self) -> "AbstractUnitOfWork":
        return self
        
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
            
    async def commit(self) -> None:
        raise NotImplementedError
        
    async def rollback(self) -> None:
        raise NotImplementedError


class MongoUnitOfWork(AbstractUnitOfWork):
    """Concrete Unit of Work managing motor database sessions and transactions."""
    
    def __init__(self, client: AsyncIOMotorClient) -> None:
        self.client = client
        self.session: Optional[Any] = None
        self.has_transaction = False
        
    async def __aenter__(self) -> "MongoUnitOfWork":
        self.session = await self.client.start_session()
        try:
            self.session.start_transaction()
            self.has_transaction = True
        except OperationFailure as e:
            # Standalone Mongo servers do not support transactions.
            # We log a warning and proceed without a transaction block.
            logging.warning(f"Transactions not supported by server: {e}. Falling back to non-transactional mode.")
            self.has_transaction = False
        return self
        
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if exc_type:
                await self.rollback()
            else:
                await self.commit()
        finally:
            if self.session:
                self.session.end_session()
                self.session = None
            
    async def commit(self) -> None:
        if self.session and self.has_transaction and self.session.in_transaction:
            await self.session.commit_transaction()
            
    async def rollback(self) -> None:
        if self.session and self.has_transaction and self.session.in_transaction:
            await self.session.abort_transaction()
'''

files["core/database/tests/test_database_persistence.py"] = '''import pytest
from unittest.mock import AsyncMock, MagicMock
from core.database.repository import MongoRepository
from core.database.unit_of_work import MongoUnitOfWork

@pytest.mark.asyncio
async def test_repository_crud_operations():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock
    
    repo = MongoRepository(db_mock, "test_collection")
    
    # Test Add
    entity = {"id": "1", "data": "value"}
    await repo.add(entity)
    collection_mock.insert_one.assert_called_once_with(entity, session=None)
    
    # Test Get
    collection_mock.find_one.return_value = entity
    res = await repo.get("1")
    assert res == entity
    collection_mock.find_one.assert_called_once_with({"id": "1"}, session=None)
    
    # Test Update
    await repo.update("1", {"data": "new_value"})
    collection_mock.update_one.assert_called_once_with({"id": "1"}, {"$set": {"data": "new_value"}}, session=None)
    
    # Test Delete
    await repo.delete("1")
    collection_mock.delete_one.assert_called_once_with({"id": "1"}, session=None)

@pytest.mark.asyncio
async def test_unit_of_work_transaction_commit():
    client_mock = AsyncMock()
    session_mock = AsyncMock()
    client_mock.start_session.return_value = session_mock
    session_mock.in_transaction = True
    
    async with MongoUnitOfWork(client_mock) as uow:
        pass
        
    client_mock.start_session.assert_called_once()
    session_mock.start_transaction.assert_called_once()
    session_mock.commit_transaction.assert_called_once()
    session_mock.abort_transaction.assert_not_called()
    session_mock.end_session.assert_called_once()

@pytest.mark.asyncio
async def test_unit_of_work_transaction_rollback():
    client_mock = AsyncMock()
    session_mock = AsyncMock()
    client_mock.start_session.return_value = session_mock
    session_mock.in_transaction = True
    
    try:
        async with MongoUnitOfWork(client_mock) as uow:
            raise ValueError("Simulated write failure")
    except ValueError:
        pass
        
    client_mock.start_session.assert_called_once()
    session_mock.start_transaction.assert_called_once()
    session_mock.commit_transaction.assert_not_called()
    session_mock.abort_transaction.assert_called_once()
    session_mock.end_session.assert_called_once()
'''

base_path = r"d:\server\Yuna V 1.00"
for filepath, content in files.items():
    full_path = os.path.join(base_path, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
print("Database persistence core files written successfully.")

from typing import Generic, TypeVar, List, Optional, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase

T = TypeVar("T")


class AbstractRepository(Generic[T]):
    """Generic repository interface for database CRUD operations."""

    async def add(self, entity: T, session: Optional[Any] = None) -> None:
        raise NotImplementedError

    async def get(self, id: str, session: Optional[Any] = None) -> Optional[T]:
        raise NotImplementedError

    async def update(
        self, id: str, updates: Dict[str, Any], session: Optional[Any] = None
    ) -> None:
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

    async def get(
        self, id: str, session: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"id": id}, session=session)

    async def update(
        self, id: str, updates: Dict[str, Any], session: Optional[Any] = None
    ) -> None:
        await self.collection.update_one({"id": id}, {"$set": updates}, session=session)

    async def delete(self, id: str, session: Optional[Any] = None) -> None:
        await self.collection.delete_one({"id": id}, session=session)

    async def list_all(self, session: Optional[Any] = None) -> List[Dict[str, Any]]:
        cursor = self.collection.find({}, session=session)
        return await cursor.to_list(length=1000)

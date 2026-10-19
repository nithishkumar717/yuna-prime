import logging
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
            logging.warning(
                f"Transactions not supported by server: {e}. Falling back to non-transactional mode."
            )
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

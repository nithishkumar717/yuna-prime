import pytest
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
    collection_mock.update_one.assert_called_once_with(
        {"id": "1"}, {"$set": {"data": "new_value"}}, session=None
    )

    # Test Delete
    await repo.delete("1")
    collection_mock.delete_one.assert_called_once_with({"id": "1"}, session=None)


@pytest.mark.asyncio
async def test_unit_of_work_transaction_commit():
    client_mock = AsyncMock()
    session_mock = AsyncMock()
    session_mock.start_transaction = MagicMock()
    session_mock.end_session = MagicMock()
    client_mock.start_session.return_value = session_mock
    session_mock.in_transaction = True

    async with MongoUnitOfWork(client_mock):
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
    session_mock.start_transaction = MagicMock()
    session_mock.end_session = MagicMock()
    client_mock.start_session.return_value = session_mock
    session_mock.in_transaction = True

    try:
        async with MongoUnitOfWork(client_mock):
            raise ValueError("Simulated write failure")
    except ValueError:
        pass

    client_mock.start_session.assert_called_once()
    session_mock.start_transaction.assert_called_once()
    session_mock.commit_transaction.assert_not_called()
    session_mock.abort_transaction.assert_called_once()
    session_mock.end_session.assert_called_once()

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.database.repositories.recommendation_repository import RecommendationRepository, AIAdvisoryRecord
from core.database.repositories.prompt_repository import PromptRepository, PromptVersionRecord
from core.database.repositories.provider_metrics_repository import ProviderMetricsRepository, ProviderMetricRecord, FailoverEventRecord
from core.database.repositories.conversation_repository import ConversationRepository, ConversationRecord
from core.database.repositories.ai_repository import AIRepository


@pytest.mark.asyncio
async def test_recommendation_repository():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    repo = RecommendationRepository(db_mock)

    record = AIAdvisoryRecord(
        id="adv-1",
        guild_id=1122,
        type="ocr",
        target_id=8888,
        input_data="buy cheap tokens!",
        output_data={"classification": "PHISHING", "confidence": 0.98},
        timestamp=1620000000.0
    )

    # Test Save
    await repo.save_advisory_record(record)
    collection_mock.replace_one.assert_called_once()

    # Test Get by ID
    collection_mock.find_one.return_value = {
        "id": "adv-1",
        "guild_id": 1122,
        "type": "ocr",
        "payload": record.model_dump()
    }
    retrieved = await repo.get_by_id("adv-1")
    assert retrieved is not None
    assert retrieved.id == "adv-1"
    assert retrieved.output_data["classification"] == "PHISHING"

    # Test list_by_target (requires sorting)
    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [{
        "id": "adv-1",
        "guild_id": 1122,
        "type": "ocr",
        "payload": record.model_dump()
    }]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    results = await repo.list_by_target(guild_id=1122, target_id=8888)
    assert len(results) == 1
    assert results[0].type == "ocr"
    cursor_mock.sort.assert_called_with("timestamp", -1)

    # Test list_by_type
    results_type = await repo.list_by_type(guild_id=1122, type_str="ocr")
    assert len(results_type) == 1
    collection_mock.find.assert_called_with({"guild_id": 1122, "type": "ocr"}, session=None)

    # Test purge_older_than
    await repo.purge_older_than(1620000000.0)
    collection_mock.delete_many.assert_called_once_with({"timestamp": {"$lt": 1620000000.0}}, session=None)


@pytest.mark.asyncio
async def test_prompt_repository():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    repo = PromptRepository(db_mock)

    record = PromptVersionRecord(
        prompt_id="moderation",
        version=2,
        system_prompt="Analyze safety.",
        json_schema={"type": "object"},
        timestamp=1620000000.0
    )

    # Test save
    await repo.save_prompt_version(record)
    collection_mock.replace_one.assert_called_once()

    # Test get_prompt_version
    collection_mock.find_one.return_value = {
        "id": "moderation:2",
        "prompt_id": "moderation",
        "version": 2,
        "payload": record.model_dump()
    }
    retrieved = await repo.get_prompt_version("moderation", 2)
    assert retrieved is not None
    assert retrieved.version == 2
    assert retrieved.system_prompt == "Analyze safety."

    # Test get_active_prompt (gets highest version)
    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [{
        "id": "moderation:2",
        "payload": record.model_dump()
    }]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    active = await repo.get_active_prompt("moderation")
    assert active is not None
    assert active.version == 2
    cursor_mock.sort.assert_called_with("version", -1)


@pytest.mark.asyncio
async def test_provider_metrics_repository():
    db_mock = MagicMock()
    metrics_collection_mock = AsyncMock()
    failover_collection_mock = AsyncMock()
    
    def get_collection(name):
        if name == "ai_provider_metrics":
            return metrics_collection_mock
        elif name == "ai_provider_failovers":
            return failover_collection_mock
        return AsyncMock()
        
    db_mock.__getitem__.side_effect = get_collection

    repo = ProviderMetricsRepository(db_mock)

    metric = ProviderMetricRecord(provider_name="google", latency_ms=150.0, token_usage=45, timestamp=1620000000.0)
    failover = FailoverEventRecord(failed_provider="openai", fallback_provider="google", reason="Timeout", timestamp=1620000000.0)

    # Test save_metric
    await repo.save_metric(metric)
    metrics_collection_mock.insert_one.assert_called_once()

    # Test save_failover
    await repo.save_failover(failover)
    failover_collection_mock.insert_one.assert_called_once()

    # Test get_average_latency
    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [
        {"payload": {"latency_ms": 100.0}},
        {"payload": {"latency_ms": 200.0}}
    ]
    metrics_collection_mock.find = MagicMock(return_value=cursor_mock)

    avg = await repo.get_average_latency("google")
    assert avg == 150.0
    cursor_mock.sort.assert_called_with("timestamp", -1)

    # Test list_failovers
    cursor_mock_failover = AsyncMock()
    cursor_mock_failover.sort = MagicMock(return_value=cursor_mock_failover)
    cursor_mock_failover.to_list.return_value = [
        {"payload": failover.model_dump()}
    ]
    failover_collection_mock.find = MagicMock(return_value=cursor_mock_failover)

    failovers = await repo.list_failovers()
    assert len(failovers) == 1
    assert failovers[0].failed_provider == "openai"


@pytest.mark.asyncio
async def test_conversation_repository():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    repo = ConversationRepository(db_mock)

    record = ConversationRecord(
        conversation_id="conv-1",
        guild_id=1122,
        user_id=4444,
        messages=["hello", "help"],
        summary="User asked for help.",
        timestamp=1620000000.0
    )

    # Test save
    await repo.save_conversation(record)
    collection_mock.replace_one.assert_called_once()

    # Test get
    collection_mock.find_one.return_value = {
        "id": "conv-1",
        "guild_id": 1122,
        "payload": record.model_dump()
    }
    retrieved = await repo.get_conversation("conv-1")
    assert retrieved is not None
    assert retrieved.conversation_id == "conv-1"

    # Test list user conversations
    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [{
        "id": "conv-1",
        "guild_id": 1122,
        "payload": record.model_dump()
    }]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    conversations = await repo.list_user_conversations(guild_id=1122, user_id=4444)
    assert len(conversations) == 1
    assert conversations[0].summary == "User asked for help."
    cursor_mock.sort.assert_called_with("timestamp", -1)


@pytest.mark.asyncio
async def test_ai_repository_aggregate():
    db_mock = MagicMock()
    repo = AIRepository(db_mock)

    assert repo.recommendations is not None
    assert repo.prompts is not None
    assert repo.provider_metrics is not None
    assert repo.conversations is not None

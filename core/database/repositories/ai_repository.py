from motor.motor_asyncio import AsyncIOMotorDatabase
from .recommendation_repository import RecommendationRepository
from .prompt_repository import PromptRepository
from .provider_metrics_repository import ProviderMetricsRepository
from .conversation_repository import ConversationRepository


class AIRepository:
    """Unified Aggregate Coordinator grouping Yuna's AI and LLM persistence repositories."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.recommendations = RecommendationRepository(db)
        self.prompts = PromptRepository(db)
        self.provider_metrics = ProviderMetricsRepository(db)
        self.conversations = ConversationRepository(db)

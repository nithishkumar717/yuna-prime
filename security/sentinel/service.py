from core.services.base import BaseService
from core.services.models import ServiceCategory
from core.container import Container
from core.event_bus import EventDispatcher
from .pipeline import ThreatPipeline
from .policy import PolicyEngine
from .response import ResponseEngine
from .engines.risk_engine import RiskEngine
from .engines.trust_engine import TrustEngine
from .engines.reputation_engine import ReputationEngine



class SentinelService(BaseService):
    """Core domain service binding the security pipeline to the Application."""

    def __init__(self, container: Container, event_bus: EventDispatcher) -> None:
        super().__init__(
            name="SentinelService", category=ServiceCategory.DOMAIN, event_bus=event_bus
        )
        self.container = container
        self.event_bus = event_bus

        self.policy_engine = PolicyEngine()
        self.response_engine = ResponseEngine()
        self.pipeline = ThreatPipeline(
            policy_engine=self.policy_engine, response_engine=self.response_engine
        )

    async def _on_start(self) -> None:
        from security.authorization.permission_guard import PermissionGuard
        from security.authorization.role_guard import RoleGuard

        # Load the Pipeline sequentially
        self.pipeline.add_analyzer(RiskEngine())
        self.pipeline.add_analyzer(PermissionGuard())
        self.pipeline.add_analyzer(RoleGuard())
        self.pipeline.add_analyzer(TrustEngine())
        self.pipeline.add_analyzer(ReputationEngine())


        self.logger.info("Sentinel Defense Pipeline Online.", event="SentinelStart")

    async def _on_stop(self) -> None:
        self.logger.info("Sentinel Defense Pipeline Offline.", event="SentinelStop")

from typing import List, Any
from .models import ThreatLevel, SecurityEvent
from .policy import PolicyEngine
from .response import ResponseEngine
from core.logging import get_logger


class ThreatAnalyzer:
    """Abstract interface for all sentinel defense-in-depth security engines."""

    async def analyze(self, payload: Any, current_threat: ThreatLevel) -> ThreatLevel:
        raise NotImplementedError


class ThreatPipeline:
    """Orchestrates sequential evaluation of payloads against registered analyzers and forwards to PolicyEngine."""

    def __init__(
        self, policy_engine: PolicyEngine, response_engine: ResponseEngine
    ) -> None:
        self.analyzers: List[ThreatAnalyzer] = []
        self.policy_engine = policy_engine
        self.response_engine = response_engine
        self.logger = get_logger("SECURITY", "ThreatPipeline")

    def add_analyzer(self, analyzer: ThreatAnalyzer) -> None:
        self.analyzers.append(analyzer)

    async def evaluate(
        self, source: str, target_id: int, payload: Any
    ) -> SecurityEvent:
        current_threat = ThreatLevel.NONE

        # Sequentially pass the accumulating threat through the analyzers
        for analyzer in self.analyzers:
            current_threat = await analyzer.analyze(payload, current_threat)

        action = await self.policy_engine.evaluate(current_threat, payload, target_id)
        await self.response_engine.execute(action, payload, target_id)

        event = SecurityEvent(
            event_source=source,
            target_id=target_id,
            threat_level=current_threat,
            action_taken=action,
            reason=f"Pipeline evaluated max threat as {current_threat.name}",
        )
        self.logger.info(
            f"Payload from {source} evaluated: {current_threat.name} -> {action.name}",
            event="ThreatEvaluated",
        )
        return event

import pytest
import json
from unittest.mock import MagicMock
from security.incident_center.incident_manager import IncidentManager
from security.incident_center.audit_export import AuditExporter
from security.incident_center.service import IncidentCenterService
from security.sentinel.pipeline import SecurityEvent
from security.sentinel.models import ThreatLevel, SecurityAction


def test_incident_manager_correlates_evidence():
    manager = IncidentManager()

    # 1. First event for Actor 999 should spawn a new case
    case1 = manager.process_security_event(
        actor_id=999,
        source="TestDetector1",
        payload={"alert": "Ping"},
        current_time=1.0,
    )
    assert case1.actor_id == 999
    assert len(case1.evidence_timeline) == 1

    # 2. Second event for Actor 999 should Correlate to the exact same case
    case2 = manager.process_security_event(
        actor_id=999,
        source="TestDetector2",
        payload={"alert": "Pong"},
        current_time=2.0,
    )
    assert case1.incident_id == case2.incident_id
    assert len(case2.evidence_timeline) == 2

    # 3. First event for Actor 555 should spawn a distinctly new case
    case3 = manager.process_security_event(
        actor_id=555, source="TestDetector1", payload={"alert": "New"}, current_time=3.0
    )
    assert case3.incident_id != case1.incident_id
    assert len(case3.evidence_timeline) == 1


def test_audit_exporter_serialization():
    manager = IncidentManager()
    exporter = AuditExporter()

    case = manager.process_security_event(
        actor_id=777, source="Core", payload={"data": True}, current_time=1.0
    )

    json_export = exporter.export_json(case)
    data = json.loads(json_export)

    assert data["actor_id"] == 777
    assert data["status"] == "OPEN"
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["source"] == "Core"
    assert "hash_signature" in data["evidence"][0]


@pytest.mark.asyncio
async def test_incident_center_service_integration():
    container = MagicMock()
    bus = MagicMock()
    bus.register = MagicMock()

    service = IncidentCenterService(container, bus)

    # Simulate an actual EventBus SecurityEvent outputting from the ThreatPipeline
    event = SecurityEvent(
        event_source="Test",
        target_id=123,
        threat_level=ThreatLevel.HIGH,
        action_taken=SecurityAction.QUARANTINE,
        reason="Test Trigger",
    )

    await service._handle_security_event(event)

    # Validate the manager correctly caught and mapped the event
    case = service.manager.correlation.find_active_case(actor_id=123)
    assert case is not None
    assert case.actor_id == 123
    assert len(case.evidence_timeline) == 1
    assert case.evidence_timeline[0].payload["action_taken"] == "QUARANTINE"

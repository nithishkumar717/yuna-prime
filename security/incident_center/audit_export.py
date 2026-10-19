import json
from .models import IncidentCase


class AuditExporter:
    """Transforms an IncidentCase into pristine structural reports intended for Mod Logs or SIEM."""

    def export_json(self, case: IncidentCase) -> str:
        data = {
            "incident_id": case.incident_id,
            "actor_id": case.actor_id,
            "start_time": case.start_time,
            "status": case.status.value,
            "evidence": [
                {
                    "timestamp": e.timestamp,
                    "source": e.source,
                    "payload": e.payload,
                    "hash_signature": e.hash_signature,
                }
                for e in case.evidence_timeline
            ],
        }
        return json.dumps(data, indent=2)

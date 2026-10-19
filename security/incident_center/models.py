from enum import Enum
from typing import List, Dict, Any
from dataclasses import dataclass, field


class IncidentStatus(Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ARCHIVED = "ARCHIVED"


@dataclass
class ForensicEvidence:
    timestamp: float
    source: str
    payload: Dict[str, Any]
    hash_signature: str


@dataclass
class IncidentCase:
    incident_id: str
    actor_id: int
    start_time: float
    status: IncidentStatus
    evidence_timeline: List[ForensicEvidence] = field(default_factory=list)

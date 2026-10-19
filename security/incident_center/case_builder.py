import hashlib
import json
import time
from typing import Dict, Any
from .models import ForensicEvidence


class CaseBuilder:
    """Wraps raw event payloads into ForensicEvidence structures ensuring immutability."""

    def create_evidence(
        self, source: str, payload: Dict[str, Any], current_time: float = 0.0
    ) -> ForensicEvidence:
        now = current_time if current_time > 0 else time.time()

        # Create a basic hash signature mapping state for immutability simulation
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hashlib.sha256(f"{now}:{source}:{payload_str}".encode()).hexdigest()

        return ForensicEvidence(
            timestamp=now, source=source, payload=payload, hash_signature=signature
        )

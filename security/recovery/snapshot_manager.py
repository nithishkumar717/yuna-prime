import uuid
import time
import json
import hashlib
from typing import Dict, Any
from .models import Snapshot


class SnapshotManager:
    """Simulates extracting structural state of a server to generate deterministic records."""

    def create_snapshot(
        self, guild_id: int, state_payload: Dict[str, Any], current_time: float = 0.0
    ) -> Snapshot:
        now = current_time if current_time > 0 else time.time()

        # Serialize and hash the state to ensure cryptographic immutability
        payload_str = json.dumps(state_payload, sort_keys=True)
        signature = hashlib.sha256(
            f"{now}:{guild_id}:{payload_str}".encode()
        ).hexdigest()

        return Snapshot(
            snapshot_id=str(uuid.uuid4()),
            guild_id=guild_id,
            timestamp=now,
            payload=state_payload,
            hash_signature=signature,
        )

import json
import hashlib
from .models import Snapshot


class IntegrityError(Exception):
    pass


class IntegrityChecker:
    """Enforces cryptographic verification of Snapshot structures."""

    def verify(self, snapshot: Snapshot) -> bool:
        payload_str = json.dumps(snapshot.payload, sort_keys=True)
        expected_signature = hashlib.sha256(
            f"{snapshot.timestamp}:{snapshot.guild_id}:{payload_str}".encode()
        ).hexdigest()

        if expected_signature != snapshot.hash_signature:
            raise IntegrityError(
                f"Snapshot {snapshot.snapshot_id} has been cryptographically tampered with!"
            )

        return True

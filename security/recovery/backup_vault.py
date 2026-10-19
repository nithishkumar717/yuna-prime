from typing import Dict, Optional
from .models import Snapshot
from .integrity_checker import IntegrityChecker


class BackupVault:
    """Secure immutable storage repository for structural Snapshots."""

    def __init__(self) -> None:
        self.snapshots: Dict[str, Snapshot] = {}
        self.checker = IntegrityChecker()

    def store(self, snapshot: Snapshot) -> None:
        # Validate integrity prior to storage
        self.checker.verify(snapshot)
        self.snapshots[snapshot.snapshot_id] = snapshot

    def retrieve(self, snapshot_id: str) -> Optional[Snapshot]:
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot:
            # Validate integrity upon retrieval to ensure no at-rest manipulation
            self.checker.verify(snapshot)
        return snapshot

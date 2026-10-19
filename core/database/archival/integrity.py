import hashlib
from typing import Union


class IntegrityVerifier:
    """Calculates and validates cryptographic SHA-256 hashes to guarantee archive tamper detection."""

    @staticmethod
    def calculate_sha256(data: Union[str, bytes]) -> str:
        """Computes the SHA-256 hex digest for string or byte content."""
        raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
        return hashlib.sha256(raw_bytes).hexdigest()

    @classmethod
    def verify_integrity(cls, data: Union[str, bytes], expected_hash: str) -> bool:
        """Verifies if computed data hash matches expected SHA-256 signature."""
        computed = cls.calculate_sha256(data)
        return computed.lower() == expected_hash.lower()

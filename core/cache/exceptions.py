class CacheError(Exception):
    """Base exception for cache layer."""


class SerializationError(CacheError):
    """Raised when serialization fails."""

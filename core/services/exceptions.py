class ServiceError(Exception):
    """Base exception for the service framework."""

    pass


class ServiceLifecycleError(ServiceError):
    """Raised when an illegal state transition occurs."""

    pass

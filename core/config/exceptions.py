class ConfigurationError(Exception):
    """Base class for configuration exceptions."""

    pass


class ConfigurationValidationError(ConfigurationError):
    """Raised when configuration validation fails."""

    pass


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when a required environment variable is missing."""

    pass

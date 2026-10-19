class UIError(Exception):
    """Base exception for presentation layer and UI component failures."""
    pass


class InvalidThemeError(UIError):
    """Raised when an invalid or unregistered theme token is specified."""
    pass


class ComponentRenderError(UIError):
    """Raised when a UI component fails multi-target rendering (Embed, HTML, Text)."""
    pass

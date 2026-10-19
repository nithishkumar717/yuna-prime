from .models import SystemEvent


class BotReadyEvent(SystemEvent):
    """Fired when the bot has successfully started."""

    pass


class DatabaseConnectedEvent(SystemEvent):
    """Fired when MongoDB establishes connection."""

    pass

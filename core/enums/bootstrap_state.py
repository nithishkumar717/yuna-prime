from enum import Enum, auto

class BootstrapState(Enum):
    INITIALIZING = auto()
    ENVIRONMENT_READY = auto()
    CONFIG_READY = auto()
    LOGGING_READY = auto()
    CONTAINER_READY = auto()
    DATABASE_READY = auto()
    CACHE_READY = auto()
    SERVICES_READY = auto()
    BOT_READY = auto()
    RUNNING = auto()
    FAILED = auto()

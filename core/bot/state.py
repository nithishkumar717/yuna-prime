from dataclasses import dataclass, field
import datetime


@dataclass
class BotState:
    startup_timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    is_ready: bool = False
    connected_guilds: int = 0

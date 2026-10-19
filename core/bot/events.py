from core.event_bus.models import DomainEvent


class MemberJoinedEvent(DomainEvent):
    member_id: int
    guild_id: int
    member_name: str

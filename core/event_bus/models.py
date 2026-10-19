from pydantic import BaseModel, Field
import uuid
import datetime


class BaseEvent(BaseModel):
    """Abstract base class for all events."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)


class DomainEvent(BaseEvent):
    """Events originating from business logic domains."""

    pass


class SystemEvent(BaseEvent):
    """Events originating from infrastructure lifecycle."""

    pass

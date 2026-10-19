import json
from typing import Any, TypeVar, Type, Optional
from pydantic import BaseModel
from core.cache.exceptions import SerializationError

T = TypeVar("T")


class JsonSerializer:
    @staticmethod
    def serialize(data: Any) -> str:
        try:
            if isinstance(data, BaseModel):
                return data.model_dump_json()
            return json.dumps(data)
        except Exception as e:
            raise SerializationError(f"Failed to serialize data: {e}")

    @staticmethod
    def deserialize(data: str, model: Optional[Type[T]] = None) -> Any:
        try:
            parsed = json.loads(data)
            if model and issubclass(model, BaseModel):
                return model(**parsed)
            return parsed
        except Exception as e:
            raise SerializationError(f"Failed to deserialize data: {e}")

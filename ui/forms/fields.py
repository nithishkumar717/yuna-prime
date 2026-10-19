from typing import Optional, List
from pydantic import BaseModel, Field


class FormField(BaseModel):
    """Abstract base class for all typed form fields."""
    key: str
    label: str
    placeholder: Optional[str] = None
    required: bool = True
    help_text: Optional[str] = None


class StringField(FormField):
    """Text string input field supporting length bounds and multiline paragraph style."""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    multiline: bool = False
    regex_pattern: Optional[str] = None


class IntegerField(FormField):
    """Numeric integer input field supporting range bounds."""
    min_value: Optional[int] = None
    max_value: Optional[int] = None


class ChoiceOption(BaseModel):
    """Choice item inside a ChoiceField."""
    label: str
    value: str


class ChoiceField(FormField):
    """Selection choice field providing predefined options."""
    choices: List[ChoiceOption] = Field(default_factory=list)

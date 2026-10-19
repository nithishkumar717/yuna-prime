from typing import Optional, List, Dict, Any
from ui.foundation.base_component import BaseUIComponent
from ui.foundation.theme import ThemeEngine
from core.commands.interactions.modals import ModalComponent
from .fields import FormField, StringField, IntegerField, ChoiceField, ChoiceOption
from .validation import FormValidator
from .serializers import FormSerializer


class FormBuilder(BaseUIComponent):
    """Fluent Form schema builder supporting field registration, input validation, and multi-target rendering."""

    def __init__(self, title: str = "Form", custom_id: str = "form:default") -> None:
        self._title = title
        self._custom_id = custom_id
        self._fields: List[FormField] = []

    def set_title(self, title: str) -> "FormBuilder":
        self._title = title
        return self

    def set_custom_id(self, custom_id: str) -> "FormBuilder":
        self._custom_id = custom_id
        return self

    def add_string_field(
        self,
        key: str,
        label: str,
        placeholder: Optional[str] = None,
        required: bool = True,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        multiline: bool = False,
        regex_pattern: Optional[str] = None,
        help_text: Optional[str] = None
    ) -> "FormBuilder":
        field = StringField(
            key=key,
            label=label,
            placeholder=placeholder,
            required=required,
            min_length=min_length,
            max_length=max_length,
            multiline=multiline,
            regex_pattern=regex_pattern,
            help_text=help_text
        )
        self._fields.append(field)
        return self

    def add_integer_field(
        self,
        key: str,
        label: str,
        placeholder: Optional[str] = None,
        required: bool = True,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        help_text: Optional[str] = None
    ) -> "FormBuilder":
        field = IntegerField(
            key=key,
            label=label,
            placeholder=placeholder,
            required=required,
            min_value=min_value,
            max_value=max_value,
            help_text=help_text
        )
        self._fields.append(field)
        return self

    def add_choice_field(
        self,
        key: str,
        label: str,
        choices: List[ChoiceOption],
        placeholder: Optional[str] = None,
        required: bool = True,
        help_text: Optional[str] = None
    ) -> "FormBuilder":
        field = ChoiceField(
            key=key,
            label=label,
            choices=choices,
            placeholder=placeholder,
            required=required,
            help_text=help_text
        )
        self._fields.append(field)
        return self

    def validate_submission(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return FormValidator.validate_inputs(self._fields, inputs)

    def to_modal(self) -> ModalComponent:
        return FormSerializer.to_modal_component(self._title, self._custom_id, self._fields)

    def render_embed(self) -> Dict[str, Any]:
        theme = ThemeEngine.get_active_theme()
        fields_json = []
        for f in self._fields:
            type_str = f.__class__.__name__.replace("Field", "")
            req_str = "Required" if f.required else "Optional"
            fields_json.append(
                {"name": f"📝 {f.label} (`{f.key}`)", "value": f"Type: {type_str} ({req_str})", "inline": True}
            )

        return {
            "title": f"📋 Form: {self._title}",
            "description": f"Custom ID: `{self._custom_id}` ({len(self._fields)} fields configured)",
            "color": theme.colors.primary,
            "fields": fields_json
        }

    def render_html(self) -> str:
        return FormSerializer.to_html_form(self._title, self._custom_id, self._fields)

    def render_text(self) -> str:
        lines: List[str] = [f"=== Form: {self._title} ===", f"ID: {self._custom_id}"]
        for f in self._fields:
            req_str = "*" if f.required else ""
            lines.append(f"• {f.label}{req_str} ({f.key})")
        return "\n".join(lines)

from typing import List
from core.commands.interactions.modals import ModalComponent, TextInputComponent
from .fields import FormField, StringField, IntegerField, ChoiceField


class FormSerializer:
    """Serializes Form schemas into Discord ModalComponent objects and Web Dashboard HTML forms."""

    @classmethod
    def to_modal_component(cls, title: str, custom_id: str, fields: List[FormField]) -> ModalComponent:
        inputs: List[TextInputComponent] = []

        for field in fields:
            style = "paragraph" if isinstance(field, StringField) and field.multiline else "short"

            min_len = field.min_length if isinstance(field, StringField) else None
            max_len = field.max_length if isinstance(field, StringField) else None

            inputs.append(
                TextInputComponent(
                    custom_id=field.key,
                    label=field.label,
                    style=style,
                    placeholder=field.placeholder,
                    required=field.required,
                    min_length=min_len,
                    max_length=max_len
                )
            )

        return ModalComponent(title=title, custom_id=custom_id, inputs=inputs)

    @classmethod
    def to_html_form(cls, title: str, form_id: str, fields: List[FormField]) -> str:
        html: List[str] = [
            f"<form id='{form_id}' class='yuna-form' method='POST'>",
            f"  <h2>{title}</h2>"
        ]

        for field in fields:
            req_attr = "required" if field.required else ""
            placeholder_attr = f"placeholder='{field.placeholder}'" if field.placeholder else ""

            html.append("  <div class='form-group'>")
            html.append(f"    <label for='{field.key}'>{field.label}</label>")

            if isinstance(field, StringField) and field.multiline:
                html.append(
                    f"    <textarea id='{field.key}' name='{field.key}' {placeholder_attr} {req_attr}></textarea>"
                )
            elif isinstance(field, ChoiceField):
                html.append(f"    <select id='{field.key}' name='{field.key}' {req_attr}>")
                for choice in field.choices:
                    html.append(f"      <option value='{choice.value}'>{choice.label}</option>")
                html.append("    </select>")
            elif isinstance(field, IntegerField):
                min_attr = f"min='{field.min_value}'" if field.min_value is not None else ""
                max_attr = f"max='{field.max_value}'" if field.max_value is not None else ""
                html.append(
                    f"    <input type='number' id='{field.key}' name='{field.key}' {min_attr} {max_attr} {placeholder_attr} {req_attr} />"
                )
            else:
                html.append(
                    f"    <input type='text' id='{field.key}' name='{field.key}' {placeholder_attr} {req_attr} />"
                )

            if field.help_text:
                html.append(f"    <small class='form-text'>{field.help_text}</small>")

            html.append("  </div>")

        html.append("  <button type='submit' class='btn btn-primary'>Submit</button>")
        html.append("</form>")

        return "\n".join(html)

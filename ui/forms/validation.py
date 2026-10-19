import re
from typing import Dict, Any, List
from .fields import FormField, StringField, IntegerField, ChoiceField
from .exceptions import FormSubmissionError


class FormValidator:
    """Validates runtime user input submissions against declared Form field constraints."""

    @classmethod
    def validate_inputs(cls, fields: List[FormField], inputs: Dict[str, Any]) -> Dict[str, Any]:
        validated: Dict[str, Any] = {}

        for field in fields:
            val = inputs.get(field.key)

            # Check required fields
            if field.required and (val is None or str(val).strip() == ""):
                raise FormSubmissionError(f"Field '{field.label}' ({field.key}) is required.")

            if val is None or str(val).strip() == "":
                continue

            # Validate StringField
            if isinstance(field, StringField):
                str_val = str(val)
                if field.min_length and len(str_val) < field.min_length:
                    raise FormSubmissionError(
                        f"Field '{field.label}' must be at least {field.min_length} characters (got {len(str_val)})."
                    )
                if field.max_length and len(str_val) > field.max_length:
                    raise FormSubmissionError(
                        f"Field '{field.label}' must be at most {field.max_length} characters (got {len(str_val)})."
                    )
                if field.regex_pattern and not re.match(field.regex_pattern, str_val):
                    raise FormSubmissionError(
                        f"Field '{field.label}' value '{str_val}' does not match pattern '{field.regex_pattern}'."
                    )
                validated[field.key] = str_val

            # Validate IntegerField
            elif isinstance(field, IntegerField):
                try:
                    int_val = int(val)
                except (ValueError, TypeError):
                    raise FormSubmissionError(f"Field '{field.label}' must be a valid integer.")

                if field.min_value is not None and int_val < field.min_value:
                    raise FormSubmissionError(f"Field '{field.label}' must be >= {field.min_value}.")
                if field.max_value is not None and int_val > field.max_value:
                    raise FormSubmissionError(f"Field '{field.label}' must be <= {field.max_value}.")
                validated[field.key] = int_val

            # Validate ChoiceField
            elif isinstance(field, ChoiceField):
                str_val = str(val)
                valid_choice_values = [c.value for c in field.choices]
                if valid_choice_values and str_val not in valid_choice_values:
                    raise FormSubmissionError(
                        f"Field '{field.label}' value '{str_val}' is not a valid option choice."
                    )
                validated[field.key] = str_val
            else:
                validated[field.key] = val

        return validated

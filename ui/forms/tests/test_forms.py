import pytest
from ui.forms import (
    FormBuilder,
    ChoiceOption,
    FormTemplates,
    FormSubmissionError
)


def test_form_builder_and_validation_valid():
    form = (
        FormBuilder(title="Feedback", custom_id="form:feedback")
        .add_string_field("name", label="Your Name", min_length=2, max_length=50)
        .add_integer_field("rating", label="Score", min_value=1, max_value=5)
        .add_choice_field(
            "category",
            label="Type",
            choices=[ChoiceOption(label="Bug", value="bug"), ChoiceOption(label="Feature", value="feature")]
        )
    )

    valid_payload = {"name": "Alice", "rating": 5, "category": "bug"}
    validated = form.validate_submission(valid_payload)

    assert validated["name"] == "Alice"
    assert validated["rating"] == 5
    assert validated["category"] == "bug"


def test_form_validation_errors():
    form = (
        FormBuilder(title="Strict Form", custom_id="form:strict")
        .add_string_field("username", label="Username", min_length=5, required=True)
        .add_integer_field("age", label="Age", min_value=18, max_value=120)
    )

    # Missing required field
    with pytest.raises(FormSubmissionError):
        form.validate_submission({"age": 25})

    # Too short string
    with pytest.raises(FormSubmissionError):
        form.validate_submission({"username": "Bob", "age": 25})

    # Integer out of bounds
    with pytest.raises(FormSubmissionError):
        form.validate_submission({"username": "Charlie", "age": 15})


def test_form_serialization_modal_and_html():
    form = FormTemplates.appeal_submission_form()

    modal = form.to_modal()
    assert modal.title == "Submit Moderation Appeal"
    assert len(modal.inputs) == 3
    assert modal.inputs[0].custom_id == "case_id"
    assert modal.inputs[1].style == "paragraph"  # Paragraph style string
    assert modal.to_dict()["components"][1]["components"][0]["style"] == 2  # Discord integer 2

    html = form.render_html()
    assert "<form id='modal:appeal:submit'" in html
    assert "<textarea id='appeal_reason'" in html

    embed = form.render_embed()
    assert "📋 Form: Submit Moderation Appeal" in embed["title"]

    text = form.render_text()
    assert "=== Form: Submit Moderation Appeal ===" in text


def test_form_templates():
    report_form = FormTemplates.user_report_form()
    assert report_form._title == "Submit Incident Report"
    assert len(report_form._fields) == 3

    ai_form = FormTemplates.ai_prompt_customizer_form()
    assert len(ai_form._fields) == 2

    guild_form = FormTemplates.guild_config_form()
    assert len(guild_form._fields) == 2

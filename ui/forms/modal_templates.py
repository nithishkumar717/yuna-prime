from .builder import FormBuilder
from .fields import ChoiceOption


class FormTemplates:
    """Pre-configured enterprise form factory presets."""

    @staticmethod
    def appeal_submission_form(custom_id: str = "modal:appeal:submit") -> FormBuilder:
        return (
            FormBuilder(title="Submit Moderation Appeal", custom_id=custom_id)
            .add_string_field(
                key="case_id",
                label="Punishment Case ID",
                placeholder="e.g. CAS-1082",
                required=True,
                max_length=32
            )
            .add_string_field(
                key="appeal_reason",
                label="Reason for Appeal",
                placeholder="Explain why the punishment should be reconsidered...",
                required=True,
                min_length=20,
                max_length=1000,
                multiline=True
            )
            .add_string_field(
                key="mitigating_evidence",
                label="Supporting Information / Evidence",
                placeholder="Paste links to screenshots or logs...",
                required=False,
                multiline=True
            )
        )

    @staticmethod
    def user_report_form(custom_id: str = "modal:report:submit") -> FormBuilder:
        return (
            FormBuilder(title="Submit Incident Report", custom_id=custom_id)
            .add_string_field(
                key="target_user",
                label="Target User ID / Mention",
                placeholder="e.g. 123456789012345678",
                required=True,
                max_length=64
            )
            .add_string_field(
                key="offense_type",
                label="Violation Category",
                placeholder="Spam, Harassment, Phishing, Toxic Behavior...",
                required=True,
                max_length=64
            )
            .add_string_field(
                key="incident_details",
                label="Incident Details",
                placeholder="Describe what occurred with timestamps if possible...",
                required=True,
                min_length=15,
                max_length=1000,
                multiline=True
            )
        )

    @staticmethod
    def ai_prompt_customizer_form(custom_id: str = "modal:ai:prompt") -> FormBuilder:
        return (
            FormBuilder(title="Customize AI System Prompt", custom_id=custom_id)
            .add_string_field(
                key="system_prompt",
                label="System Persona Instructions",
                placeholder="Enter system prompt guidance for AI advisory engine...",
                required=True,
                min_length=10,
                max_length=2000,
                multiline=True
            )
            .add_integer_field(
                key="max_tokens",
                label="Max Output Tokens",
                placeholder="512",
                required=True,
                min_value=64,
                max_value=4096
            )
        )

    @staticmethod
    def guild_config_form(custom_id: str = "modal:config:guild") -> FormBuilder:
        return (
            FormBuilder(title="Configure Server Settings", custom_id=custom_id)
            .add_string_field(
                key="mod_log_channel",
                label="Moderation Log Channel ID",
                placeholder="e.g. 987654321098765432",
                required=True,
                max_length=32
            )
            .add_choice_field(
                key="automod_severity",
                label="AutoMod Strictness Mode",
                choices=[
                    ChoiceOption(label="Low (Notify Only)", value="low"),
                    ChoiceOption(label="Medium (Auto Mute)", value="medium"),
                    ChoiceOption(label="Strict (Auto Kick/Ban)", value="strict")
                ],
                required=True
            )
        )

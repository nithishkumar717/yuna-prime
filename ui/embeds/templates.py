from ui.foundation.theme import ThemeEngine
from .builder import EmbedBuilder


class EmbedTemplates:
    """Pre-styled enterprise embed composition factory templates."""

    @staticmethod
    def success(title: str, description: str) -> EmbedBuilder:
        theme = ThemeEngine.get_active_theme()
        return (
            EmbedBuilder()
            .set_title(f"✅ {title}")
            .set_description(description)
            .set_color(theme.colors.success)
        )

    @staticmethod
    def warning(title: str, description: str) -> EmbedBuilder:
        theme = ThemeEngine.get_active_theme()
        return (
            EmbedBuilder()
            .set_title(f"⚠️ {title}")
            .set_description(description)
            .set_color(theme.colors.warning)
        )

    @staticmethod
    def error(title: str, description: str) -> EmbedBuilder:
        theme = ThemeEngine.get_active_theme()
        return (
            EmbedBuilder()
            .set_title(f"❌ {title}")
            .set_description(description)
            .set_color(theme.colors.danger)
        )

    @staticmethod
    def info(title: str, description: str) -> EmbedBuilder:
        theme = ThemeEngine.get_active_theme()
        return (
            EmbedBuilder()
            .set_title(f"ℹ️ {title}")
            .set_description(description)
            .set_color(theme.colors.info)
        )

    @staticmethod
    def security_alert(incident_type: str, target: str, details: str) -> EmbedBuilder:
        theme = ThemeEngine.get_active_theme()
        return (
            EmbedBuilder()
            .set_title(f"🛡️ Sentinel Security Alert - {incident_type}")
            .set_description(details)
            .add_field("Target User / Entity", target, inline=True)
            .add_field("Status", "Action Executed & Logged", inline=True)
            .set_color(theme.colors.danger)
            .set_footer("Yuna Sentinel Security Subsystem")
        )

    @staticmethod
    def moderation_case(
        case_id: str,
        action: str,
        target: str,
        reason: str,
        moderator: str
    ) -> EmbedBuilder:
        theme = ThemeEngine.get_active_theme()
        return (
            EmbedBuilder()
            .set_title(f"⚖️ Moderation Action: Case #{case_id}")
            .set_description(f"Action **{action.upper()}** has been applied.")
            .add_field("Target User", target, inline=True)
            .add_field("Moderator", moderator, inline=True)
            .add_field("Reason", reason, inline=False)
            .set_color(theme.colors.primary)
            .set_footer("Yuna Enterprise Moderation Platform")
        )

    @staticmethod
    def ai_advisory(recommendation_type: str, target: str, reasoning: str) -> EmbedBuilder:
        theme = ThemeEngine.get_active_theme()
        return (
            EmbedBuilder()
            .set_title(f"🤖 AI Advisory Recommendation: {recommendation_type}")
            .set_description(reasoning)
            .add_field("Target Entity", target, inline=True)
            .add_field("Confidence", "High (Advisory Only)", inline=True)
            .set_color(theme.colors.info)
            .set_footer("Yuna AI Enterprise Engine (AI advises. Engines decide.)")
        )

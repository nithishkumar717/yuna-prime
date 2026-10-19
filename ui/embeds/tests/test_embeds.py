import pytest
from ui.embeds import (
    EmbedBuilder,
    EmbedTemplates,
    EmbedLimitExceededError
)


def test_fluent_embed_builder_rendering():
    builder = (
        EmbedBuilder()
        .set_title("System Maintenance")
        .set_description("Database upgrade scheduled for 02:00 UTC.")
        .set_author("Yuna DevOps", icon_url="https://example.com/icon.png")
        .add_field("Duration", "15 minutes", inline=True)
        .add_field("Impact", "Minor latency", inline=True)
        .set_footer("Release v7.1.0")
        .set_color(0x3498DB)
    )

    embed_json = builder.render_embed()
    assert embed_json["title"] == "System Maintenance"
    assert embed_json["author"]["name"] == "Yuna DevOps"
    assert len(embed_json["fields"]) == 2
    assert embed_json["footer"]["text"] == "Release v7.1.0"
    assert embed_json["color"] == 0x3498DB

    html_output = builder.render_html()
    assert "<div class='yuna-embed'" in html_output
    assert "System Maintenance" in html_output

    text_output = builder.render_text()
    assert "=== System Maintenance ===" in text_output
    assert "• Duration: 15 minutes" in text_output


def test_embed_validator_limits():
    # Test title length breach
    long_title_builder = EmbedBuilder().set_title("A" * 300)
    with pytest.raises(EmbedLimitExceededError):
        long_title_builder.render_embed()

    # Test field count breach
    many_fields_builder = EmbedBuilder().set_title("Fields Test")
    for i in range(30):
        many_fields_builder.add_field(f"Field {i}", "val")

    with pytest.raises(EmbedLimitExceededError):
        many_fields_builder.render_embed()


def test_embed_templates():
    sec_alert = EmbedTemplates.security_alert(
        incident_type="Raid Prevention",
        target="User#1234",
        details="Mass join attempt mitigated."
    ).render_embed()

    assert "Sentinel Security Alert" in sec_alert["title"]
    assert sec_alert["footer"]["text"] == "Yuna Sentinel Security Subsystem"

    mod_case = EmbedTemplates.moderation_case(
        case_id="108",
        action="ban",
        target="Spammer#9999",
        reason="Repeated phishing links.",
        moderator="ModAlice"
    ).render_embed()

    assert "Case #108" in mod_case["title"]
    assert mod_case["fields"][0]["value"] == "Spammer#9999"

    ai_advice = EmbedTemplates.ai_advisory(
        recommendation_type="Timeout Escalation",
        target="User#5555",
        reasoning="Pattern of escalating hostility detected over 30 minutes."
    ).render_embed()

    assert "AI Advisory Recommendation" in ai_advice["title"]
    assert "Pattern of escalating hostility" in ai_advice["description"]

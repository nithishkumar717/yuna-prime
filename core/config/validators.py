def validate_discord_token(token: str) -> str:
    """Validates the structure of a Discord bot token."""
    if not token or len(token) < 50:
        raise ValueError("Discord token appears to be invalid or too short.")
    return token

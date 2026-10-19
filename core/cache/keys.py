class KeyBuilder:
    @staticmethod
    def guild(guild_id: str | int) -> str:
        return f"guild:{guild_id}"

    @staticmethod
    def member(guild_id: str | int, user_id: str | int) -> str:
        return f"member:{guild_id}:{user_id}"

    @staticmethod
    def settings(guild_id: str | int) -> str:
        return f"settings:{guild_id}"

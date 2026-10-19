"""Authorization guards and route protectors for Yuna Dashboard."""

from __future__ import annotations

import functools
from typing import Any, Callable
from flask import session, jsonify, request


def require_login(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to require that the user is logged in via Discord OAuth."""
    @functools.wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "user" not in session:
            return jsonify({"error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_guild_permission(guild_id_key: str = "guild_id") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to require that the user has Manage Server permission for a specific guild."""
    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            # First verify login
            if "user" not in session:
                return jsonify({"error": "Not logged in"}), 401

            guild_id = kwargs.get(guild_id_key)
            if not guild_id:
                # Try to get it from request arguments or JSON body
                guild_id = request.args.get(guild_id_key) or (request.json or {}).get(guild_id_key)

            if not guild_id:
                return jsonify({"error": "Missing guild_id parameter"}), 400

            try:
                guild_id_int = int(guild_id)
                if guild_id_int <= 0:
                    return jsonify({"error": "Invalid guild_id parameter"}), 400
            except ValueError:
                return jsonify({"error": "Invalid guild_id parameter"}), 400

            # Check user's manageable guilds in session
            user_guilds = session.get('guilds', [])
            if user_guilds:
                user_guild = next((g for g in user_guilds if str(g.get("id")) == str(guild_id_int)), None)
                if not user_guild:
                    return jsonify({"error": "No manage server permission for this guild"}), 403

            # Bypass live Discord and Bot checks if in mock testing mode
            if session.get("mock_mode"):
                return f(*args, **kwargs)

            # Import the necessary helper functions from app to check user guilds and permission
            # Note: importing locally to avoid circular dependencies
            try:
                from app import get_current_user_guilds, has_manage_guild_permission, bot_instance
            except ImportError:
                import sys
                import app as main_app
                get_current_user_guilds = getattr(main_app, 'get_current_user_guilds', lambda: [])
                has_manage_guild_permission = getattr(main_app, 'has_manage_guild_permission', lambda g: True)
                bot_instance = getattr(main_app, 'bot_instance', None)

            curr_guilds = get_current_user_guilds()
            if not curr_guilds:
                return jsonify({"error": "Could not retrieve user guilds"}), 401

            # Check if user has manage permission and bot is in the guild
            user_g = next((g for g in curr_guilds if int(g["id"]) == guild_id_int), None)
            if not user_g or not has_manage_guild_permission(user_g):
                return jsonify({"error": "No manage server permission for this guild"}), 403

            if not bot_instance or not bot_instance.is_ready():
                return jsonify({"error": "Bot not ready"}), 503

            bot_guild = bot_instance.get_guild(guild_id_int)
            if not bot_guild:
                return jsonify({"error": "Bot is not a member of this guild"}), 404

            return f(*args, **kwargs)
        return decorated_function
    return decorator

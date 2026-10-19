"""Session and OAuth2 authentication hardening middleware."""

from __future__ import annotations

import time
import requests
from datetime import timedelta
from typing import Optional, Dict, Any
from flask import Flask, session


class AuthHardening:
    """Configures secure session settings and authentication lifecycle."""

    def __init__(self, app: Optional[Flask] = None, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=1)
        self._session.mount("https://", adapter)
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Configure secure session defaults on the Flask application."""
        # Use secure cookies
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        
        # Check environment
        is_prod = app.config.get("ENV") == "production"
        app.config["SESSION_COOKIE_SECURE"] = is_prod

        # Session lifecycle: 1 day limit
        app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=1)

        @app.before_request
        def make_session_permanent() -> None:
            session.permanent = True

    def refresh_discord_token(self, refresh_token: str) -> Dict[str, Any]:
        """Call Discord API to refresh the OAuth2 token with pooled connection and fast timeouts."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Discord Client ID and Secret must be configured to refresh tokens.")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        r = self._session.post("https://discord.com/api/v10/oauth2/token", data=data, headers=headers, timeout=(3.05, 5.0))
        r.raise_for_status()
        
        token_data = r.json()
        token_data["expires_at"] = time.time() + token_data.get("expires_in", 604800)
        return token_data

    def get_valid_token(self) -> Optional[str]:
        """Retrieve a valid access token from the session, refreshing it if expired."""
        token_data = session.get("discord_token_data")
        if not token_data:
            return session.get("discord_token")

        expires_at = token_data.get("expires_at", 0)
        if time.time() + 60 > expires_at:
            refresh_token = token_data.get("refresh_token")
            if not refresh_token:
                return None
            try:
                new_token_data = self.refresh_discord_token(refresh_token)
                session["discord_token_data"] = new_token_data
                session["discord_token"] = new_token_data["access_token"]
                return new_token_data["access_token"]
            except Exception as e:
                # Log or handle refresh failure
                print(f"Failed to refresh Discord token: {e}")
                return None

        return token_data.get("access_token")

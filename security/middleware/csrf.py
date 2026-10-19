"""CSRF protection middleware for Flask."""

from __future__ import annotations

import secrets
from typing import Optional, Set
from flask import Flask, request, session, abort


class CSRFProtection:
    """Synchronizer token pattern CSRF protection middleware."""

    def __init__(self, app: Optional[Flask] = None):
        self.exempt_views: Set[str] = set()
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize CSRF protection on the Flask application."""
        
        @app.before_request
        def csrf_protect() -> None:
            # Generate a CSRF token for the session if it doesn't exist
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_hex(32)

            # Skip validation for safe methods
            if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
                return

            # Skip validation for exempt paths
            if request.path in self.exempt_views:
                return

            # Retrieve token from headers or form data or JSON payload
            token = (
                request.headers.get("X-CSRF-Token")
                or request.headers.get("X-CSRFToken")
                or request.form.get("csrf_token")
            )
            if not token and request.is_json and isinstance(request.json, dict):
                token = request.json.get("csrf_token")

            if not token:
                abort(403, "CSRF token missing.")

            session_token = session.get("csrf_token") or request.cookies.get("csrf_token")
            if not session_token or not secrets.compare_digest(session_token, token):
                abort(403, "CSRF token invalid.")

        @app.after_request
        def set_csrf_cookie(response):
            # Set the CSRF token in a cookie so client JS can read it and send it back via headers
            if "csrf_token" in session:
                is_secure = request.is_secure or app.config.get("SESSION_COOKIE_SECURE", False)
                response.set_cookie(
                    "csrf_token",
                    session["csrf_token"],
                    samesite="Lax",
                    secure=is_secure,
                    httponly=False,  # Must be readable by client JS
                )
            return response

    def exempt(self, view_path: str) -> None:
        """Exempt a path from CSRF validation."""
        self.exempt_views.add(view_path)

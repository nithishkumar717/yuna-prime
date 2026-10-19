"""Tests for web security middleware, CSRF, secure headers, and authorization guards."""

from __future__ import annotations

import pytest
import time
from unittest import mock
from flask import Flask, jsonify
from security.middleware import CSRFProtection, SecurityHeaders, AuthHardening
from security.authorization.guards import require_login, require_guild_permission


@pytest.fixture
def secure_app():
    """Create a configured Flask application for testing web security."""
    app = Flask("test_secure_app")
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-12345"
    
    # Initialize middlewares
    AuthHardening(app)
    CSRFProtection(app)
    SecurityHeaders(app)
    
    @app.route("/api/test-get", methods=["GET"])
    def get_route():
        return jsonify({"status": "ok"})

    @app.route("/api/test-post", methods=["POST"])
    def post_route():
        return jsonify({"status": "saved"})

    @app.route("/api/test-login-protected")
    @require_login
    def login_protected():
        return jsonify({"status": "logged-in"})

    @app.route("/api/guilds/<int:guild_id>/protected")
    @require_guild_permission("guild_id")
    def guild_protected(guild_id):
        return jsonify({"guild_id": guild_id})

    return app


@pytest.fixture
def client(secure_app):
    return secure_app.test_client()


def test_security_headers(client):
    """Verify standard security headers are injected into HTTP responses."""
    response = client.get("/api/test-get")
    assert response.status_code == 200
    
    # Check key security headers
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers


def test_csrf_cookie_generation(client):
    """Verify a CSRF token cookie is set on response."""
    response = client.get("/api/test-get")
    assert response.status_code == 200
    
    cookies = response.headers.getlist("Set-Cookie")
    csrf_cookie = next((c for c in cookies if "csrf_token=" in c), None)
    assert csrf_cookie is not None
    assert "SameSite=Lax" in csrf_cookie


def test_csrf_validation_blocks_unsafe_methods(client):
    """Verify CSRF validation blocks unsafe requests without token."""
    response = client.post("/api/test-post", json={"data": "test"})
    assert response.status_code == 403
    assert b"CSRF token missing" in response.data


def test_csrf_validation_allows_safe_methods(client):
    """Verify CSRF validation permits GET requests without token validation."""
    response = client.get("/api/test-get")
    assert response.status_code == 200


def test_csrf_validation_succeeds_with_valid_token(client):
    """Verify CSRF token validation succeeds when a valid token is supplied."""
    # Establish session and cookie by making a GET request
    client.get("/api/test-get")
    
    with client.session_transaction() as sess:
        csrf_token = sess.get("csrf_token")
        
    assert csrf_token is not None
    
    # Perform POST request providing the token in header
    response = client.post(
        "/api/test-post",
        headers={"X-CSRF-Token": csrf_token},
        json={"data": "test"}
    )
    assert response.status_code == 200
    assert response.json == {"status": "saved"}


def test_csrf_validation_fails_with_invalid_token(client):
    """Verify CSRF token validation fails when an invalid token is supplied."""
    client.get("/api/test-get")
    
    response = client.post(
        "/api/test-post",
        headers={"X-CSRF-Token": "invalid-token-value"},
        json={"data": "test"}
    )
    assert response.status_code == 403
    assert b"CSRF token invalid" in response.data


def test_require_login_guard_blocks(client):
    """Verify @require_login blocks requests when user is not in session."""
    response = client.get("/api/test-login-protected")
    assert response.status_code == 401
    assert response.json == {"error": "Not logged in"}


def test_require_login_guard_allows(client):
    """Verify @require_login permits requests when user is in session."""
    with client.session_transaction() as sess:
        sess["user"] = {"id": "12345", "username": "test_user"}
        
    response = client.get("/api/test-login-protected")
    assert response.status_code == 200
    assert response.json == {"status": "logged-in"}


@mock.patch("main.get_current_user_guilds")
@mock.patch("main.has_manage_guild_permission")
@mock.patch("main.bot_instance")
def test_require_guild_permission_guard_allows(mock_bot, mock_has_perm, mock_get_guilds, client):
    """Verify @require_guild_permission allows access if user has Manage Server and bot is ready."""
    with client.session_transaction() as sess:
        sess["user"] = {"id": "12345", "username": "test_user"}

    mock_get_guilds.return_value = [{"id": "999", "permissions": "32"}]
    mock_has_perm.return_value = True
    
    # Mock bot
    mock_bot.is_ready.return_value = True
    mock_guild = mock.MagicMock()
    mock_guild.id = 999
    mock_bot.get_guild.return_value = mock_guild
    
    response = client.get("/api/guilds/999/protected")
    assert response.status_code == 200
    assert response.json == {"guild_id": 999}


@mock.patch("main.get_current_user_guilds")
@mock.patch("main.has_manage_guild_permission")
def test_require_guild_permission_guard_blocks_no_perm(mock_has_perm, mock_get_guilds, client):
    """Verify @require_guild_permission blocks access if user lacks Manage Server."""
    with client.session_transaction() as sess:
        sess["user"] = {"id": "12345", "username": "test_user"}

    mock_get_guilds.return_value = [{"id": "999", "permissions": "0"}]
    mock_has_perm.return_value = False
    
    response = client.get("/api/guilds/999/protected")
    assert response.status_code == 403
    assert response.json == {"error": "No manage server permission for this guild"}


def test_auth_hardening_token_refresh():
    """Verify token refresh logic executes on expires_at threshold."""
    auth = AuthHardening(client_id="123", client_secret="456")
    
    # Test valid token (not expired)
    with mock.patch("security.middleware.auth.session", {"discord_token_data": {"access_token": "token1", "expires_at": time.time() + 3600}}):
        assert auth.get_valid_token() == "token1"

    # Test expired token refresh invocation
    with mock.patch("security.middleware.auth.session", {"discord_token_data": {"access_token": "token1", "refresh_token": "refresh1", "expires_at": time.time() - 10}}):
        with mock.patch.object(auth, "refresh_discord_token") as mock_refresh:
            mock_refresh.return_value = {"access_token": "token2", "expires_at": time.time() + 3600}
            assert auth.get_valid_token() == "token2"
            mock_refresh.assert_called_once_with("refresh1")

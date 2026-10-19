"""Security headers middleware for Flask."""

from __future__ import annotations

import os
from typing import Optional
from flask import Flask


class SecurityHeaders:
    """Injects standard web security headers and dynamic scripts into all responses."""

    def __init__(self, app: Optional[Flask] = None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the security headers middleware on the Flask app."""
        _security_js_injected = False
        _security_js_path = os.path.join(app.root_path, 'shared', 'security.js')
        if os.path.isfile(_security_js_path):
            _security_js_injected = True
        
        @app.after_request
        def apply_headers(response):
            # Prevent clickjacking
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            
            # Prevent MIME sniffing
            response.headers["X-Content-Type-Options"] = "nosniff"
            
            # Cross-Site Scripting protection
            response.headers["X-XSS-Protection"] = "1; mode=block"
            
            # Referrer Policy
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            # Content Security Policy (CSP)
            csp_rules = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com",
                "img-src 'self' data: https://cdn.discordapp.com https://discord.com",
                "connect-src 'self' https://discord.com",
                "frame-ancestors 'none'",
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_rules)
            
            # Strict Transport Security (HSTS)
            if app.config.get("SESSION_COOKIE_SECURE", False):
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                
            # Inject security.js client script automatically into HTML responses if file exists
            if _security_js_injected and response.content_type and "text/html" in response.content_type:
                try:
                    html_data = response.get_data(as_text=True)
                    tag = '<script src="/shared/security.js"></script>'
                    close_head = html_data.find("</head>")
                    if close_head != -1:
                        html_data = html_data[:close_head] + tag + html_data[close_head:]
                        response.set_data(html_data)
                except Exception:
                    pass

            return response

# backend/csrf_protection.py
"""
CSRF Protection configuration for the Aureon API.

Uses fastapi-csrf-protect to prevent Cross-Site Request Forgery attacks.
"""
from fastapi_csrf_protect import CsrfProtect
from pydantic import BaseModel
from .config import settings


class CsrfSettings(BaseModel):
    """CSRF protection configuration."""
    secret_key: str = settings.secret_key
    cookie_samesite: str = "lax"
    cookie_secure: bool = settings.environment == "production"
    cookie_httponly: bool = False  # Must be False for JS to read token
    token_location: str = "header"
    header_name: str = "X-CSRF-Token"
    header_type: str = None  # No prefix required


@CsrfProtect.load_config
def get_csrf_config():
    """Load CSRF configuration."""
    return CsrfSettings()

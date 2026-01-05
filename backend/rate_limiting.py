# backend/rate_limiting.py
"""
Rate limiting configuration for the Aureon API.

Uses slowapi to protect expensive endpoints from abuse.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from .constants import (
    RATE_LIMIT_UPLOAD,
    RATE_LIMIT_SETTLEMENT,
    RATE_LIMIT_AI_RESOLVE,
)

# Create limiter instance - key_func extracts client identifier
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.
    
    Returns a JSON response with 429 status code and retry information.
    """
    return JSONResponse(
        status_code=429,
        content={
            "status": "error",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many requests. Please try again in {exc.detail}.",
            "retry_after": str(exc.detail),
        }
    )


# Rate limit strings for decorators
UPLOAD_LIMIT = f"{RATE_LIMIT_UPLOAD}/minute"
SETTLEMENT_LIMIT = f"{RATE_LIMIT_SETTLEMENT}/minute"
AI_RESOLVE_LIMIT = f"{RATE_LIMIT_AI_RESOLVE}/minute"

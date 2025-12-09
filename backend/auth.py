# backend/auth.py
"""
Authentication module with environment-aware JWT validation.
- Development: Allows dev token for local testing
- Production: Requires valid Clerk JWT token
"""
import os
import logging
from typing import Optional
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
CLERK_PEM_PUBLIC_KEY = os.getenv("CLERK_PEM_PUBLIC_KEY", "")
DEV_TENANT_ID = "dev_tenant_01"

# Security scheme
security = HTTPBearer(auto_error=False)


class AuthenticationError(HTTPException):
    """Custom authentication error with detailed messaging."""
    def __init__(self, detail: str, status_code: int = 401):
        super().__init__(status_code=status_code, detail=detail)


def _validate_clerk_token(token: str) -> dict:
    """
    Validate Clerk JWT token and extract claims.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        AuthenticationError: If token is invalid
    """
    if not CLERK_PEM_PUBLIC_KEY:
        logger.error("CLERK_PEM_PUBLIC_KEY not configured")
        raise AuthenticationError("Authentication not configured")
    
    try:
        # Decode and verify the JWT
        payload = jwt.decode(
            token,
            CLERK_PEM_PUBLIC_KEY,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat", "sub"]
            }
        )
        
        # Check expiration explicitly
        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            raise AuthenticationError("Token has expired")
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise AuthenticationError(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise AuthenticationError("Authentication failed")


def _extract_tenant_id(payload: dict) -> str:
    """
    Extract tenant ID from JWT payload.
    
    Clerk tokens include user ID in 'sub' claim.
    We use this as the tenant identifier.
    """
    # Primary: Use Clerk's subject (user ID)
    tenant_id = payload.get("sub")
    
    # Fallback: Check for custom claim
    if not tenant_id:
        tenant_id = payload.get("tenant_id") or payload.get("org_id")
    
    if not tenant_id:
        raise AuthenticationError("No tenant identifier in token")
    
    return tenant_id


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Get the current authenticated user's tenant ID.
    
    In development mode, allows requests without authentication
    for easier local testing.
    
    In production mode, requires valid Clerk JWT token.
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials
        
    Returns:
        Tenant ID string
        
    Raises:
        HTTPException: If authentication fails in production
    """
    # Development mode: Allow unauthenticated access
    if ENVIRONMENT == "development":
        if credentials is None or not credentials.credentials:
            logger.debug("Dev mode: Using default tenant")
            return DEV_TENANT_ID
        
        # If token is provided in dev mode, still try to validate it
        # but fall back to dev tenant on failure
        if credentials.credentials == "dev-token":
            return DEV_TENANT_ID
        
        try:
            payload = _validate_clerk_token(credentials.credentials)
            return _extract_tenant_id(payload)
        except AuthenticationError:
            logger.debug("Dev mode: Token validation failed, using default tenant")
            return DEV_TENANT_ID
    
    # Production mode: Require valid authentication
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication required")
    
    # Validate the token
    payload = _validate_clerk_token(credentials.credentials)
    tenant_id = _extract_tenant_id(payload)
    
    # Add user info to request state for logging
    request.state.user_id = payload.get("sub")
    request.state.tenant_id = tenant_id
    
    logger.debug(f"Authenticated user: {tenant_id}")
    return tenant_id


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work differently for authenticated users.
    """
    if credentials is None or not credentials.credentials:
        return None
    
    try:
        if ENVIRONMENT == "development" and credentials.credentials == "dev-token":
            return DEV_TENANT_ID
        
        payload = _validate_clerk_token(credentials.credentials)
        return _extract_tenant_id(payload)
    except AuthenticationError:
        return None


def require_admin(user_id: str = Depends(get_current_user)) -> str:
    """
    Dependency that requires admin privileges.
    Extend this to check against an admin list or role.
    """
    # TODO: Implement proper admin role checking
    admin_users = os.getenv("ADMIN_USERS", "").split(",")
    
    if user_id not in admin_users and ENVIRONMENT == "production":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return user_id
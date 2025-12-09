# backend/middleware.py
"""
Production middleware for request tracking, timing, and security.
"""
import time
import uuid
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique request ID to each request for tracing.
    The ID is available in:
    - request.state.request_id
    - Response header X-Request-ID
    """
    
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get existing request ID from header or generate new one
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        # Store in request state for use in handlers
        request.state.request_id = request_id
        
        # Call the actual endpoint
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers[self.header_name] = request_id
        
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Tracks request processing time.
    Adds X-Response-Time header with milliseconds.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        # Calculate processing time
        process_time = (time.perf_counter() - start_time) * 1000
        response.headers["X-Response-Time"] = f"{process_time:.2f}ms"
        
        # Log slow requests
        if process_time > 1000:  # > 1 second
            logger.warning(
                f"Slow request: {request.method} {request.url.path} took {process_time:.2f}ms"
            )
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured logging for all requests.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get request details
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log request
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            }
        )
        
        try:
            response = await call_next(request)
            
            # Log response
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "response_time": response.headers.get("X-Response-Time", "unknown"),
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                },
                exc_info=True
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Remove server header if present
        if "server" in response.headers:
            del response.headers["server"]
        
        return response

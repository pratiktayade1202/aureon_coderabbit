# backend/main.py
"""
Main application entry point.
Production-ready FastAPI application with proper middleware stack.
"""
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from .database import engine, Base
from .logging_config import setup_logging
from .config import settings
from .middleware import (
    RequestIDMiddleware,
    TimingMiddleware,
    SecurityHeadersMiddleware,
)
from .ingestion_api import router as ingestion_router
from .recon_api import router as recon_router
from .rules_api import router as rules_router
from .learning_api import router as learning_router
from .health import router as health_router
from .seed_rules import ensure_rule_definitions_exist

# Initialize logging
logger = setup_logging(settings.environment)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info(f"🚀 {settings.app_name} v{settings.app_version} starting up...")
    logger.info(f"   Environment: {settings.environment}")
    logger.info(f"   Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'}")
    
    # Initialize database tables
    logger.info("🛠️ Initializing Enterprise Database Schema...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        raise
    
    # Seed rule definitions
    logger.info("🌱 Seeding rule definitions...")
    try:
        ensure_rule_definitions_exist()
    except Exception as e:
        logger.error(f"❌ Rule seeding failed: {str(e)}")
        # Don't crash the app, but log the error
        # Rules can be seeded later or on next restart
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("👋 Application shutting down...")


# Create FastAPI app with production settings
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-ready financial reconciliation platform",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
    lifespan=lifespan,
)

# --- MIDDLEWARE STACK ---
# Order matters! Last added = first executed

# 1. Security headers (innermost - runs last on request, first on response)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Request timing
app.add_middleware(TimingMiddleware)

# 3. Request ID tracking
app.add_middleware(RequestIDMiddleware)

# 4. GZip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

# 5. CORS middleware - MUST be near top to handle OPTIONS preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)


# --- GLOBAL ERROR HANDLERS ---

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions (404, 403, etc.) with consistent format.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "request_id": request_id,
            "error_code": f"HTTP_{exc.status_code}"
        },
        headers={"X-Request-ID": request_id}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors (Pydantic validation failures).
    Returns structured error with field-level details.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Extract validation errors
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation error: {len(errors)} field(s) failed validation",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": errors
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Request validation failed",
            "request_id": request_id,
            "error_code": "VALIDATION_ERROR",
            "details": errors
        },
        headers={"X-Request-ID": request_id}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for all unhandled errors.
    
    This is the last line of defense - catches any exception that wasn't
    handled by more specific handlers. Logs full stack trace but returns
    sanitized error to client.
    
    CRITICAL: Never returns raw exception messages in production to avoid
    leaking sensitive information (DB connection strings, API keys, etc.)
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log full exception with stack trace server-side
    logger.error(
        f"💥 UNHANDLED EXCEPTION: {exc.__class__.__name__}: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "exception_type": exc.__class__.__name__,
        },
        exc_info=True  # Include full stack trace in logs
    )
    
    # Determine error message based on environment
    if settings.environment == "development":
        # In development, show detailed error for debugging
        detail = f"{exc.__class__.__name__}: {str(exc)}"
        include_traceback = True
    else:
        # In production, show generic message to avoid leaking internals
        detail = "An internal server error occurred. Please contact support if the issue persists."
        include_traceback = False
    
    response_content = {
        "status": "error",
        "message": detail,
        "request_id": request_id,
        "error_code": "INTERNAL_SERVER_ERROR",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Only include exception type in development
    if include_traceback:
        response_content["exception_type"] = exc.__class__.__name__
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_content,
        headers={"X-Request-ID": request_id}
    )

# --- ROUTER REGISTRATION ---
# Create API v1 router
api_v1 = APIRouter(prefix="/api/v1")

# Include routers with proper prefixes
api_v1.include_router(health_router, tags=["health"])
api_v1.include_router(ingestion_router, prefix="/ingestion", tags=["ingestion"])
api_v1.include_router(recon_router, prefix="/recon", tags=["reconciliation"])
api_v1.include_router(rules_router, prefix="", tags=["rules"])
api_v1.include_router(learning_router, prefix="", tags=["learning"])

# Include the main API router
app.include_router(api_v1)


# --- BASIC ROUTES ---
@app.get("/", tags=["root"])
def root():
    """Root endpoint with API information."""
    return {
        "system": settings.app_name,
        "status": "OPERATIONAL",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "endpoints": {
            "health": "/api/v1/health",
            "upload": "/api/v1/ingestion/upload",
            "reconciliation": "/api/v1/recon/run",
            "trades": "/api/v1/recon/trades",
            "rules": "/api/v1/rules/list",
            "docs": "/docs" if settings.environment != "production" else None,
        }
    }


@app.get("/health", tags=["health"])
def root_health_check():
    """Quick health check at root level."""
    return {
        "status": "healthy",
        "service": "aureon-backend",
        "version": settings.app_version,
        "environment": settings.environment
    }


# For development
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        workers=settings.workers if settings.environment == "production" else 1,
        log_config=None,  # Use our custom logging
        access_log=False,  # We handle logging ourselves
    )
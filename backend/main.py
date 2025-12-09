# backend/main.py
"""
Main application entry point.
Production-ready FastAPI application with proper middleware stack.
"""
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
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


# --- GLOBAL ERROR HANDLER ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    Ensures consistent error response format.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True
    )
    
    # Don't leak internal details in production
    detail = str(exc) if settings.environment == "development" else "Internal server error"
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": detail,
            "request_id": request_id,
        },
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
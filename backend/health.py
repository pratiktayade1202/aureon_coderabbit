# backend/health.py
"""
Health check endpoints.
"""
from fastapi import APIRouter
from .config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "aureon-backend",
        "version": settings.app_version,
        "environment": settings.environment
    }

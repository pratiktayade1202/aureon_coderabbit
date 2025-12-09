# backend/config.py
"""
Application configuration.
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv(override=True)  # Override env vars with .env file values

class Settings:
    """Application settings."""
    
    def __init__(self):
        # Application
        self.app_name = os.getenv("APP_NAME", "Aureon Reconciliation")
        self.app_version = os.getenv("APP_VERSION", "2.0.0-dev")
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Database
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://aureon:aureon123@localhost:5432/custody_ai"
        )
        
        # CORS
        cors_origins_str = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
        )
        origins = [origin.strip() for origin in cors_origins_str.split(",")]
        # In development, be permissive to avoid CORS friction
        if self.environment == "development":
            self.cors_origins = ["*"]
        else:
            self.cors_origins = origins
        
        # Workers
        self.workers = int(os.getenv("WORKERS", "1"))

# Create global settings instance
settings = Settings()

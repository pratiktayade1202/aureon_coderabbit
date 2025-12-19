# backend/config.py
"""
Production-grade application configuration with fail-fast validation.
Uses pydantic-settings for environment variable validation and type safety.
"""
import sys
import logging
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file before initializing settings
load_dotenv(override=True)

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings with fail-fast validation.
    
    Required fields will cause the application to exit on startup
    if not provided in the environment.
    """
    
    # === Application Settings ===
    app_name: str = Field(default="Aureon Reconciliation", alias="APP_NAME")
    app_version: str = Field(default="2.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    
    # === Database Configuration (REQUIRED) ===
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # === Redis Configuration (OPTIONAL) ===
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    
    # === AI Services - API Keys ===
    # Gemini is REQUIRED (Primary)
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    
    # OpenAI is OPTIONAL (Fallback only)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    
    # === AI Model Configuration (with defaults) ===
    gemini_model: str = Field(default="gemini-2.0-flash-exp", alias="GEMINI_MODEL")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    
    # === CORS Configuration ===
    cors_origins_str: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        alias="CORS_ORIGINS"
    )
    
    # === Workers Configuration ===
    workers: int = Field(default=1, alias="WORKERS")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def cors_origins(self) -> List[str]:
        """
        Parse CORS origins from comma-separated string.
        In development, allow all origins for easier testing.
        """
        if self.environment == "development":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins_str.split(",")]
    
    @field_validator("gemini_api_key")
    @classmethod
    def validate_gemini_key(cls, v: str) -> str:
        """Validate Gemini key is present."""
        if not v or len(v) < 10:
            raise ValueError("GEMINI_API_KEY is required.")
        return v
        
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v or not v.startswith(("postgresql://", "postgres://")):
            raise ValueError(
                "DATABASE_URL must be a valid PostgreSQL connection string "
                "(e.g., postgresql://user:password@host:port/database)"
            )
        return v
    
    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate Redis URL format (if provided)."""
        if v is not None and not v.startswith("redis://"):
            raise ValueError(
                "REDIS_URL must be a valid Redis connection string "
                "(e.g., redis://host:port/db) or None"
            )
        return v


def _initialize_settings() -> Settings:
    """
    Initialize settings with fail-fast behavior.
    """
    try:
        settings = Settings()
        logger.info(f"✓ Configuration loaded successfully for environment: {settings.environment}")
        logger.info(f"✓ Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")
        logger.info(f"✓ Gemini Model: {settings.gemini_model} (PRIMARY)")
        
        if settings.openai_api_key:
            logger.info(f"✓ OpenAI Model: {settings.openai_model} (FALLBACK ENABLED)")
        else:
            logger.info("ℹ OpenAI: Disabled (No API Key provided)")
        
        if settings.redis_url:
            logger.info(f"✓ Redis: Configured")
        else:
            logger.info("ℹ Redis: Disabled (No REDIS_URL provided)")
            
        return settings
    except Exception as e:
        logger.critical("=" * 80)
        logger.critical("FATAL: Configuration validation failed")
        logger.critical("=" * 80)
        logger.critical(str(e))
        logger.critical("")
        logger.critical("Required environment variables:")
        logger.critical("  - DATABASE_URL")
        logger.critical("  - GEMINI_API_KEY")
        logger.critical("")
        logger.critical("Optional environment variables:")
        logger.critical("  - REDIS_URL (for caching, optional)")
        logger.critical("=" * 80)
        sys.exit(1)


# Create global settings instance with fail-fast initialization
settings = _initialize_settings()


# Export for convenience
__all__ = ["settings", "Settings"]

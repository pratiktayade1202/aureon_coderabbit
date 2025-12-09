# backend/config.py
"""
Production-grade application configuration with fail-fast validation.
Uses pydantic-settings for environment variable validation and type safety.
"""
import sys
import logging
from typing import List
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
    
    # === Redis Configuration (REQUIRED) ===
    redis_url: str = Field(..., alias="REDIS_URL")
    
    # === AI Services - API Keys (REQUIRED) ===
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    
    # === AI Model Configuration (with defaults) ===
    gemini_model: str = Field(default="gemini-2.5-pro", alias="GEMINI_MODEL")
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
    
    @field_validator("gemini_api_key", "openai_api_key")
    @classmethod
    def validate_api_keys(cls, v: str) -> str:
        """Validate that API keys are not empty and have reasonable length."""
        if not v or len(v) < 10:
            raise ValueError(
                "API key is required and must be a valid key. "
                "Please set GEMINI_API_KEY and OPENAI_API_KEY in your .env file."
            )
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
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v or not v.startswith("redis://"):
            raise ValueError(
                "REDIS_URL must be a valid Redis connection string "
                "(e.g., redis://host:port/db)"
            )
        return v


def _initialize_settings() -> Settings:
    """
    Initialize settings with fail-fast behavior.
    
    If required environment variables are missing or invalid,
    log a clear error and exit the process immediately.
    
    Returns:
        Settings: Validated settings instance
        
    Exits:
        Calls sys.exit(1) if validation fails
    """
    try:
        settings = Settings()
        logger.info(f"✓ Configuration loaded successfully for environment: {settings.environment}")
        logger.info(f"✓ Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")
        logger.info(f"✓ Redis: {settings.redis_url.split('@')[-1] if '@' in settings.redis_url else 'configured'}")
        logger.info(f"✓ Gemini Model: {settings.gemini_model}")
        logger.info(f"✓ OpenAI Model: {settings.openai_model}")
        return settings
    except Exception as e:
        logger.critical("=" * 80)
        logger.critical("FATAL: Configuration validation failed")
        logger.critical("=" * 80)
        logger.critical(str(e))
        logger.critical("")
        logger.critical("Required environment variables:")
        logger.critical("  - DATABASE_URL: PostgreSQL connection string")
        logger.critical("  - REDIS_URL: Redis connection string")
        logger.critical("  - GEMINI_API_KEY: Google AI API key")
        logger.critical("  - OPENAI_API_KEY: OpenAI API key")
        logger.critical("")
        logger.critical("Please ensure all required variables are set in your .env file")
        logger.critical("=" * 80)
        sys.exit(1)


# Create global settings instance with fail-fast initialization
settings = _initialize_settings()


# Export for convenience
__all__ = ["settings", "Settings"]

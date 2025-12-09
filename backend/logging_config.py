# backend/logging_config.py
"""
Production-grade logging configuration.

Features:
- Structured logging with contextual information
- Different log levels for development vs production
- Proper formatting for Docker/container environments
- No logging to files (use Docker log aggregation instead)
"""
import logging
import sys
from typing import Optional


def setup_logging(environment: str = "development") -> logging.Logger:
    """
    Setup production-grade logging configuration.
    
    Development:
    - DEBUG level for detailed troubleshooting
    - Colorized console output (if terminal supports it)
    - More verbose format with module names
    
    Production:
    - INFO level for operational visibility
    - Structured JSON-like format for log aggregation
    - Optimized for Docker/container logging
    
    Args:
        environment: Environment name (development, production, etc.)
    
    Returns:
        Configured logger instance
    """
    is_development = environment.lower() == "development"
    
    # Set log level based on environment
    log_level = logging.DEBUG if is_development else logging.INFO
    
    # Choose format based on environment
    if is_development:
        # Development: Human-readable format with colors
        log_format = (
            '%(asctime)s | %(levelname)-8s | %(name)-25s | '
            '%(funcName)-20s | %(message)s'
        )
    else:
        # Production: Structured format for log aggregation
        log_format = (
            '%(asctime)s | %(levelname)-8s | %(name)s | '
            'pid=%(process)d | %(message)s'
        )
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Override any existing configuration
    )
    
    # Set specific log levels for noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    # Suppress SQLAlchemy query logging (very verbose)
    # Use WARNING to only see errors, not every single query
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    
    # Create application logger
    logger = logging.getLogger("aureon")
    logger.setLevel(log_level)
    
    # Log startup message
    logger.info("=" * 80)
    logger.info(f"📋 Logging initialized for {environment.upper()} environment")
    logger.info(f"📋 Log level: {logging.getLevelName(log_level)}")
    logger.info("=" * 80)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name or "aureon")

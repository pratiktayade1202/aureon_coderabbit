# backend/logging_config.py
"""
Logging configuration for the application.
"""
import logging
import sys

def setup_logging(environment: str = "development") -> logging.Logger:
    """
    Setup logging configuration.
    
    Args:
        environment: Environment name (development, production, etc.)
    
    Returns:
        Configured logger instance
    """
    log_level = logging.DEBUG if environment == "development" else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for {environment} environment")
    
    return logger

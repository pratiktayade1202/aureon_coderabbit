# backend/utils/accessors.py
"""
Utility functions for accessing data from objects and dictionaries.
"""
from typing import Any, Optional
from datetime import date, datetime
from dateutil import parser

def get_value(obj: Any, key: str, default: Any = None) -> Any:
    """
    Get a value from an object (dict or object with attributes).
    
    Args:
        obj: Object to get value from
        key: Key/attribute name
        default: Default value if not found
    
    Returns:
        Value from object
    """
    if obj is None:
        return default
    
    # Try dict access
    if isinstance(obj, dict):
        return obj.get(key, default)
    
    # Try attribute access
    return getattr(obj, key, default)

def to_date(value: Any, default: Optional[date] = None) -> Optional[date]:
    """
    Convert a value to a date object.
    
    Args:
        value: Value to convert (string, date, datetime, etc.)
        default: Default value if conversion fails
    
    Returns:
        date object or None
    """
    if value is None:
        return default
    
    if isinstance(value, date):
        return value
    
    if isinstance(value, datetime):
        return value.date()
    
    if isinstance(value, str):
        try:
            # Try parsing with dateutil
            parsed = parser.parse(value)
            return parsed.date() if isinstance(parsed, datetime) else parsed
        except (ValueError, TypeError):
            return default
    
    return default

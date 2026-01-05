# backend/utils/financial.py
"""
Financial utility functions for safe decimal handling and calculations.
"""
from decimal import Decimal, InvalidOperation
from typing import Any, Union

def to_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """
    Safely convert a value to Decimal.
    
    Args:
        value: Value to convert (int, float, string, Decimal, etc.)
        default: Default value if conversion fails
    
    Returns:
        Decimal value
    """
    if value is None:
        return default
    
    if isinstance(value, Decimal):
        return value
    
    try:
        # Handle string values - remove commas and currency symbols
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").replace("₹", "").replace("€", "").strip()
        
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

def get_financial_value(obj: Any, key: str, default: Decimal = Decimal('0')) -> Decimal:
    """
    Get a financial value from an object (dict or object with attributes).
    
    Args:
        obj: Object to get value from
        key: Key/attribute name
        default: Default value if not found
    
    Returns:
        Decimal value
    """
    if obj is None:
        return default
    
    # Try dict access
    if isinstance(obj, dict):
        value = obj.get(key, default)
    else:
        # Try attribute access
        value = getattr(obj, key, default)
    
    return to_decimal(value, default)

def calculate_total_value(quantity: Any, price: Any) -> Decimal:
    """
    Calculate total value from quantity and price.
    
    Args:
        quantity: Quantity (shares, units, etc.)
        price: Price per unit
    
    Returns:
        Total value as Decimal
    """
    qty = to_decimal(quantity)
    prc = to_decimal(price)
    return qty * prc

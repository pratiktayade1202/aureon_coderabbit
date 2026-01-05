# backend/ai_layer/prompt_sanitizer.py
"""
Prompt sanitization utilities to prevent prompt injection attacks.

This module provides functions to sanitize user-controlled data before
it is included in AI prompts, preventing attackers from injecting
malicious instructions.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that could indicate prompt injection attempts
DANGEROUS_PATTERNS = [
    r'ignore\s+(all\s+)?(previous\s+)?(instructions?|prompts?|rules?)',
    r'disregard\s+(all\s+)?(previous\s+)?(instructions?|context)',
    r'forget\s+(all\s+)?(previous\s+)?',
    r'system\s*:\s*',
    r'assistant\s*:\s*',
    r'user\s*:\s*',
    r'human\s*:\s*',
    r'&lt;\|.*?\|&gt;',  # Special tokens
    r'\[\[.*?\]\]',  # Potential special delimiters
    r'&lt;/?prompt&gt;',
    r'&lt;/?instruction&gt;',
    r'RETURN\s+JSON',  # Override output format
    r'OUTPUT\s*:\s*\{',  # Attempt to inject output
]

# Maximum length for sanitized text fields
MAX_DESCRIPTION_LENGTH = 500
MAX_SYMBOL_LENGTH = 50
MAX_REFERENCE_LENGTH = 200


def sanitize_for_prompt(text: Optional[str], max_length: int = MAX_DESCRIPTION_LENGTH) -> str:
    """
    Sanitize user-controlled text before including in AI prompts.
    
    This function:
    1. Removes potential injection phrases
    2. Strips special characters that could be used for attacks
    3. Limits text length to prevent context overflow
    
    Args:
        text: Raw text that may contain user input
        max_length: Maximum allowed length after sanitization
        
    Returns:
        Sanitized text safe for prompt inclusion
    """
    if not text:
        return ""
    
    sanitized = str(text).strip()
    
    # Check for and redact dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.warning(f"Prompt injection pattern detected and sanitized: {pattern}")
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + '...'
    
    return sanitized


def sanitize_trade_data(trade: dict) -> dict:
    """
    Sanitize all user-controlled fields in a trade record.
    
    Args:
        trade: Trade record dictionary
        
    Returns:
        New dictionary with sanitized fields
    """
    return {
        "id": trade.get("id"),
        "date": str(trade.get("date", "")),
        "symbol": sanitize_for_prompt(trade.get("symbol"), MAX_SYMBOL_LENGTH),
        "side": sanitize_for_prompt(trade.get("side"), 10),
        "amount": float(trade.get("amount") or 0),
        "quantity": float(trade.get("quantity") or 0),
        "currency": sanitize_for_prompt(trade.get("currency"), 10) or "INR",
        "description": sanitize_for_prompt(trade.get("description"), MAX_DESCRIPTION_LENGTH),
    }


def sanitize_cash_candidate(candidate: dict) -> dict:
    """
    Sanitize all user-controlled fields in a cash transaction candidate.
    
    Args:
        candidate: Cash transaction dictionary
        
    Returns:
        New dictionary with sanitized fields
    """
    return {
        "id": candidate.get("id"),
        "date": str(candidate.get("date", "")),
        "amount": float(candidate.get("amount") or 0),
        "description": sanitize_for_prompt(
            candidate.get("description"), 
            MAX_DESCRIPTION_LENGTH
        ),
    }


def sanitize_learning_examples(examples: list) -> list:
    """
    Sanitize learning examples (few-shot context).
    
    Args:
        examples: List of learning example dictionaries
        
    Returns:
        List of sanitized examples
    """
    sanitized = []
    for ex in examples[:3]:  # Limit to 3 examples
        sanitized.append({
            "symbol": sanitize_for_prompt(ex.get("symbol"), MAX_SYMBOL_LENGTH),
            "trade_amount": float(ex.get("trade_amount") or 0),
            "cash_id": ex.get("cash_id"),
            "cash_amount": float(ex.get("cash_amount") or 0),
            "note": sanitize_for_prompt(ex.get("note"), 200),
        })
    return sanitized

# backend/ai_schema.py
"""
AI-powered schema mapping using Gemini 2.5 Flash Lite.

This module provides intelligent column mapping for messy financial data files,
enabling Aureon to ingest files with non-standard headers automatically.
"""
import os
import json
import time
import logging
from collections import deque
from datetime import datetime, timezone
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set - AI schema mapping will be disabled")

# Rate limits (defaults: 10 RPM, 150 RPD) – override via env if needed
RPM_LIMIT = int(os.getenv("GEMINI_RPM_LIMIT", "10"))
RPD_LIMIT = int(os.getenv("GEMINI_RPD_LIMIT", "150"))

# In-memory counters
CALL_TIMESTAMPS = deque()
DAY_COUNTER = {"date": None, "count": 0}

# The "Truth" - Our Database Schema (what we expect)
STANDARD_SCHEMA = {
    "date": "Transaction Date (YYYY-MM-DD)",
    "ex_date": "Ex-Date (for Corporate Actions)",
    "record_date": "Record Date",
    "symbol": "Security Name / Ticker / Stock code",
    "quantity": "Number of units/shares held or traded",
    "amount": "Total Net Value / Settlement Amount",
    "price": "Price per unit",
    "market_price": "Current market price per unit",
    "side": "Buy / Sell / DR / CR direction",
    "isin": "ISIN Code (12 character identifier)",
    "description": "Narration / Description text",
    "type": "Corporate Action Type (Dividend/Split)",
    "nav_value": "NAV per unit for mutual funds",
    "fund_name": "Mutual Fund Scheme Name",
    "balance": "Ledger/Account Balance",
    "total_value": "Total portfolio/holding value",
    "avg_cost": "Average cost basis per unit",
    "aum": "Assets Under Management",
    "currency": "Currency code (INR, USD, etc.)",
}

# --- GLOBAL STATE ---
HEADER_CACHE = {}
LAST_CALL_TIME = 0
MIN_CALL_INTERVAL = 2.0  # Baseline spacing to avoid bursts


def get_smart_mapping(headers: list) -> dict:
    """
    Uses Gemini 2.5 Flash Lite for intelligent column mapping.
    
    This is the AI-native approach: we ask Gemini to understand messy
    financial headers and map them to our standard schema.
    
    Features:
    - Caches results to avoid redundant API calls
    - Respects rate limits (2s between calls)
    - Gracefully degrades if API is unavailable
    
    Args:
        headers: List of column headers from the input file
        
    Returns:
        Dict mapping original headers to standard schema keys
    """
    global LAST_CALL_TIME
    
    if not GEMINI_API_KEY:
        logger.debug("Gemini API key not configured, skipping AI mapping")
        return {}
    
    # --- FAST PATH: Check Cache ---
    header_key = tuple(h.lower().strip() for h in headers)
    if header_key in HEADER_CACHE:
        logger.info("⚡ CACHE HIT: Reusing AI mapping")
        return HEADER_CACHE[header_key]
    
    # --- RATE LIMITING ---
    try:
        _respect_rate_limits()
    except RuntimeError as rl_err:
        logger.warning(f"[AI] Skipping Gemini call: {rl_err}")
        return {}
    
    # --- CALL GEMINI 2.5 FLASH LITE ---
    logger.info(f"🧠 Gemini 2.5 Flash Lite analyzing {len(headers)} columns...")
    
    try:
        # Use Gemini 2.5 Pro (flash-exp is deprecated, using stable pro version)
        model = genai.GenerativeModel(
            'gemini-2.5-pro',
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.1,  # Low temperature for consistent mapping
            }
        )
        
        prompt = f"""You are a Data Engineer specializing in financial data.
Your task: Map these messy CSV/Excel headers to our Standard Schema.

INPUT HEADERS: {json.dumps(headers)}

STANDARD SCHEMA (map TO these keys):
{json.dumps(STANDARD_SCHEMA, indent=2)}

RULES:
1. Return ONLY valid JSON: {{"Original_Header": "standard_key"}}
2. Only include high-confidence matches (>80% sure)
3. Map quantity-related columns (qty, units, shares, holding_qty) to "quantity"
4. Map value columns (val_inr, mkt_val, market_value) to "total_value" for holdings
5. Map price columns (mkt_price, unit_price, rate) to "market_price" or "price"
6. "Credit/Debit" columns should NOT be mapped to 'side'
7. If a header doesn't match any standard field, don't include it
8. Common Indian financial data patterns:
   - "scrip" or "security" → "symbol"
   - "nav" → "nav_value"
   - "scheme" → "fund_name"
   - "bal" or "closing_bal" → "balance"

Return the mapping as JSON."""

        response = model.generate_content(prompt)
        _register_call()
        LAST_CALL_TIME = time.time()
        
        # Parse response
        raw_text = response.text.strip()
        
        # Clean markdown code blocks if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        mapping = json.loads(raw_text)
        
        if mapping and isinstance(mapping, dict):
            # Validate mapping - only keep valid target columns
            valid_targets = set(STANDARD_SCHEMA.keys())
            validated_mapping = {
                k: v for k, v in mapping.items() 
                if v in valid_targets
            }
            
            if validated_mapping:
                HEADER_CACHE[header_key] = validated_mapping
                logger.info(f"✅ Gemini mapped {len(validated_mapping)} columns: {validated_mapping}")
                return validated_mapping
            else:
                logger.warning("Gemini returned mapping with no valid targets")
                return {}
        
        logger.warning("Gemini returned empty or invalid mapping")
        return {}
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        LAST_CALL_TIME = time.time()
        return {}
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        LAST_CALL_TIME = time.time()
        return {}


def clear_cache():
    """Clear the header mapping cache."""
    global HEADER_CACHE
    HEADER_CACHE = {}
    logger.info("AI schema mapping cache cleared")


def _respect_rate_limits():
    """Ensure we do not exceed RPM/RPD quotas."""
    global CALL_TIMESTAMPS, DAY_COUNTER

    now = time.time()
    elapsed = now - LAST_CALL_TIME
    if elapsed < MIN_CALL_INTERVAL:
        sleep_time = MIN_CALL_INTERVAL - elapsed
        logger.debug(f"🚦 Rate limiting: waiting {sleep_time:.2f}s")
        time.sleep(sleep_time)

    # Minute-level window
    window_start = now - 60
    while CALL_TIMESTAMPS and CALL_TIMESTAMPS[0] < window_start:
        CALL_TIMESTAMPS.popleft()
    if RPM_LIMIT > 0 and len(CALL_TIMESTAMPS) >= RPM_LIMIT:
        wait_time = 60 - (now - CALL_TIMESTAMPS[0]) + 0.05
        logger.debug(f"🚦 RPM limit hit ({RPM_LIMIT}/min). Sleeping {wait_time:.2f}s")
        time.sleep(max(wait_time, 0))

    # Daily limit (UTC)
    today = datetime.now(timezone.utc).date()
    if DAY_COUNTER["date"] != today:
        DAY_COUNTER["date"] = today
        DAY_COUNTER["count"] = 0
    if RPD_LIMIT > 0 and DAY_COUNTER["count"] >= RPD_LIMIT:
        logger.warning("Gemini daily quota exhausted; skipping AI mapping for today")
        raise RuntimeError("Gemini daily quota exhausted")


def _register_call():
    """Record successful API invocation for rate tracking."""
    now = time.time()
    CALL_TIMESTAMPS.append(now)
    today = datetime.now(timezone.utc).date()
    if DAY_COUNTER["date"] != today:
        DAY_COUNTER["date"] = today
        DAY_COUNTER["count"] = 0
    DAY_COUNTER["count"] += 1
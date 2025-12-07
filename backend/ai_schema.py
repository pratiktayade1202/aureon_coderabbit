# backend/ai_schema.py
import json
import time
from .llm_gateway import LLMGateway

# The "Truth" - Our Database Schema
STANDARD_SCHEMA = {
    "date": "Transaction Date (YYYY-MM-DD)",
    "ex_date": "Ex-Date (for Corporate Actions)",
    "record_date": "Record Date",
    "symbol": "Security Name / Ticker / ISIN",
    "quantity": "Number of units/shares",
    "amount": "Total Net Value / Settlement Amount",
    "price": "Price per unit / NAV",
    "side": "Buy / Sell / DR / CR",
    "isin": "ISIN Code (12 chars)",
    "description": "Narration / Description text",
    "type": "Corporate Action Type (Dividend/Split)"
}

# Global Cache: { ('Header', 'A', 'B'): {'mapped': 'dict'} }
HEADER_CACHE = {}

def get_smart_mapping(headers: list) -> dict:
    """
    Uses OpenAI (gpt-4o-mini) to map messy headers.
    Includes Caching for speed.
    """
    
    # 1. FAST PATH: Check Cache
    # If we have seen these exact headers before, return instantly.
    header_key = tuple(headers)
    if header_key in HEADER_CACHE:
        print("⚡ CACHE HIT: Reusing OpenAI mapping (0s)")
        return HEADER_CACHE[header_key]

    # 2. ASK OPENAI
    print(f"🧠 AI (ChatGPT) Analyzing {len(headers)} columns...")
    
    prompt = f"""
    Map these CSV headers to the Standard Schema.
    
    Incoming Headers: {headers}
    Standard Schema: {json.dumps(STANDARD_SCHEMA)}
    
    Return strictly valid JSON in this format: {{"Incoming_Header": "standard_field_key"}}
    Only map clear matches. Ignore ambiguity.
    """
    
    # Switch to OpenAI Brain (gpt-4o-mini)
    # It is fast and reliable for JSON tasks.
    mapping = LLMGateway.call_openai_brain(
        prompt, 
        system_role="You are a Senior Data Engineer specializing in financial ETL."
    )
    
    # 3. Save to Cache
    if mapping:
        HEADER_CACHE[header_key] = mapping
    
    return mapping
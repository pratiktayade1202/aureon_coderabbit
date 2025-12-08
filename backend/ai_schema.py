# backend/ai_schema.py
import os
import json
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
    "type": "Corporate Action Type (Dividend/Split)",
    "nav_value": "NAV per unit",
    "fund_name": "Mutual Fund Scheme Name",
    "balance": "Ledger Balance"
}

# --- GLOBAL STATE ---
HEADER_CACHE = {}
LAST_CALL_TIME = 0 

def get_smart_mapping(headers: list) -> dict:
    """
    Uses Gemini 2.0 Flash Lite.
    Enforces a 4-second gap between calls to respect Free Tier limits.
    """
    global LAST_CALL_TIME
    
    # 1. FAST PATH: Check Cache
    header_key = tuple(headers)
    if header_key in HEADER_CACHE:
        print("⚡ CACHE HIT: Reusing AI mapping (0s delay)")
        return HEADER_CACHE[header_key]

    # 2. TRAFFIC CONTROL
    elapsed = time.time() - LAST_CALL_TIME
    if elapsed < 4.0:
        sleep_time = 4.0 - elapsed
        print(f"🚦 Throttling: Waiting {sleep_time:.2f}s for API limit...")
        time.sleep(sleep_time)

    # 3. ASK GEMINI
    print(f"🧠 AI (Gemini 2.0 Flash Lite) Analyzing {len(headers)} columns...")
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-lite-preview-02-05')
        
        prompt = f"""
        You are a Data Engineer. Map these messy CSV headers to the Standard Schema keys provided below.
        
        Incoming Headers: {headers}
        Standard Schema: {json.dumps(STANDARD_SCHEMA)}
        
        Rules:
        1. Return ONLY valid JSON. No Markdown.
        2. Format: {{"Incoming_Header": "standard_field_key"}}
        3. Only map high-confidence matches.
        4. "Credit/Debit" columns should NOT be mapped to 'side'.
        """
        
        response = model.generate_content(prompt)
        LAST_CALL_TIME = time.time()
        
        # Clean response
        raw_text = response.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[7:]
        if raw_text.endswith("```"): raw_text = raw_text[:-3]
            
        mapping = json.loads(raw_text)
        
        if mapping:
            HEADER_CACHE[header_key] = mapping
            return mapping
            
    except Exception as e:
        print(f"⚠️ Gemini Mapping Error: {e}")
        LAST_CALL_TIME = time.time() # Reset timer even on fail
        return {}

    return {}
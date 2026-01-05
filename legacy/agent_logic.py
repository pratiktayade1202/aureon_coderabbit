# backend/agent_logic.py
import os
import json
import pandas as pd
from sqlalchemy import text
from .database import engine
from .llm_gateway import LLMGateway

# --- 🛡️ COMPLIANCE SHIELD: DATA MASKING ---
def anonymize_data(df):
    """
    Strips PII (Names, Descriptions) before sending to AI.
    Replaces them with generic tokens.
    """
    df_clean = df.copy()
    
    # 1. Redact Description/Narrations (High risk for Names/PANs)
    if 'description' in df_clean.columns:
        df_clean['description'] = "REDACTED_DESC"
        
    # 2. Mask Symbol if it looks like a person's name (simple heuristic)
    # (In production, we'd use Named Entity Recognition here)
    
    # 3. Select ONLY the columns needed for logic checks
    # The AI needs Dates/Amounts to find errors, but not file paths or internal IDs.
    cols_to_keep = ['date', 'symbol', 'side', 'quantity', 'price', 'amount']
    
    # Filter to only existing columns
    safe_cols = [c for c in cols_to_keep if c in df_clean.columns]
    
    return df_clean[safe_cols]

def run_ai_audit_agent():
    print("🕵️ AI AGENT: Waking up...")
    
    try:
        with engine.connect() as conn:
            # Fetch last 50 trades (newest first)
            query = text("SELECT * FROM broker_trades ORDER BY id DESC LIMIT 50")
            df = pd.read_sql(query, conn)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if df.empty:
        return {"status": "empty", "message": "No trades to audit."}

    # --- APPLY THE SHIELD ---
    secure_df = anonymize_data(df)
    trades_context = secure_df.to_string(index=False)

    # Construct Prompt
    prompt = f"""
    You are a Senior Compliance Officer. Audit this trade log.

    RULES:
    1. WEEKEND CHECK: Flag trades on Saturday/Sunday. (Date format: YYYY-MM-DD)
    2. GHOST TRADE: Flag if Quantity > 0 but Amount is 0/Null.
    3. PRICE SHOCK: Flag if Price is 0 or negative.

    LOG (Sanitized):
    {trades_context}

    OUTPUT JSON:
    {{
        "anomalies": [
            {{ "id": "row_index", "issue": "Error description", "severity": "HIGH" }}
        ]
    }}
    
    """
# --- VERIFICATION: PRINT WHAT WE SEND ---
    print("\n" + "="*40)
    print("🔒 SECURITY AUDIT: PAYLOAD TO AI")
    print("="*40)
    print(trades_context)  # This prints the anonymized table
    print("="*40 + "\n")

    print("🧠 AGENT: Sending SANITIZED data to AI...")
    return LLMGateway.get_json(prompt)
    print("🧠 AGENT: Sending SANITIZED data to AI...")
    return LLMGateway.get_json(prompt)
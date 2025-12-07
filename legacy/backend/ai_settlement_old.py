# backend/ai_settlement.py
import pandas as pd
import json
from sqlalchemy import text
from .database import engine
from .llm_gateway import LLMGateway
from .executor import DBExecutor

def run_deterministic_settlement():
    """PHASE 1: SQL Matcher"""
    print("⚡ PHASE 1: Running SQL Matcher...")
    try:
        with engine.begin() as conn:
            # FIX: Catch NULLs and Empty Strings
            conn.execute(text("""
                UPDATE broker_trades
                SET status = '✅ SETTLED', 
                    bank_ref = bank_txns.description
                FROM bank_txns
                WHERE (broker_trades.status IS NULL OR broker_trades.status = 'UNSETTLED' OR broker_trades.status = '')
                  AND (bank_txns.status IS NULL OR bank_txns.status = 'UNUSED')
                  AND bank_txns.amount = broker_trades.amount
                  AND bank_txns.date = broker_trades.date
            """))
            
            # Also lock the cash
            conn.execute(text("""
                UPDATE bank_txns
                SET status = 'USED'
                WHERE id IN (
                    SELECT b.id 
                    FROM broker_trades bt
                    JOIN bank_txns b ON bt.amount = b.amount AND bt.date = b.date
                    WHERE bt.status = '✅ SETTLED'
                )
            """))
    except Exception as e:
        print(f"⚠️ Phase 1 Error: {e}")
    return _fetch_display_data()

def run_ai_resolution():
    """PHASE 2: AI Agent"""
    print("🧠 PHASE 2: AI Agent resolving edge cases...")
    try:
        with engine.connect() as conn:
            # FIX: Catch NULLs and Empty Strings here too
            trades = pd.read_sql("""
                SELECT * FROM broker_trades 
                WHERE status IS NULL OR status = 'UNSETTLED' OR status = ''
            """, conn)
            
            cash = pd.read_sql("""
                SELECT * FROM bank_txns 
                WHERE status IS NULL OR status = 'UNUSED'
            """, conn)
        
        if trades.empty:
            print("✨ No pending trades found.")
            return _fetch_display_data()

        # Send to AI
        trades_lite = trades[['id', 'date', 'symbol', 'amount']].to_dict(orient='records')
        cash_lite = cash[['id', 'date', 'description', 'amount']].to_dict(orient='records')

        prompt = f"""
        Act as a Settlement Officer. Resolve {len(trades_lite)} exceptions.

        TRADES (Unsettled): {json.dumps(trades_lite)}
        CASH (Available): {json.dumps(cash_lite)}

        RULES:
        1. Match Trade to Cash (Amount diff <= 0.05 OR Date diff <= 3 days).
        2. IF MATCH: status="✅ SETTLED (AI)", reason="Matched T+N", cash_id=MATCHED_CASH_ID
        3. IF NO MATCH: status="⚠️ ESCALATED", reason="Missing Cash", cash_id=null

        OUTPUT JSON:
        {{
            "decisions": [
                {{ "id": 123, "status": "...", "reason": "...", "cash_id": 456 }}
            ]
        }}
        """

        print("...Sending to GPT-4o-mini...")
        response = LLMGateway.call_openai_brain(prompt)
        
        if response and "decisions" in response:
            DBExecutor.apply_settlement_plan(response)
        else:
            print("❌ AI returned invalid structure.")
            
        return _fetch_display_data()

    except Exception as e:
        print(f"❌ Phase 2 Error: {e}")
        return []

def _fetch_display_data():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM broker_trades ORDER BY id ASC LIMIT 100", conn)
    output = []
    for _, row in df.iterrows():
        output.append({
            "id": f"tr_{row['id']}",
            "timestamp": str(row["date"]),
            "security": row["symbol"],
            "bank_ref": row["bank_ref"] or "---",
            "amount": row["amount"],
            "status": row["status"] or "UNSETTLED",
        })
    return output
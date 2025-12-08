# backend/ai_layer/agent.py

from sqlalchemy.orm import Session
from sqlalchemy import text
import json

class AIAgent:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def analyze_single_trade(self, trade_id: int):
        """
        Deterministic Analysis: Finds the best Cash Match using Math, not LLM.
        """
        # 1. Fetch the Trade
        trade = self.db.execute(
            text("SELECT * FROM broker_trades WHERE id = :id AND tenant_id = :tid"),
            {"id": trade_id, "tid": self.tenant_id}
        ).mappings().first()

        if not trade:
            return {"found": False, "message": "Trade not found"}

        # 2. Search for Cash Candidates (Amount match +/- 1%)
        target_amount = abs(float(trade.amount or 0))
        min_amt = target_amount * 0.99
        max_amt = target_amount * 1.01

        candidates = self.db.execute(
            text("""
                SELECT * FROM bank_txns 
                WHERE tenant_id = :tid 
                  AND status = 'UNUSED'
                  AND ABS(amount) BETWEEN :min_a AND :max_a
                ORDER BY date ASC
            """),
            {"tid": self.tenant_id, "min_a": min_amt, "max_a": max_amt}
        ).mappings().all()

        # 3. Best Match Logic (Closest Amount, then Closest Date)
        best_match = None
        confidence = 0.0
        reason = "No matching cash found within 1% tolerance."

        if candidates:
            # Pick the first one for now (or refine by date)
            c = candidates[0] 
            best_match = dict(c)
            # Serialize dates for JSON
            if 'date' in best_match: best_match['date'] = str(best_match['date'])
            if 'value_date' in best_match: best_match['value_date'] = str(best_match['value_date'])
            
            confidence = 0.95 # High confidence because math matched
            reason = f"Found cash entry of {best_match.get('amount')} matching trade amount."

        return {
            "found": True if best_match else False,
            "trade_id": trade_id,
            "best_candidate": best_match,
            "ai_suggestion": {
                "confidence": confidence,
                "action": "MATCH",
                "explanation": reason
            }
        }
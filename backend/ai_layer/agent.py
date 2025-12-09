# backend/ai_layer/agent.py
"""
AI Agent for intelligent trade reconciliation.

Uses a two-phase approach:
1. Deterministic matching: Find cash entries within tolerance
2. LLM reasoning (GPT-4o-mini): Analyze ambiguous cases and provide explanations
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
import json
import logging
from ..llm_gateway import LLMGateway

logger = logging.getLogger(__name__)


class AIAgent:
    def __init__(self, db: Session, tenant_id: str, use_llm: bool = True):
        self.db = db
        self.tenant_id = tenant_id
        self.use_llm = use_llm  # Enable/disable LLM reasoning

    def analyze_single_trade(self, trade_id: int):
        """
        Hybrid Analysis: Math-first matching + LLM reasoning for explanations.
        
        Phase 1: Deterministic search for cash matches (fast, free)
        Phase 2: LLM analysis for confidence scoring and explanation (optional)
        """
        # 1. Fetch the Trade
        trade = self.db.execute(
            text("SELECT * FROM broker_trades WHERE id = :id AND tenant_id = :tid"),
            {"id": trade_id, "tid": self.tenant_id}
        ).mappings().first()

        if not trade:
            return {"found": False, "message": "Trade not found"}

        trade_data = dict(trade)
        
        # 2. Search for Cash Candidates (Amount match +/- 1%)
        # Include both 'UNUSED' status and NULL status (common after fresh ingestion)
        target_amount = abs(float(trade.amount or 0))
        min_amt = target_amount * 0.99
        max_amt = target_amount * 1.01

        candidates = self.db.execute(
            text("""
                SELECT * FROM bank_txns 
                WHERE tenant_id = :tid 
                  AND (status = 'UNUSED' OR status IS NULL)
                  AND ABS(amount) BETWEEN :min_a AND :max_a
                ORDER BY ABS(ABS(amount) - :target) ASC, date ASC
                LIMIT 5
            """),
            {"tid": self.tenant_id, "min_a": min_amt, "max_a": max_amt, "target": target_amount}
        ).mappings().all()

        # 3. Deterministic Match (Phase 1)
        best_match = None
        confidence = 0.0
        reason = "No matching cash found within 1% tolerance."

        if candidates:
            c = candidates[0] 
            best_match = dict(c)
            # Serialize dates for JSON
            if 'date' in best_match: best_match['date'] = str(best_match['date'])
            if 'value_date' in best_match: best_match['value_date'] = str(best_match['value_date'])
            
            # Calculate base confidence from amount match
            amount_diff = abs(float(best_match.get('amount', 0)) - target_amount)
            amount_diff_pct = (amount_diff / target_amount * 100) if target_amount > 0 else 100
            
            # Exact match = 0.99, 1% diff = 0.90
            confidence = max(0.90, 0.99 - (amount_diff_pct / 10))
            reason = f"Found cash entry of {best_match.get('amount')} (diff: {amount_diff_pct:.2f}%)."
            
            # 4. LLM Reasoning (Phase 2) - Optional
            if self.use_llm and len(candidates) > 1:
                llm_analysis = self._get_llm_reasoning(trade_data, candidates[:3])
                if llm_analysis:
                    confidence = llm_analysis.get("confidence", confidence)
                    reason = llm_analysis.get("explanation", reason)
                    logger.info(f"LLM reasoning applied: {reason[:100]}...")

        return {
            "found": True if best_match else False,
            "trade_id": trade_id,
            "best_candidate": best_match,
            "candidates_count": len(candidates),
            "ai_suggestion": {
                "confidence": confidence,
                "action": "MATCH" if confidence > 0.8 else "REVIEW",
                "explanation": reason
            }
        }

    def _get_llm_reasoning(self, trade: dict, candidates: list) -> dict:
        """
        Use GPT-4o-mini to analyze ambiguous matches and provide reasoning.
        """
        try:
            # Serialize trade data
            trade_summary = {
                "id": trade.get("id"),
                "date": str(trade.get("date")),
                "symbol": trade.get("symbol"),
                "side": trade.get("side"),
                "amount": float(trade.get("amount") or 0),
                "quantity": float(trade.get("quantity") or 0),
            }
            
            # Serialize candidates
            candidates_summary = []
            for c in candidates:
                candidates_summary.append({
                    "id": c.get("id"),
                    "date": str(c.get("date")),
                    "amount": float(c.get("amount") or 0),
                    "description": str(c.get("description") or "")[:100],
                })
            
            prompt = f"""You are a financial reconciliation expert. Analyze this trade and its potential cash matches.

TRADE:
{json.dumps(trade_summary, indent=2)}

CASH CANDIDATES:
{json.dumps(candidates_summary, indent=2)}

Determine which cash entry is the best match. Consider:
1. Amount similarity (most important)
2. Date proximity  
3. Description relevance

Return JSON with:
- "best_match_id": ID of the best matching cash entry
- "confidence": Float 0.0-1.0
- "explanation": Brief reason for the match (max 100 chars)
"""
            
            result = LLMGateway.call_openai_brain(
                prompt,
                system_role="You are a financial reconciliation AI. Always respond with valid JSON."
            )
            
            if result and isinstance(result, dict):
                logger.debug(f"LLM analysis result: {result}")
                return result
                
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
        
        return None

    def analyze_all_unmatched(self) -> list:
        """
        Analyze all unmatched trades for the tenant.
        Returns list of analysis results.
        """
        unmatched = self.db.execute(
            text("""
                SELECT id FROM broker_trades 
                WHERE tenant_id = :tid 
                  AND (status = 'UNSETTLED' OR status IS NULL)
                LIMIT 50
            """),
            {"tid": self.tenant_id}
        ).mappings().all()
        
        results = []
        for row in unmatched:
            analysis = self.analyze_single_trade(row["id"])
            results.append(analysis)
        
        return results
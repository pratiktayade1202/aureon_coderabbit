# backend/ai_layer/agent.py
"""
Production-grade AI Agent for intelligent trade reconciliation.

Architecture:
- Phase 1: Deterministic matching (math-based, fast, free)
- Phase 2: AI reasoning via model-agnostic gateway (LLM-powered analysis)

The agent is model-agnostic - it knows nothing about specific LLM vendors.
All AI calls route through llm_gateway.reason_on_discrepancy().
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, desc
import json
import logging
from typing import Dict, Any, List, Optional

# Use the unified gateway interface
from ..llm_gateway import LLMGateway
from ..models import LearningEvent

logger = logging.getLogger(__name__)


class AIAgent:
    """
    Hybrid AI Agent: Deterministic matching + LLM reasoning.
    
    Responsibilities:
    1. Find candidate matches using deterministic rules (amount, date tolerance)
    2. Use AI to analyze ambiguous cases and provide explanations
    3. Generate confidence scores and actionable recommendations
    
    The agent is vendor-agnostic and routes all AI calls through the gateway.
    """
    
    def __init__(self, db: Session, tenant_id: str, use_llm: bool = True):
        """
        Initialize AI Agent.
        
        Args:
            db: Database session
            tenant_id: Tenant identifier for multi-tenancy
            use_llm: Enable/disable LLM reasoning (default: True)
        """
        self.db = db
        self.tenant_id = tenant_id
        self.use_llm = use_llm
        logger.info(f"AIAgent initialized for tenant {tenant_id} (LLM: {use_llm})")

    def analyze_single_trade(self, trade_id: int) -> Dict[str, Any]:
        """
        Hybrid Analysis: Math-first matching + AI reasoning for explanations.
        
        Flow:
        1. Fetch the trade from database
        2. Search for candidate cash matches (deterministic, within 1% tolerance)
        3. Calculate base confidence from amount/date similarity
        4. If ambiguous (multiple candidates), invoke AI reasoning
        5. Return structured analysis with confidence and recommendation
        
        Args:
            trade_id: ID of the trade to analyze
            
        Returns:
            Dict with analysis results:
            {
                "found": bool,
                "trade_id": int,
                "best_candidate": dict or None,
                "candidates_count": int,
                "ai_suggestion": {
                    "confidence": float,
                    "action": "MATCH" | "REVIEW" | "ESCALATE",
                    "explanation": str
                }
            }
        """
        logger.info(f"Analyzing trade {trade_id} for tenant {self.tenant_id}")
        
        # 1. Fetch the Trade
        trade = self.db.execute(
            text("SELECT * FROM broker_trades WHERE id = :id AND tenant_id = :tid"),
            {"id": trade_id, "tid": self.tenant_id}
        ).mappings().first()

        if not trade:
            logger.warning(f"Trade {trade_id} not found")
            return {
                "found": False,
                "trade_id": trade_id,
                "message": "Trade not found",
                "ai_suggestion": {
                    "confidence": 0.0,
                    "action": "ESCALATE",
                    "explanation": "Trade record does not exist"
                }
            }

        trade_data = dict(trade)
        
        # 2. Search for Cash Candidates (Amount match +/- 1%)
        # Include both 'UNUSED' status and NULL status (common after fresh ingestion)
        # NOTE: `trade` is a SQLAlchemy RowMapping; use the dict for access.
        target_amount = abs(float(trade_data.get("amount") or 0))
        if target_amount == 0:
            logger.warning(f"Trade {trade_id} has zero amount, cannot match")
            return {
                "found": False,
                "trade_id": trade_id,
                "best_candidate": None,
                "candidates_count": 0,
                "ai_suggestion": {
                    "confidence": 0.0,
                    "action": "ESCALATE",
                    "explanation": "Trade has zero or null amount"
                }
            }
        
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

        logger.info(f"Found {len(candidates)} candidate cash entries for trade {trade_id}")

        # 3. Deterministic Match (Phase 1)
        best_match = None
        confidence = 0.0
        reason = "No matching cash found within 1% tolerance."
        action = "ESCALATE"

        if candidates:
            c = candidates[0] 
            best_match = dict(c)
            
            # Serialize dates for JSON
            if 'date' in best_match and best_match['date']:
                best_match['date'] = str(best_match['date'])
            if 'value_date' in best_match and best_match['value_date']:
                best_match['value_date'] = str(best_match['value_date'])
            
            # Calculate base confidence from amount match
            cash_amount = abs(float(best_match.get('amount', 0)))
            amount_diff = abs(cash_amount - target_amount)
            amount_diff_pct = (amount_diff / target_amount * 100) if target_amount > 0 else 100
            
            # Improved confidence calculation:
            # - Exact match (< 0.01% diff): 0.95 confidence
            # - Near exact (< 0.1% diff): 0.92 confidence
            # - Close (< 0.5% diff): 0.88 confidence
            # - Acceptable (< 1% diff): 0.85 confidence
            if amount_diff_pct < 0.01:
                confidence = 0.95
                reason = f"Exact amount match: cash {cash_amount} matches trade {target_amount}"
            elif amount_diff_pct < 0.1:
                confidence = 0.92
                reason = f"Near-exact match: cash {cash_amount} vs trade {target_amount} (diff: {amount_diff_pct:.3f}%)"
            elif amount_diff_pct < 0.5:
                confidence = 0.88
                reason = f"Close match: cash {cash_amount} vs trade {target_amount} (diff: {amount_diff_pct:.2f}%)"
            else:
                confidence = max(0.85, 0.92 - (amount_diff_pct * 0.07))
                reason = f"Found cash entry of {cash_amount} (diff: {amount_diff_pct:.2f}% from {target_amount})"
            
            # Determine action based on confidence
            if confidence >= 0.90:
                action = "MATCH"
            elif confidence >= 0.80:
                action = "REVIEW"
            else:
                action = "ESCALATE"
            
            logger.info(f"Deterministic analysis for trade {trade_id}: confidence={confidence:.2f}, diff={amount_diff_pct:.3f}%")
            
            # 4. AI Reasoning (Phase 2) - Invoke when multiple candidates OR ambiguous
            # Lowered threshold: invoke AI when there are multiple candidates or confidence is borderline
            should_invoke_ai = self.use_llm and (len(candidates) > 1 or (0.80 <= confidence <= 0.92))
            
            if should_invoke_ai:
                logger.info(f"Invoking AI reasoning for trade {trade_id} ({len(candidates)} candidates, conf={confidence:.2f})")
                ai_analysis = self._get_ai_reasoning(trade_data, candidates[:3])
                
                if ai_analysis:
                    # AI can boost or reduce confidence based on reasoning
                    ai_confidence = ai_analysis.get("confidence", confidence)
                    ai_reason = ai_analysis.get("explanation", reason)
                    ai_action = ai_analysis.get("action", action)
                    
                    # Only override if AI provides meaningful input
                    if ai_confidence > 0:
                        # Blend deterministic and AI confidence (weight towards AI when it's confident)
                        if ai_confidence > 0.9:
                            confidence = ai_confidence
                        else:
                            confidence = (confidence * 0.4) + (ai_confidence * 0.6)
                        
                        reason = ai_reason
                        action = ai_action
                    
                    # If AI found a better match, update best_match
                    suggested_id = ai_analysis.get("best_match_id")
                    if suggested_id:
                        for cand in candidates:
                            if cand.get("id") == suggested_id:
                                best_match = dict(cand)
                                if 'date' in best_match and best_match['date']:
                                    best_match['date'] = str(best_match['date'])
                                if 'value_date' in best_match and best_match['value_date']:
                                    best_match['value_date'] = str(best_match['value_date'])
                                break
                    
                    logger.info(f"AI reasoning complete: {reason[:100]}... (final confidence: {confidence:.2f})")
        
        # Log AI decision to audit trail
        try:
            from ..models import ReconLog
            audit_log = ReconLog(
                tenant_id=self.tenant_id,
                trade_id=trade_id,
                cash_id=best_match.get("id") if best_match else None,
                reason=f"AI Analysis: {reason[:200]}",
                status_before="ANALYZING",
                status_after=action,
                agent_model="AI_AGENT",
            )
            self.db.add(audit_log)
            self.db.flush()  # Write immediately for audit trail
        except Exception as log_err:
            logger.debug(f"Failed to log AI decision: {log_err}")

        return {
            "found": True if best_match else False,
            "trade_id": trade_id,
            "best_candidate": best_match,
            "candidates_count": len(candidates),
            "ai_suggestion": {
                "confidence": confidence,
                "action": action,
                "explanation": reason
            }
        }

    def _fetch_relevant_learnings(self, trade: dict) -> List[Dict[str, Any]]:
        """
        ACTIVE LEARNING CORE: Retrieve past manual resolutions (few-shot examples).

        Strategy:
        - Pull last 50 HUMAN_MANUAL events for this tenant
        - Prioritize events whose trade_data.symbol matches current trade.symbol
        - Return up to 3 examples formatted for prompt injection
        """
        try:
            symbol = (trade.get("symbol") or "").strip()

            events = (
                self.db.query(LearningEvent)
                .filter(
                    LearningEvent.tenant_id == self.tenant_id,
                    LearningEvent.source == "HUMAN_MANUAL",
                )
                .order_by(desc(LearningEvent.timestamp))
                .limit(50)
                .all()
            )

            relevant: List[LearningEvent] = []

            # 1) Symbol-specific learnings first
            if symbol:
                for e in events:
                    t_data = e.trade_data or {}
                    if (t_data.get("symbol") or "").strip() == symbol:
                        relevant.append(e)
                        if len(relevant) >= 3:
                            break

            # 2) Backfill with recent generic learnings
            if len(relevant) < 3:
                for e in events:
                    if e in relevant:
                        continue
                    relevant.append(e)
                    if len(relevant) >= 3:
                        break

            formatted: List[Dict[str, Any]] = []
            for e in relevant[:3]:
                t_data = e.trade_data or {}
                formatted.append(
                    {
                        "symbol": t_data.get("symbol"),
                        "trade_amount": t_data.get("amount"),
                        "cash_id": t_data.get("cash_id"),
                        "cash_amount": t_data.get("cash_amount"),
                        "note": e.correction_notes,
                    }
                )

            return formatted
        except Exception as e:
            logger.warning(f"Failed to fetch learnings: {e}")
            return []

    def _get_ai_reasoning(self, trade: dict, candidates: list) -> Optional[Dict[str, Any]]:
        """
        Use AI to analyze ambiguous matches and provide reasoning.
        
        This method is MODEL-AGNOSTIC - it does not know about specific LLM vendors.
        All AI calls route through llm_gateway.reason_on_discrepancy().
        
        Args:
            trade: Trade record as dict
            candidates: List of candidate cash transactions
            
        Returns:
            Dict with AI analysis:
            {
                "best_match_id": int,
                "confidence": float,
                "action": "MATCH" | "REVIEW" | "ESCALATE",
                "explanation": str
            }
            
            Returns None if AI call fails.
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
                "currency": trade.get("currency", "INR"),
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

            # === Phase 3: Active Learning (Few-shot context injection) ===
            past_learnings = self._fetch_relevant_learnings(trade)
            learnings_text = ""
            if past_learnings:
                learnings_text = (
                    "PAST HUMAN RESOLUTIONS (USE AS GUIDANCE; DO NOT HALLUCINATE):\n"
                    + json.dumps(past_learnings, indent=2)
                    + "\n"
                )
            
            # Build context for AI reasoning
            context = f"""Analyze this financial reconciliation scenario and determine the best match.

TRADE TO RECONCILE:
{json.dumps(trade_summary, indent=2)}

CANDIDATE CASH ENTRIES:
{json.dumps(candidates_summary, indent=2)}

{learnings_text}

ANALYSIS CRITERIA:
1. Amount similarity (most important - exact match is ideal)
2. Date proximity (consider T+0, T+1, T+2 settlement cycles)
3. Description relevance (look for trade IDs, symbols, references)
4. Currency consistency
5. If a past human resolution is highly similar, prefer that logic (within reason).

REQUIRED OUTPUT (JSON):
{{
    "best_match_id": <ID of best matching cash entry>,
    "confidence": <float between 0.0 and 1.0>,
    "action": "<MATCH|REVIEW|ESCALATE>",
    "explanation": "<brief reason for the match, max 150 chars>"
}}

ACTION DEFINITIONS:
- MATCH: High confidence (>0.9), auto-match recommended
- REVIEW: Medium confidence (0.7-0.9), needs analyst review
- ESCALATE: Low confidence (<0.7), significant discrepancy
"""
            
            # Call the unified reasoning gateway (model-agnostic)
            result_str = LLMGateway.reason_on_discrepancy(context, use_json=True)
            result = json.loads(result_str)
            
            # Validate response structure
            if not all(k in result for k in ["best_match_id", "confidence", "explanation"]):
                logger.warning(f"AI response missing required fields: {result}")
                return None
            
            # Ensure action is set
            if "action" not in result:
                conf = result.get("confidence", 0.0)
                if conf > 0.9:
                    result["action"] = "MATCH"
                elif conf > 0.7:
                    result["action"] = "REVIEW"
                else:
                    result["action"] = "ESCALATE"
            
            logger.debug(f"AI analysis result: {result}")
            return result
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"AI reasoning failed: {e}", exc_info=True)
            return None

    def analyze_all_unmatched(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Analyze all unmatched trades for the tenant.
        
        Args:
            limit: Maximum number of trades to analyze (default 50)
            
        Returns:
            List of analysis results
        """
        logger.info(f"Analyzing all unmatched trades for tenant {self.tenant_id} (limit: {limit})")
        
        unmatched = self.db.execute(
            text("""
                SELECT id FROM broker_trades 
                WHERE tenant_id = :tid 
                  AND (status = 'UNSETTLED' OR status IS NULL)
                ORDER BY date DESC
                LIMIT :limit
            """),
            {"tid": self.tenant_id, "limit": limit}
        ).mappings().all()
        
        logger.info(f"Found {len(unmatched)} unmatched trades")
        
        results = []
        for row in unmatched:
            analysis = self.analyze_single_trade(row["id"])
            results.append(analysis)
        
        return results
    
    def analyze_break(self, break_id: int) -> Dict[str, Any]:
        """
        Analyze a specific reconciliation break and suggest resolution.
        
        Args:
            break_id: ID of the break to analyze
            
        Returns:
            Dict with break analysis and AI suggestions
        """
        logger.info(f"Analyzing break {break_id} for tenant {self.tenant_id}")
        
        # Fetch break details
        break_record = self.db.execute(
            text("""
                SELECT b.*, t.symbol, t.amount as trade_amount, t.date as trade_date
                FROM recon_breaks b
                LEFT JOIN broker_trades t ON b.trade_id = t.id
                WHERE b.id = :bid AND b.tenant_id = :tid
            """),
            {"bid": break_id, "tid": self.tenant_id}
        ).mappings().first()
        
        if not break_record:
            return {
                "found": False,
                "break_id": break_id,
                "message": "Break not found"
            }
        
        # If break has a trade_id, analyze the trade
        if break_record.get("trade_id"):
            return self.analyze_single_trade(break_record["trade_id"])
        
        # Otherwise, provide break-level analysis
        return {
            "found": True,
            "break_id": break_id,
            "break_type": break_record.get("break_type"),
            "severity": break_record.get("severity"),
            "amount_diff": float(break_record.get("amount_diff", 0.0)),
            "ai_suggestion": {
                "confidence": 0.5,
                "action": "REVIEW",
                "explanation": f"Break of type {break_record.get('break_type')} requires manual review"
            }
        }


# === Export Public API ===
__all__ = ["AIAgent"]

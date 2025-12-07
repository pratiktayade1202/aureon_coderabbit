# backend/ai_layer/agent.py

import json
from datetime import timedelta, datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..models import ReconBreak, BrokerTrade, BankTxn, ReconLog, RuleMemory

class AIAgent:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    # ... [Keep analyze_single_trade as is] ...
    def analyze_single_trade(self, trade_id: int):
        """
        Tier-3 Co-Pilot (Single Trade Analysis)

        - Looks at one BrokerTrade
        - Scans unused BankTxn rows within ±15 days
        - Scores candidates by:
            * Amount difference
            * Relative % diff
            * Date distance
            * Symbol presence in description
        - Returns a read-only suggestion payload for the frontend.
        - DOES NOT commit anything to the DB. Human confirms via /manual-resolve.
        """
        # 1. Fetch trade in this tenant
        trade = (
            self.db.query(BrokerTrade)
            .filter(
                BrokerTrade.id == trade_id,
                BrokerTrade.tenant_id == self.tenant_id,
            )
            .first()
        )

        if not trade:
            return {
                "found": False,
                "ai_suggestion": {
                    "confidence": 0.0,
                    "explanation": "Trade not found for this tenant.",
                },
                "best_candidate": None,
                "candidates": [],
            }

        if not trade.date:
            return {
                "found": False,
                "ai_suggestion": {
                    "confidence": 0.0,
                    "explanation": "Trade has no booking date; cannot search cash window.",
                },
                "best_candidate": None,
                "candidates": [],
            }

        # 2. Define search window (±15 days)
        min_date = trade.date - timedelta(days=15)
        max_date = trade.date + timedelta(days=15)

        # 3. Pull candidate cash txns
        candidates = (
            self.db.query(BankTxn)
            .filter(
                BankTxn.tenant_id == self.tenant_id,
                BankTxn.status == "UNUSED",
                BankTxn.date >= min_date,
                BankTxn.date <= max_date,
            )
            .all()
        )

        if not candidates:
            return {
                "found": False,
                "ai_suggestion": {
                    "confidence": 0.0,
                    "explanation": "No UNUSED cash transactions found within ±15 days.",
                },
                "best_candidate": None,
                "candidates": [],
            }

        def score_candidate(tr, cash):
            """
            Pure heuristic, deterministic scoring in [0, 1].
            Higher = better match.
            """
            # Guard against missing data
            if tr.amount is None or cash.amount is None:
                return 0.0, "Missing amount on trade or cash leg"

            t_amt = float(tr.amount)
            c_amt = float(cash.amount)
            diff = abs(t_amt - c_amt)

            # Relative difference
            rel_diff = diff / abs(t_amt) if t_amt != 0 else 1.0

            # Date distance
            if tr.date and cash.date:
                day_diff = abs((cash.date - tr.date).days)
            else:
                day_diff = 999

            confidence = 0.0
            reason_parts = []

            # Amount + date banding
            if diff <= 0.5 and day_diff <= 2:
                confidence = 0.98
                reason_parts.append("Exact amount match (≤0.5) within 2 days")
            elif rel_diff <= 0.01 and day_diff <= 3:
                confidence = 0.93
                reason_parts.append("≤1% amount mismatch within 3 days")
            elif rel_diff <= 0.03 and day_diff <= 5:
                confidence = 0.82
                reason_parts.append("≤3% amount mismatch within 5 days")
            elif rel_diff <= 0.05 and day_diff <= 10:
                confidence = 0.70
                reason_parts.append("≤5% amount mismatch within 10 days")
            else:
                # Weak heuristic, penalize by both rel_diff and day_diff
                # This never becomes "high confidence"
                confidence = max(0.05, 1.0 - (rel_diff * 2.0) - (day_diff / 30.0))
                confidence = min(confidence, 0.6)
                reason_parts.append(
                    f"Weak heuristic match: {rel_diff:.2%} diff, {day_diff} days apart"
                )

            # Symbol mention in description → small boost
            symbol = (tr.symbol or "").upper().strip()
            desc = (cash.description or "").upper()
            if symbol and symbol in desc:
                confidence = min(confidence + 0.05, 0.99)
                reason_parts.append("Symbol present in bank description")

            # BUY/SELL sign sanity (optional, trades stored as signed net)
            # If signs are opposite, keep but don't boost.
            if t_amt > 0 and c_amt < 0:
                reason_parts.append("Opposite sign (BUY vs debit)")
            elif t_amt < 0 and c_amt > 0:
                reason_parts.append("Opposite sign (SELL vs credit)")

            explanation = "; ".join(reason_parts) if reason_parts else "Heuristic scoring"
            return float(max(0.0, min(confidence, 0.99))), explanation

        # 4. Score all candidates
        candidate_payloads = []
        best_candidate = None
        best_conf = 0.0
        best_reason = ""

        for cash in candidates:
            conf, reason = score_candidate(trade, cash)

            candidate_payloads.append(
                {
                    "id": cash.id,
                    "date": str(cash.date) if cash.date else None,
                    "description": cash.description,
                    "amount": float(cash.amount) if cash.amount is not None else None,
                    "score": conf,
                    "explanation": reason,
                }
            )

            if conf > best_conf:
                best_conf = conf
                best_candidate = cash
                best_reason = reason

        # 5. Decision: is this "confident enough" to show as a match?
        # This controls:
        #  - UI "Best Match Found" vs amber warning
        #  - Whether the "Accept & Resolve" button is enabled
        CONFIDENCE_THRESHOLD = 0.70
        found = bool(best_candidate and best_conf >= CONFIDENCE_THRESHOLD)

        if not found:
            # Still return the top candidate info for transparency
            if best_candidate:
                explanation = (
                    f"Top candidate is Txn #{best_candidate.id} "
                    f"but confidence {best_conf:.0%} is below the {CONFIDENCE_THRESHOLD:.0%} threshold."
                )
            else:
                explanation = "No viable candidates scored above noise threshold."

            return {
                "found": False,
                "ai_suggestion": {
                    "confidence": float(best_conf),
                    "explanation": explanation,
                },
                "best_candidate": None,
                "candidates": candidate_payloads,
            }

        # 6. Shape response for BreakDrawer.jsx
        best_payload = {
            "id": best_candidate.id,
            "date": str(best_candidate.date) if best_candidate.date else None,
            "description": best_candidate.description,
            "amount": float(best_candidate.amount)
            if best_candidate.amount is not None
            else None,
        }

        return {
            "found": True,
            "ai_suggestion": {
                "confidence": float(best_conf),
                "explanation": best_reason,
            },
            "best_candidate": best_payload,
            "candidates": candidate_payloads,
        }

    def resolve_breaks(self, dry_run: bool = False):
        # ... [Keep existing logic] ...
        breaks = self.db.query(ReconBreak).filter(
            ReconBreak.tenant_id == self.tenant_id,
            ReconBreak.status == "OPEN"
        ).all()
        
        results = {"processed": 0, "resolved": 0, "details": []}
        
        print(f"🤖 AI AGENT: Analyzing {len(breaks)} breaks...")

        for brk in breaks:
            # 1. Analyze
            trade = self.db.query(BrokerTrade).get(brk.trade_id)
            if not trade: continue
            
            # Simple fuzzy logic for Batch Mode (Faster than full analyze_single_trade)
            # Re-implementing the core logic here for speed in batch
            min_date = trade.date - timedelta(days=15)
            max_date = trade.date + timedelta(days=15)
            
            candidates = self.db.query(BankTxn).filter(
                BankTxn.tenant_id == self.tenant_id,
                BankTxn.status == "UNUSED",
                BankTxn.date >= min_date,
                BankTxn.date <= max_date
            ).all()
            
            if not candidates: continue
            
            best = min(candidates, key=lambda c: abs(c.amount - trade.amount))
            diff = abs(trade.amount - best.amount)
            
            confidence = 0.0
            reason = ""
            
            if diff < 1.0:
                confidence = 0.99
                reason = "Exact Amount Match"
            elif trade.amount > 0 and (diff / trade.amount) < 0.05:
                confidence = 0.85
                reason = "Fuzzy Match (<5% diff)"

            if confidence >= 0.70:
                if not dry_run:
                    self._apply_resolution(trade, best, brk, {"confidence": confidence, "explanation": reason})
                results["resolved"] += 1
                results["details"].append({"id": trade.id, "reason": reason})
            
            results["processed"] += 1
            
        return results

    def _apply_resolution(self, trade, cash, brk, ai_resp):
        """
        Commits the match and WRITES THE AUDIT LOG immediately.
        """
        try:
            # 1. Update Entities
            trade.status = f"✅ SETTLED (AI {int(ai_resp['confidence']*100)}%)"
            trade.bank_ref = f"AI Match: {cash.description[:20]}..."
            trade.recon_id = f"AI-{trade.id}-{cash.id}"
            
            cash.status = "USED"
            cash.trade_ref = trade.id
            
            brk.status = "RESOLVED"
            brk.resolution_note = ai_resp["explanation"]
            
            # 2. Create Log Entry
            log = ReconLog(
                tenant_id=self.tenant_id,
                trade_id=trade.id,
                cash_id=cash.id,
                rule_id="AI_AUTO_BATCH",  # Distinct ID for batch runs
                status_before="BREAK",
                status_after="SETTLED",
                reason=ai_resp["explanation"],
                agent_model="Aureon-Neural-v1",
                timestamp=datetime.utcnow()
            )
            self.db.add(log)
            
            # 3. Commit Transaction
            self.db.commit()
            print(f"📝 Audit Log Written for Trade {trade.id}")
            
        except Exception as e:
            self.db.rollback()
            print(f"❌ Failed to commit resolution: {e}")
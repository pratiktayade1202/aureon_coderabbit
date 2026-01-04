# backend/rule_engine/core/engine.py
"""
Hybrid Rule Engine 2.0 - Deterministic Reconciliation Engine.

CRITICAL CHANGE FROM V1:
- DELETED: _vectorized_match() hash-based matcher
- NEW: Rule-driven matching via CandidateGenerator
- Flow: TIER 0 → TIER 1 → CANDIDATE SCORING → AGGREGATION

AI is FORBIDDEN until Tier 4 (not yet implemented).
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import date

from .candidate_generator import CandidateGenerator, ScoredCandidate
from .config import DEFAULT_THRESHOLDS, DEFAULT_TOLERANCES
from .registry import RuleRegistry
from ..tiers import DataQualityGate, HardInvariantChecker

# Import Domain Registrars for backward compatibility with seed_rules
from ..domains.positions import register_position_rules
from ..domains.trade_cash import register_trade_cash_rules
from ..domains.nav import register_nav_rules
from ..domains.data_quality import register_data_quality_rules

logger = logging.getLogger(__name__)


class ReconciliationEngine:
    """
    Deterministic Rule Engine 2.0.
    
    Flow:
    1. TIER 0: Data Quality gates on all records
    2. For each trade: Generate candidates from cash pool
    3. TIER 1-3: Score candidates (invariants → tolerances → temporal)
    4. AGGREGATION: Pick best candidate, decide MATCH/REVIEW/BREAK
    5. OUTPUT: Full audit trail with rule scores
    
    NO AI. NO FALLBACKS. NO RETRIES.
    If nothing matches → BREAK.
    """
    
    def __init__(self, thresholds=None, tolerances=None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.tolerances = tolerances or DEFAULT_TOLERANCES
        self.candidate_generator = CandidateGenerator(self.thresholds, self.tolerances)
        self.registry = RuleRegistry
        self.is_initialized = False
        logger.info("ReconciliationEngine 2.0 initialized (DETERMINISTIC ONLY)")
    
    def initialize(self):
        """
        Initialize legacy rule registry for backward compatibility.
        This is used by seed_rules.py to populate the database with rule definitions.
        """
        if self.is_initialized:
            return
        
        print("🚀 Aureon Engine: Initializing Rule Domains...")
        register_position_rules()
        register_trade_cash_rules()
        register_nav_rules()
        register_data_quality_rules()
        self.is_initialized = True
        print(f"✅ Engine Ready. {len(self.registry.get_all())} rules loaded.")
    
    def run(self, trades: List[Dict], cash_entries: List[Dict], 
            metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run deterministic reconciliation.
        
        Args:
            trades: List of trade dicts
            cash_entries: List of cash transaction dicts
            metadata: Optional metadata (tenant_id, run_date, etc.)
            
        Returns:
            Report with matches, breaks, and full audit trail
        """
        run_id = (metadata or {}).get("run_id", "unknown")
        
        logger.info(f"=" * 60)
        logger.info(f"[ENGINE] Starting reconciliation run {run_id}")
        logger.info(f"[ENGINE] Trades: {len(trades)}, Cash: {len(cash_entries)}")
        logger.info(f"[ENGINE] Thresholds: auto_match={self.thresholds.auto_match}, review={self.thresholds.review_floor}")
        logger.info(f"=" * 60)
        
        # Results tracking
        matches = []
        reviews = []
        breaks = []
        trade_results = {}
        
        # Track consumed cash to prevent double-matching
        consumed_cash_ids = set()
        
        # ─────────────────────────────────────────────────────────
        # PHASE 1: TIER 0 - Data Quality Gate (ALL Records)
        # ─────────────────────────────────────────────────────────
        valid_trades = []
        valid_cash = []
        
        for trade in trades:
            trade_id = trade.get("id")
            dq_results = DataQualityGate.run_all(trade, "trade")
            dq_passed = all(r.passed for r in dq_results)
            
            if not dq_passed:
                failed_rules = [r for r in dq_results if not r.passed]
                logger.warning(f"[ENGINE] Trade={trade_id} REJECTED at Tier0 (DQ)")
                for r in failed_rules:
                    logger.warning(f"  {r.rule_id}: {r.message}")
                
                breaks.append({
                    "trade_id": trade_id,
                    "rule_id": failed_rules[0].rule_id,
                    "break_type": "DATA_QUALITY",
                    "severity": "CRITICAL",
                    "message": failed_rules[0].message,
                    "details": {"id": trade_id}
                })
            else:
                valid_trades.append(trade)
        
        for cash in cash_entries:
            cash_id = cash.get("id")
            dq_results = DataQualityGate.run_all(cash, "cash")
            dq_passed = all(r.passed for r in dq_results)
            
            if dq_passed:
                valid_cash.append(cash)
            else:
                logger.debug(f"[ENGINE] Cash={cash_id} failed DQ, excluded from pool")
        
        logger.info(f"[ENGINE] After Tier0: {len(valid_trades)} valid trades, {len(valid_cash)} valid cash")
        
        # ─────────────────────────────────────────────────────────
        # PHASE 2: For each trade, generate and score candidates
        # ─────────────────────────────────────────────────────────
        for trade in valid_trades:
            trade_id = trade.get("id")
            
            # Filter out already-consumed cash
            available_cash = [c for c in valid_cash if c.get("id") not in consumed_cash_ids]
            
            # Generate candidates using Tier 1-3 rules
            candidates = self.candidate_generator.generate_candidates(
                trade, 
                available_cash,
                max_candidates=5
            )
            
            # Log full rule trail
            self._log_trade_result(trade_id, candidates)
            
            if not candidates:
                # NO CANDIDATES PASSED INVARIANTS → BREAK
                logger.info(f"[ENGINE] Trade={trade_id} → decision=BREAK (no candidates)")
                breaks.append({
                    "trade_id": trade_id,
                    "rule_id": "NO_MATCH",
                    "break_type": "NO_CANDIDATES",
                    "severity": "MEDIUM",
                    "message": f"No cash entries passed invariant checks",
                    "amount_diff": float(trade.get("amount", 0)),
                    "details": {"id": trade_id}
                })
                trade_results[trade_id] = {"decision": "BREAK", "reason": "no_candidates"}
                continue
            
            # Best candidate
            best = candidates[0]
            
            if best.decision == "MATCH":
                # AUTO MATCH (confidence >= 0.95)
                matches.append({
                    "trade_id": trade_id,
                    "cash_id": best.cash_id,
                    "confidence": best.confidence,
                    "rule_trail": self._extract_rule_trail(best),
                })
                consumed_cash_ids.add(best.cash_id)
                trade_results[trade_id] = {
                    "decision": "MATCH", 
                    "cash_id": best.cash_id,
                    "confidence": best.confidence
                }
                
            elif best.decision == "REVIEW":
                # NEEDS HUMAN REVIEW (0.75 <= confidence < 0.95)
                reviews.append({
                    "trade_id": trade_id,
                    "cash_id": best.cash_id,
                    "confidence": best.confidence,
                    "rule_trail": self._extract_rule_trail(best),
                    "alternatives": len(candidates) - 1,
                })
                # Don't consume cash for REVIEW - human decides
                trade_results[trade_id] = {
                    "decision": "REVIEW",
                    "cash_id": best.cash_id,
                    "confidence": best.confidence
                }
                
            else:
                # BREAK (confidence < 0.75)
                breaks.append({
                    "trade_id": trade_id,
                    "rule_id": "LOW_CONFIDENCE",
                    "break_type": "CONFIDENCE_BELOW_THRESHOLD",
                    "severity": "MEDIUM",
                    "message": f"Best candidate confidence {best.confidence:.3f} below threshold",
                    "amount_diff": best.aggregated_result.amount_diff if best.aggregated_result else 0,
                    "details": {"id": trade_id, "best_cash_id": best.cash_id}
                })
                trade_results[trade_id] = {
                    "decision": "BREAK",
                    "reason": "low_confidence",
                    "confidence": best.confidence
                }
        
        # ─────────────────────────────────────────────────────────
        # PHASE 3: Summary Report
        # ─────────────────────────────────────────────────────────
        report = {
            "status": "success",
            "run_id": run_id,
            "match_count": len(matches),
            "review_count": len(reviews),
            "break_count": len(breaks),
            "matches": matches,
            "reviews": reviews,
            "breaks": breaks,
            "trade_results": trade_results,
            "thresholds": {
                "auto_match": self.thresholds.auto_match,
                "review_floor": self.thresholds.review_floor,
            }
        }
        
        logger.info(f"=" * 60)
        logger.info(f"[ENGINE] Run {run_id} Complete")
        logger.info(f"[ENGINE] MATCH: {len(matches)} | REVIEW: {len(reviews)} | BREAK: {len(breaks)}")
        logger.info(f"=" * 60)
        
        return report
    
    def _log_trade_result(self, trade_id: int, candidates: List[ScoredCandidate]):
        """Log structured rule execution trace for a trade."""
        logger.info(f"")
        logger.info(f"[ENGINE] Trade={trade_id}")
        
        if not candidates:
            logger.info(f"  Candidates=0")
            logger.info(f"  → decision=BREAK (no candidates passed Tier 0-1)")
            return
        
        best = candidates[0]
        logger.info(f"  Candidates={len(candidates)}")
        
        # Group results by tier
        tier_results = {}
        for r in best.rule_results:
            tier = r.tier
            if tier not in tier_results:
                tier_results[tier] = []
            tier_results[tier].append(r)
        
        for tier in sorted(tier_results.keys()):
            tier_name = {
                0: "Tier0", 1: "Tier1", 2: "Tier2", 3: "Tier3"
            }.get(tier, f"Tier{tier}")
            
            tier_passed = all(r.passed for r in tier_results[tier])
            logger.info(f"  {tier_name}={'PASS' if tier_passed else 'FAIL'}")
            
            # Log scoring rules with weight > 0
            for r in tier_results[tier]:
                if r.weight > 0:
                    logger.info(f"    {r.rule_id} score={r.score:.2f} weight={r.weight:.2f} | {r.message}")
        
        logger.info(f"  → confidence={best.confidence:.3f}")
        logger.info(f"  → decision={best.decision}")
    
    def _extract_rule_trail(self, candidate: ScoredCandidate) -> List[Dict]:
        """Extract rule trail for audit logging."""
        trail = []
        for r in candidate.rule_results:
            if r.weight > 0:  # Only include scoring rules
                trail.append({
                    "rule_id": r.rule_id,
                    "tier": r.tier,
                    "score": round(r.score, 3),
                    "weight": r.weight,
                    "passed": r.passed,
                    "message": r.message,
                })
        return trail
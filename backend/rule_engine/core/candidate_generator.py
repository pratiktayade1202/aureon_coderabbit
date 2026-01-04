# backend/rule_engine/core/candidate_generator.py
"""
Hybrid Rule Engine 2.0 - Candidate Generation Engine.

CRITICAL CHANGE FROM v1:
Matching is now RULE-DRIVEN. This module generates candidate pairs
and scores them using the tier hierarchy. It REPLACES the naive
`_vectorized_match()` that ran before rules.

AI is FORBIDDEN in candidate generation (Tiers 0-3).
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from .result import RuleResult, AggregatedResult
from .aggregator import ResultAggregator
from .config import DEFAULT_THRESHOLDS, DEFAULT_TOLERANCES
from ..tiers.tier0_data_quality import DataQualityGate
from ..tiers.tier1_invariants import HardInvariantChecker
from ..tiers.tier2_tolerances import FinancialToleranceScorer
from ..tiers.tier3_temporal import TemporalScorer
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScoredCandidate:
    """A trade-cash pair with its aggregated score."""
    
    trade_id: int
    cash_id: int
    trade: Dict[str, Any]
    cash: Dict[str, Any]
    
    # Scoring
    confidence: float = 0.0
    decision: str = "BREAK"  # "MATCH", "REVIEW", "BREAK"
    
    # Rule breakdown
    rule_results: List[RuleResult] = field(default_factory=list)
    aggregated_result: Optional[AggregatedResult] = None
    
    # Flags
    has_hard_failure: bool = False
    ai_involved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "cash_id": self.cash_id,
            "confidence": round(self.confidence, 4),
            "decision": self.decision,
            "has_hard_failure": self.has_hard_failure,
            "ai_involved": self.ai_involved,
            "rule_count": len(self.rule_results),
        }


class CandidateGenerator:
    """
    Rule-driven candidate generation and scoring.
    
    This replaces the pre-rule `_vectorized_match()` pattern.
    Matching is now an integrated part of rule execution.
    
    Flow:
    1. For each trade, generate candidate cash entries (date window)
    2. Run Tier 0-3 rules on each pair
    3. Score and rank candidates
    4. Return top candidates with full audit trail
    """
    
    def __init__(self, 
                 thresholds=None, 
                 tolerances=None,
                 aggregator=None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.tolerances = tolerances or DEFAULT_TOLERANCES
        self.aggregator = aggregator or ResultAggregator(self.thresholds)
    
    def generate_candidates(self, 
                            trade: Dict[str, Any],
                            cash_entries: List[Dict[str, Any]],
                            max_candidates: int = 5) -> List[ScoredCandidate]:
        """
        Generate and score candidate pairs for a trade.
        
        Args:
            trade: Trade record to match
            cash_entries: List of potential cash matches
            max_candidates: Maximum candidates to return
            
        Returns:
            List of ScoredCandidate, sorted by confidence (descending)
        """
        trade_id = trade.get("id")
        logger.info(f"Generating candidates for trade {trade_id} from {len(cash_entries)} cash entries")
        
        # 1. Validate trade data quality first (Tier 0)
        trade_dq_results = DataQualityGate.run_all(trade, "trade")
        trade_dq_failed = any(not r.passed for r in trade_dq_results)
        
        if trade_dq_failed:
            logger.warning(f"Trade {trade_id} failed data quality checks")
            # Return empty - trade itself is invalid
            return []
        
        candidates: List[ScoredCandidate] = []
        
        # 2. Score each cash entry as a potential match
        for cash in cash_entries:
            cash_id = cash.get("id")
            
            # Skip invalid cash entries
            cash_dq_results = DataQualityGate.run_all(cash, "cash")
            cash_dq_failed = any(not r.passed for r in cash_dq_results)
            
            if cash_dq_failed:
                continue
            
            # 3. Run invariant checks (Tier 1)
            inv_results = HardInvariantChecker.run_all(trade, cash)
            has_hard_fail = HardInvariantChecker.has_hard_failure(inv_results)
            
            if has_hard_fail:
                # Don't add to candidates - invariant violation
                logger.debug(f"Trade {trade_id} / Cash {cash_id}: Hard invariant failure")
                continue
            
            # 4. Run scoring rules (Tier 2-3)
            tolerance_results = FinancialToleranceScorer.run_all(trade, cash, self.tolerances)
            temporal_results = TemporalScorer.run_all(trade, cash, self.tolerances)
            
            # 5. Combine all results
            all_results = (
                trade_dq_results + 
                cash_dq_results + 
                inv_results + 
                tolerance_results + 
                temporal_results
            )
            
            # 6. Aggregate into final score
            aggregated = self.aggregator.aggregate(
                all_results, 
                trade_id=trade_id, 
                cash_id=cash_id
            )
            
            # 7. Create scored candidate
            candidate = ScoredCandidate(
                trade_id=trade_id,
                cash_id=cash_id,
                trade=trade,
                cash=cash,
                confidence=aggregated.confidence,
                decision=aggregated.decision,
                rule_results=all_results,
                aggregated_result=aggregated,
                has_hard_failure=has_hard_fail,
                ai_involved=aggregated.ai_involvement != "NONE"
            )
            
            candidates.append(candidate)
        
        # 8. Sort by confidence (descending)
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        
        # 9. Return top candidates
        top_candidates = candidates[:max_candidates]
        
        top_conf = top_candidates[0].confidence if top_candidates else 0
        logger.info(
            f"Trade {trade_id}: Generated {len(candidates)} candidates, "
            f"top confidence: {top_conf:.3f}"
        )
        
        return top_candidates
    
    def find_best_match(self, 
                        trade: Dict[str, Any],
                        cash_entries: List[Dict[str, Any]]) -> Optional[ScoredCandidate]:
        """
        Find the best matching cash entry for a trade.
        
        Returns:
            Best ScoredCandidate if confidence >= review_floor, else None
        """
        candidates = self.generate_candidates(trade, cash_entries, max_candidates=1)
        
        if not candidates:
            return None
        
        best = candidates[0]
        
        # Only return if above minimum threshold
        if best.confidence >= self.thresholds.review_floor:
            return best
        
        logger.info(f"Trade {trade.get('id')}: Best candidate {best.cash_id} below threshold ({best.confidence:.3f})")
        return None
    
    def batch_match(self,
                    trades: List[Dict[str, Any]],
                    cash_entries: List[Dict[str, Any]]) -> Dict[str, List[ScoredCandidate]]:
        """
        Match multiple trades against cash entries.
        
        Returns:
            Dict mapping trade_id to list of scored candidates
        """
        results = {}
        matched_cash_ids = set()
        
        for trade in trades:
            trade_id = trade.get("id")
            
            # Exclude already-matched cash
            available_cash = [c for c in cash_entries if c.get("id") not in matched_cash_ids]
            
            candidates = self.generate_candidates(trade, available_cash)
            results[trade_id] = candidates
            
            # Mark best match as consumed (if AUTO MATCH)
            if candidates and candidates[0].decision == "MATCH":
                matched_cash_ids.add(candidates[0].cash_id)
        
        return results

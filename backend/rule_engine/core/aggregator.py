# backend/rule_engine/core/aggregator.py
"""
Hybrid Rule Engine 2.0 - Weighted Confidence Aggregator.

Key changes from v1:
- Weighted confidence calculation (not binary count)
- Hard invariant enforcement (Tier 0-1 failures = BREAK, no override)
- AI contribution tracking and capping
- Decision thresholds: 0.95 auto-match, 0.75 review floor
"""

from typing import List, Dict, Any, Optional
from .result import RuleResult, AggregatedResult
from .config import DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
import logging

logger = logging.getLogger(__name__)


class ResultAggregator:
    """
    Aggregates individual RuleResults into a final reconciliation decision.
    
    DESIGN PRINCIPLES (Non-Negotiable):
    1. Hard invariant failures cannot be overridden by AI
    2. AI contribution is capped at 10% globally
    3. Confidence is explained by rule contributions
    4. Every decision is auditable
    """
    
    SEVERITY_WEIGHT = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
        "INFO": 0,
        None: 0
    }

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
    
    def aggregate(self, results: List[RuleResult], 
                  trade_id: Optional[int] = None,
                  cash_id: Optional[int] = None) -> AggregatedResult:
        """
        Aggregate rule results into final decision.
        
        Algorithm:
        1. Check for hard failures (Tier 0-1) - immediate BREAK
        2. Calculate weighted confidence from Tier 2-5 scores
        3. Cap AI contribution at 10%
        4. Determine decision: MATCH (≥0.95), REVIEW (≥0.75), BREAK (<0.75)
        5. Generate explainable contributions
        
        Returns:
            AggregatedResult with confidence, decision, and full breakdown
        """
        
        # 1. Check for hard failures first (Tier 0-1 invariants)
        hard_fails = [r for r in results if r.is_hard_fail and not r.passed]
        if hard_fails:
            logger.info(f"Hard invariant failure detected: {[r.rule_id for r in hard_fails]}")
            return AggregatedResult(
                confidence=0.0,
                decision="BREAK",
                rule_contributions=[self._to_contribution(r) for r in results],
                blocking_rules=hard_fails,
                explanation=f"Hard invariant failed: {hard_fails[0].rule_id} - {hard_fails[0].message}",
                total_ai_contribution=0.0,
                ai_involvement="NONE",
                trade_id=trade_id,
                cash_id=cash_id,
            )
        
        # 2. Calculate weighted confidence from soft rules
        valid_results = [r for r in results if r.score >= 0 and r.tier >= 2]
        
        if not valid_results:
            # No scoring rules ran - likely data quality issue
            return AggregatedResult(
                confidence=0.0,
                decision="BREAK",
                rule_contributions=[self._to_contribution(r) for r in results],
                blocking_rules=[],
                explanation="No scoring rules executed - possible data quality issue",
                total_ai_contribution=0.0,
                ai_involvement="NONE",
                trade_id=trade_id,
                cash_id=cash_id,
            )
        
        total_weight = sum(r.weight for r in valid_results)
        weighted_sum = sum(r.weight * r.score for r in valid_results)
        
        # Normalize confidence
        if total_weight > 0:
            base_confidence = weighted_sum / total_weight
        else:
            base_confidence = 0.0
        
        # 3. Track and cap AI contribution
        total_ai_contribution = sum(r.ai_contribution for r in results)
        ai_cap = self.thresholds.ai_cap_global
        
        if total_ai_contribution > ai_cap:
            logger.warning(f"AI contribution {total_ai_contribution:.3f} exceeds cap {ai_cap}")
            total_ai_contribution = ai_cap  # Hard cap enforcement
        
        # AI can only ADD to confidence, never establish it
        # Confidence = base_from_rules + min(ai_delta, 0.10)
        final_confidence = min(1.0, base_confidence + total_ai_contribution)
        
        # 4. Determine decision
        decision = self.thresholds.get_decision(final_confidence)
        
        # 5. Determine AI involvement level
        if total_ai_contribution > 0:
            # Check which tier AI was involved in
            ai_tiers = [r.tier for r in results if r.ai_involved]
            if 5 in ai_tiers:
                ai_involvement = "SIMILARITY"
            elif 4 in ai_tiers:
                ai_involvement = "NORMALIZATION" 
            else:
                ai_involvement = "NORMALIZATION"
        else:
            ai_involvement = "NONE"
        
        # 6. Generate explanation
        explanation = self._generate_explanation(
            results, final_confidence, decision, total_ai_contribution
        )
        
        return AggregatedResult(
            confidence=final_confidence,
            decision=decision,
            rule_contributions=[self._to_contribution(r) for r in results],
            blocking_rules=[],
            explanation=explanation,
            total_ai_contribution=total_ai_contribution,
            ai_involvement=ai_involvement,
            trade_id=trade_id,
            cash_id=cash_id,
        )
    
    def _to_contribution(self, result: RuleResult) -> Dict[str, Any]:
        """Convert RuleResult to contribution dict."""
        return {
            "rule_id": result.rule_id,
            "tier": result.tier,
            "score": round(result.score, 4),
            "weight": round(result.weight, 4),
            "contribution": round(result.contribution, 4),
            "passed": result.passed,
            "is_hard_fail": result.is_hard_fail,
            "message": result.message,
        }
    
    def _generate_explanation(self, results: List[RuleResult], 
                              confidence: float, 
                              decision: str,
                              ai_contribution: float) -> str:
        """
        Generate human-readable explanation of decision.
        
        Format:
        "[DECISION] with X% confidence.
         Primary factors: Rule1 (Y%), Rule2 (Z%).
         AI assistance: [NONE/description]."
        """
        # Sort by contribution (descending)
        sorted_results = sorted(
            [r for r in results if r.score >= 0 and r.tier >= 2],
            key=lambda r: r.contribution,
            reverse=True
        )
        
        # Top 3 contributors
        top_contributors = sorted_results[:3]
        factor_parts = []
        for r in top_contributors:
            pct = r.contribution * 100
            factor_parts.append(f"{r.rule_id} ({pct:.1f}%)")
        
        factors_str = ", ".join(factor_parts) if factor_parts else "No primary factors"
        
        # AI description
        if ai_contribution > 0:
            ai_str = f"AI assisted with {ai_contribution*100:.1f}% boost"
        else:
            ai_str = "No AI assistance required"
        
        return (
            f"{decision} with {confidence*100:.1f}% confidence. "
            f"Primary factors: {factors_str}. "
            f"{ai_str}."
        )
    
    @staticmethod
    def aggregate_legacy(results: List[RuleResult]) -> Dict[str, Any]:
        """
        DEPRECATED: Legacy aggregation for backward compatibility.
        
        Use aggregate() for new code.
        """
        report = {
            "status": "PASSED",
            "worst_severity": "INFO",
            "score_total": 0.0,
            "break_count": 0,
            "breaks": [],
            "warnings": [],
            "matches": [],
            "ai_training_payloads": [],
            "domain_summary": {}
        }
        
        total_weight = 0
        matched_trade_ids = set()
        
        for res in results:
            domain = res.details.get("domain", "UNKNOWN")
            if domain not in report["domain_summary"]:
                report["domain_summary"][domain] = {"passed": 0, "failed": 0, "skipped": 0}
            
            if res.score == -1:
                report["domain_summary"][domain]["skipped"] += 1
                continue
                
            if res.passed:
                report["domain_summary"][domain]["passed"] += 1
                total_weight += 1
                report["score_total"] += 1
                
                if (res.details.get("match_algorithm") == "PROPOSED_MATCH" and 
                    "id" in res.details):
                    trade_id = res.details.get("id")
                    cash_id = res.details.get("cash_id")
                    
                    if trade_id and cash_id and trade_id not in matched_trade_ids:
                        report["matches"].append({
                            "trade_id": trade_id,
                            "cash_id": cash_id,
                            "rule_id": res.rule_id,
                            "confidence": 1.0 if res.score == 1.0 else 0.95
                        })
                        matched_trade_ids.add(trade_id)
            else:
                report["domain_summary"][domain]["failed"] += 1
                total_weight += 1
                report["break_count"] += 1
                
                payload = {
                    "rule_id": res.rule_id,
                    "message": res.message,
                    "severity": res.severity,
                    "break_type": res.break_type,
                    "details": res.details
                }
                
                if res.severity == "LOW" or res.break_type == "WARNING":
                    report["warnings"].append(payload)
                else:
                    report["breaks"].append(payload)
                    report["status"] = "FAILED"
                    
                    curr_weight = ResultAggregator.SEVERITY_WEIGHT.get(report["worst_severity"], 0)
                    new_weight = ResultAggregator.SEVERITY_WEIGHT.get(res.severity, 0)
                    if new_weight > curr_weight:
                        report["worst_severity"] = res.severity

                if "raw_context" in res.details:
                    report["ai_training_payloads"].append({
                        "rule_id": res.rule_id,
                        "context": res.details["raw_context"],
                        "outcome": "FAIL",
                        "severity": res.severity
                    })

        if total_weight > 0:
            report["final_score_pct"] = (report["score_total"] / total_weight) * 100
        else:
            report["final_score_pct"] = 100.0
        
        report["match_count"] = len(report["matches"])

        return report
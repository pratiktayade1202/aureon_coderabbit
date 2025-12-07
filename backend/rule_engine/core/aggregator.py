# backend/rule_engine/core/aggregator.py

from typing import List, Dict, Any
from .result import RuleResult

class ResultAggregator:
    """
    [Structural Fix #3]
    Aggregates individual RuleResults into a cohesive Reconciliation Report.
    Calculates worst severity, groups by domain, and extracts AI training data.
    """
    
    SEVERITY_WEIGHT = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
        "INFO": 0,
        None: 0
    }

    @staticmethod
    def aggregate(results: List[RuleResult]) -> Dict[str, Any]:
        report = {
            "status": "PASSED",
            "worst_severity": "INFO",
            "score_total": 0.0,
            "break_count": 0,
            "breaks": [],
            "warnings": [],
            "ai_training_payloads": [], # For Phase 2
            "domain_summary": {}
        }
        
        total_weight = 0
        
        for res in results:
            # 1. Update Domain Summary
            domain = res.details.get("domain", "UNKNOWN")
            if domain not in report["domain_summary"]:
                report["domain_summary"][domain] = {"passed": 0, "failed": 0, "skipped": 0}
            
            if res.score == -1:
                report["domain_summary"][domain]["skipped"] += 1
                continue # Skip scoring for skipped rules
                
            if res.passed:
                report["domain_summary"][domain]["passed"] += 1
                total_weight += 1
                report["score_total"] += 1
            else:
                report["domain_summary"][domain]["failed"] += 1
                total_weight += 1
                report["break_count"] += 1
                
                # 2. Track Breaks vs Warnings
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
                    
                    # 3. Update Worst Severity
                    curr_weight = ResultAggregator.SEVERITY_WEIGHT.get(report["worst_severity"], 0)
                    new_weight = ResultAggregator.SEVERITY_WEIGHT.get(res.severity, 0)
                    if new_weight > curr_weight:
                        report["worst_severity"] = res.severity

                # 4. Extract Machine Data for AI
                if "raw_context" in res.details:
                    report["ai_training_payloads"].append({
                        "rule_id": res.rule_id,
                        "context": res.details["raw_context"],
                        "outcome": "FAIL",
                        "severity": res.severity
                    })

        # Finalize Score
        if total_weight > 0:
            report["final_score_pct"] = (report["score_total"] / total_weight) * 100
        else:
            report["final_score_pct"] = 100.0

        return report
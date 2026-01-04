# backend/rule_engine/core/result.py
"""
Enhanced RuleResult structure for Hybrid Rule Engine 2.0.

Every rule MUST emit a structured result with weighted scoring.
This replaces binary pass/fail with continuous confidence scoring.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class RuleResult:
    """
    Weighted rule result for confidence aggregation.
    
    Key changes from v1:
    - Added tier for rule hierarchy
    - Added weight for contribution calculation
    - Added is_hard_fail for invariant enforcement
    - Added failure_mode for categorized breaks
    - Added raw_values for audit trail
    """
    
    # Identity
    rule_id: str                          # e.g., "FT_001", "INV_002"
    tier: int = 2                         # 0-5 (0=DataQuality, 1=Invariant, etc.)
    
    # Scoring (0.0 to 1.0)
    score: float = 1.0                    # 1.0 = Perfect, 0.0 = Complete fail
    weight: float = 0.10                  # Contribution weight (sum to 1.0)
    
    # Status
    passed: bool = True                   # Convenience flag (score >= threshold)
    is_hard_fail: bool = False            # True for Tier 0-1 invariants (no override)
    
    # Break information
    failure_mode: Optional[str] = None    # e.g., "AMOUNT_MISMATCH", "CURRENCY_MISMATCH"
    break_type: Optional[str] = None      # e.g., "DATA_QUALITY", "ECONOMIC", "TIMING"
    severity: Optional[str] = None        # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    amount_diff: float = 0.0              # For economic breaks
    
    # Explanation
    message: str = ""                     # Human-readable summary
    justification: str = ""               # Detailed explanation for audit
    
    # Audit data
    raw_values: Dict[str, Any] = field(default_factory=dict)  # Debug/audit data
    details: Dict[str, Any] = field(default_factory=dict)     # Additional context
    
    # Metadata
    ai_involved: bool = False             # True if AI contributed to this result
    ai_contribution: float = 0.0          # AI's contribution to score (max 0.10)
    
    def __post_init__(self):
        """Auto-set severity based on tier if not provided."""
        if self.severity is None:
            if self.tier == 0:
                self.severity = "CRITICAL" if not self.passed else "INFO"
            elif self.tier == 1:
                self.severity = "CRITICAL" if not self.passed else "INFO"
            elif self.tier == 2:
                self.severity = "HIGH" if not self.passed else "INFO"
            elif self.tier == 3:
                self.severity = "MEDIUM" if not self.passed else "INFO"
            else:
                self.severity = "LOW" if not self.passed else "INFO"
        
        # Tier 0-1 are always hard failures
        if self.tier <= 1 and not self.passed:
            self.is_hard_fail = True
    
    @property
    def contribution(self) -> float:
        """Weighted contribution to final confidence."""
        return self.weight * self.score
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response and audit logging."""
        return {
            "rule_id": self.rule_id,
            "tier": self.tier,
            "score": round(self.score, 4),
            "weight": round(self.weight, 4),
            "contribution": round(self.contribution, 4),
            "passed": self.passed,
            "is_hard_fail": self.is_hard_fail,
            "failure_mode": self.failure_mode,
            "break_type": self.break_type,
            "severity": self.severity,
            "message": self.message,
            "justification": self.justification,
            "amount_diff": self.amount_diff,
            "ai_involved": self.ai_involved,
            "ai_contribution": round(self.ai_contribution, 4),
        }
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Full serialization including raw values for audit trail."""
        result = self.to_dict()
        result["raw_values"] = self.raw_values
        result["details"] = self.details
        return result


@dataclass
class AggregatedResult:
    """
    Final reconciliation decision after all rules execute.
    
    Decisions:
    - MATCH: confidence >= 0.95 (auto-commit)
    - REVIEW: 0.75 <= confidence < 0.95 (human review required)
    - BREAK: confidence < 0.75 (unresolvable)
    """
    
    # Decision
    confidence: float                     # 0.0 to 1.0
    decision: str                         # "MATCH", "REVIEW", "BREAK"
    
    # Contributor breakdown
    rule_contributions: list = field(default_factory=list)  # List of {rule_id, score, weight, contribution}
    
    # Blocking rules (for BREAK decisions)
    blocking_rules: list = field(default_factory=list)      # Rules that caused hard failure
    
    # Explanation
    explanation: str = ""                 # Human-readable decision rationale
    
    # AI tracking
    total_ai_contribution: float = 0.0    # Sum of AI contributions (should be <= 0.10)
    ai_involvement: str = "NONE"          # "NONE", "NORMALIZATION", "SIMILARITY"
    
    # Audit
    trade_id: Optional[int] = None
    cash_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": round(self.confidence, 4),
            "decision": self.decision,
            "rule_contributions": self.rule_contributions,
            "blocking_rules": [r.to_dict() if hasattr(r, 'to_dict') else r for r in self.blocking_rules],
            "explanation": self.explanation,
            "total_ai_contribution": round(self.total_ai_contribution, 4),
            "ai_involvement": self.ai_involvement,
            "trade_id": self.trade_id,
            "cash_id": self.cash_id,
        }
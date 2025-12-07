# backend/rule_engine/core/result.py

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

@dataclass
class RuleResult:
    rule_id: str
    passed: bool
    score: float = 1.0  # 1.0 = Perfect Match, 0.0 = Total Fail
    
    # Details for the Break/Exception log
    break_type: Optional[str] = None  # e.g., 'DATA', 'ECONOMIC'
    severity: Optional[str] = None    # e.g., 'HIGH', 'LOW'
    amount_diff: float = 0.0
    
    message: str = ""
    details: dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "score": self.score,
            "break_type": self.break_type,
            "severity": self.severity,
            "message": self.message,
            "amount_diff": self.amount_diff
        }
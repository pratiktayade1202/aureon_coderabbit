# backend/rule_engine/core/config.py
"""
Rule Engine Configuration - Approved Weight Distribution.

These weights are FROZEN per architectural review (2026-01-03).
Changes require Principal Architect approval.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RuleWeights:
    """
    APPROVED weight distribution for confidence aggregation.
    
    Total: 100% (1.0)
    
    Changes from v1:
    - Reference reduced from 20% to 15% (India/APAC narrative unreliability)
    - Structural carved out explicitly at 5%
    """
    
    # Tier 2: Financial Tolerances
    amount_match: float = 0.30        # Primary matching criterion
    
    # Tier 3: Temporal Rules
    date_match: float = 0.25          # Settlement timing critical
    
    # Tier 4: Structural
    reference_match: float = 0.15     # Reduced: narratives unreliable in India/APAC
    structural: float = 0.05          # Partial fills, netting patterns
    
    # Tier 1: Invariants (binary but weighted)
    currency_match: float = 0.10      # Binary but important
    direction_match: float = 0.10     # Binary but important
    
    # Tier 5: Contextual
    contextual: float = 0.05          # Weak signal, nice-to-have
    
    def validate(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = (
            self.amount_match + self.date_match + self.reference_match +
            self.structural + self.currency_match + self.direction_match +
            self.contextual
        )
        return abs(total - 1.0) < 0.001


@dataclass
class ThresholdConfig:
    """
    Decision thresholds - APPROVED configuration.
    
    Phase 1 (conservative):
    - AUTO MATCH >= 0.95
    - REVIEW [0.75, 0.95)
    - BREAK < 0.75
    """
    
    auto_match: float = 0.95      # Confidence for auto-commit
    review_floor: float = 0.75    # Below this = BREAK
    
    # AI contribution limits
    ai_cap_tier4: float = 0.05    # Max AI contribution at Tier 4
    ai_cap_tier5: float = 0.10    # Max AI contribution at Tier 5
    ai_cap_global: float = 0.10   # Absolute AI cap
    
    def get_decision(self, confidence: float) -> str:
        """Determine decision based on confidence."""
        if confidence >= self.auto_match:
            return "MATCH"
        elif confidence >= self.review_floor:
            return "REVIEW"
        else:
            return "BREAK"


@dataclass
class ToleranceConfig:
    """
    Financial tolerance parameters.
    
    These can be overridden per broker/fund via RuleProfile.
    """
    
    # Amount tolerances
    amount_abs_tolerance: float = 0.50      # ₹0.50 absolute
    amount_pct_tolerance: float = 0.0001    # 0.01% percentage
    
    # Date tolerances
    settlement_t_plus: int = 1              # Default T+1 (equity)
    settlement_max_days: int = 3            # Maximum T+3
    
    # Fee tolerances
    stt_tolerance: float = 5.0              # ₹5 tolerance on STT
    gst_tolerance: float = 1.0              # ₹1 tolerance on GST
    stamp_duty_tolerance: float = 5.0       # ₹5 tolerance
    
    # Rounding
    rounding_precision: float = 0.01        # ₹0.01


@dataclass  
class RuleProfile:
    """
    Rule enablement profiles - per broker/fund/asset class.
    
    Mitigates rule explosion paralysis by allowing granular control.
    Implement during Phase M3.
    """
    
    profile_id: str                                     # e.g., "HDFC_EQUITY_DOMESTIC"
    enabled_rules: set = field(default_factory=set)     # ["FT_001", "TMP_002", ...]
    disabled_rules: set = field(default_factory=set)
    weight_overrides: Dict[str, float] = field(default_factory=dict)  # {"FT_001": 0.35}
    tolerance_overrides: Dict[str, float] = field(default_factory=dict)
    
    def is_rule_enabled(self, rule_id: str) -> bool:
        """Check if rule should run for this profile."""
        if rule_id in self.disabled_rules:
            return False
        if self.enabled_rules and rule_id not in self.enabled_rules:
            return False
        return True
    
    def get_weight(self, rule_id: str, default_weight: float) -> float:
        """Get weight for rule, applying any overrides."""
        return self.weight_overrides.get(rule_id, default_weight)


# Default singleton instances
DEFAULT_WEIGHTS = RuleWeights()
DEFAULT_THRESHOLDS = ThresholdConfig()
DEFAULT_TOLERANCES = ToleranceConfig()


def get_engine_config() -> Dict:
    """
    Get current engine configuration for audit logging.
    """
    return {
        "weights": {
            "amount": DEFAULT_WEIGHTS.amount_match,
            "date": DEFAULT_WEIGHTS.date_match,
            "reference": DEFAULT_WEIGHTS.reference_match,
            "structural": DEFAULT_WEIGHTS.structural,
            "currency": DEFAULT_WEIGHTS.currency_match,
            "direction": DEFAULT_WEIGHTS.direction_match,
            "contextual": DEFAULT_WEIGHTS.contextual,
        },
        "thresholds": {
            "auto_match": DEFAULT_THRESHOLDS.auto_match,
            "review_floor": DEFAULT_THRESHOLDS.review_floor,
            "ai_cap": DEFAULT_THRESHOLDS.ai_cap_global,
        },
        "tolerances": {
            "amount_abs": DEFAULT_TOLERANCES.amount_abs_tolerance,
            "amount_pct": DEFAULT_TOLERANCES.amount_pct_tolerance,
            "settlement_t_plus": DEFAULT_TOLERANCES.settlement_t_plus,
        }
    }

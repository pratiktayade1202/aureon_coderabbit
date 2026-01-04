# backend/rule_engine/core/match_config.py
"""
Match Configuration (v2.1)

Configurable matching parameters that can be loaded from tenant settings.
This replaces hardcoded tolerances with a flexible, auditable configuration.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MatchConfig:
    """
    Configuration for the matching engine.
    
    All tolerances and thresholds are configurable and can be loaded
    from TenantSettings for per-tenant customization.
    """
    
    # === Amount Tolerances ===
    exact_tolerance: float = 0.001      # 0.1% - considered exact match
    standard_tolerance: float = 0.01    # 1% - standard auto-match
    fuzzy_tolerance: float = 0.05       # 5% - requires human review
    
    # === Date Tolerances ===
    date_tolerance_days: int = 2        # T+2 default for equity
    
    # === Confidence Thresholds ===
    auto_match_threshold: float = 0.85  # Auto-propose above this
    review_threshold: float = 0.60      # Flag for human review
    
    # === Scoring Weights (must sum to 1.0) ===
    weight_amount: float = 0.40         # Amount match weight
    weight_date: float = 0.20           # Date proximity weight
    weight_reference: float = 0.20      # Reference/ID match weight
    weight_description: float = 0.20    # Description similarity weight
    
    # === Feature Flags ===
    enable_fuzzy_description: bool = True   # Use description matching
    enable_partial_matching: bool = True    # M:N matching for partials
    enable_netting: bool = False            # Netting detection
    
    def __post_init__(self):
        """Validate configuration."""
        total_weight = (
            self.weight_amount + 
            self.weight_date + 
            self.weight_reference + 
            self.weight_description
        )
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total_weight}")
    
    @classmethod
    def from_tenant_settings(cls, settings) -> "MatchConfig":
        """Create config from TenantSettings model."""
        return cls(
            standard_tolerance=getattr(settings, 'amount_tolerance_percent', 0.01),
            date_tolerance_days=getattr(settings, 'date_tolerance_days', 2),
            auto_match_threshold=getattr(settings, 'ai_commit_threshold', 0.85),
        )
    
    @classmethod
    def strict(cls) -> "MatchConfig":
        """Strict configuration for high-value trades."""
        return cls(
            exact_tolerance=0.0001,
            standard_tolerance=0.005,
            fuzzy_tolerance=0.02,
            auto_match_threshold=0.95,
        )
    
    @classmethod
    def lenient(cls) -> "MatchConfig":
        """Lenient configuration for known noisy data sources."""
        return cls(
            exact_tolerance=0.01,
            standard_tolerance=0.03,
            fuzzy_tolerance=0.10,
            auto_match_threshold=0.75,
        )


@dataclass
class MatchScore:
    """
    Result of scoring a potential match.
    """
    score: float                    # 0.0 to 1.0 overall confidence
    action: str                     # PROPOSE, REVIEW, or BREAK
    match_tier: str                 # EXACT, STANDARD, FUZZY, or NONE
    
    # Breakdown by component
    amount_score: float = 0.0
    date_score: float = 0.0
    reference_score: float = 0.0
    description_score: float = 0.0
    
    # Details for explainability
    amount_diff: float = 0.0
    amount_diff_pct: float = 0.0
    date_diff_days: int = 0
    matched_references: list = field(default_factory=list)
    
    @property
    def is_confident(self) -> bool:
        """True if score is above auto-match threshold (0.85 default)."""
        return self.score >= 0.85
    
    @property
    def needs_review(self) -> bool:
        """True if score is in review range (0.60-0.85)."""
        return 0.60 <= self.score < 0.85
    
    def to_explanation(self) -> dict:
        """
        Deterministic explainability schema (v2.1).
        No prose - auditors don't trust English.
        """
        return {
            "rule_id": "MULTI_TIER_MATCH",
            "match_tier": self.match_tier,
            "confidence": round(self.score, 4),
            "action": self.action,
            "breakdown": {
                "amount": round(self.amount_score, 4),
                "date": round(self.date_score, 4),
                "reference": round(self.reference_score, 4),
                "description": round(self.description_score, 4),
            },
            "fields_compared": {
                "amount_diff": round(self.amount_diff, 2),
                "amount_diff_pct": round(self.amount_diff_pct, 6),
                "date_diff_days": self.date_diff_days,
                "matched_references": self.matched_references,
            },
        }

# backend/rule_engine/tiers/__init__.py
"""
Tier-based Rule Modules for Hybrid Rule Engine 2.0.

Tier hierarchy:
- Tier 0: Data Quality (Gate Rules) - DQ_*
- Tier 1: Hard Invariants (Cannot Override) - INV_*
- Tier 2: Financial Tolerances - FT_*
- Tier 3: Temporal Rules - TMP_*
- Tier 4: Structural Patterns - STR_*
- Tier 5: Contextual Heuristics - CTX_*
"""

from .tier0_data_quality import DataQualityGate
from .tier1_invariants import HardInvariantChecker
from .tier2_tolerances import FinancialToleranceScorer
from .tier3_temporal import TemporalScorer

__all__ = [
    "DataQualityGate",
    "HardInvariantChecker",
    "FinancialToleranceScorer",
    "TemporalScorer",
]

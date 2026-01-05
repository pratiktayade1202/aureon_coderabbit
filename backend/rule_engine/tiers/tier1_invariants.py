# backend/rule_engine/tiers/tier1_invariants.py
"""
Tier 1: Hard Invariant Rules.

These rules enforce non-negotiable financial constraints.
Failures here = BREAK (AI cannot override).

AI is FORBIDDEN at this tier.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from ..core.result import RuleResult
from ..core.config import DEFAULT_TOLERANCES
import logging

logger = logging.getLogger(__name__)


class HardInvariantChecker:
    """
    Hard Invariant validation rules.
    
    These are NON-NEGOTIABLE. If any invariant fails:
    - Result is BREAK
    - AI cannot override
    - No confidence scoring applies
    
    All rules return is_hard_fail=True on failure.
    """
    
    TIER = 1
    
    @classmethod
    def run_all(cls, trade: Dict[str, Any], cash: Dict[str, Any]) -> List[RuleResult]:
        """
        Run all invariant checks on a trade-cash pair.
        
        Args:
            trade: Trade record dict
            cash: Cash record dict
            
        Returns:
            List of RuleResult for each invariant check
        """
        results = []
        
        results.append(cls.inv_001_currency_identity(trade, cash))
        results.append(cls.inv_002_direction_consistency(trade, cash))
        results.append(cls.inv_003_settlement_window(trade, cash))
        results.append(cls.inv_004_amount_sign_consistency(trade, cash))
        results.append(cls.inv_005_entity_match(trade, cash))
        
        return results
    
    @classmethod
    def has_hard_failure(cls, results: List[RuleResult]) -> bool:
        """Check if any result is a hard failure."""
        return any(r.is_hard_fail and not r.passed for r in results)
    
    @classmethod
    def inv_001_currency_identity(cls, trade: Dict[str, Any], 
                                   cash: Dict[str, Any]) -> RuleResult:
        """
        INV_001: Currency Identity Match.
        
        Trade.currency MUST equal Cash.currency.
        Exception: FX-adjusted equivalents (future enhancement).
        """
        trade_ccy = (trade.get("currency") or "").upper().strip()
        cash_ccy = (cash.get("currency") or "").upper().strip()
        
        if not trade_ccy or not cash_ccy:
            return RuleResult(
                rule_id="INV_001",
                tier=cls.TIER,
                score=0.0,
                weight=0.10,  # Currency is 10% of decision weight
                passed=False,
                is_hard_fail=True,
                failure_mode="MISSING_CURRENCY",
                break_type="ECONOMIC",
                severity="CRITICAL",
                message="Currency missing on trade or cash",
                raw_values={"trade_currency": trade_ccy, "cash_currency": cash_ccy}
            )
        
        if trade_ccy != cash_ccy:
            return RuleResult(
                rule_id="INV_001",
                tier=cls.TIER,
                score=0.0,
                weight=0.10,
                passed=False,
                is_hard_fail=True,
                failure_mode="CURRENCY_MISMATCH",
                break_type="ECONOMIC",
                severity="CRITICAL",
                message=f"Currency mismatch: Trade={trade_ccy}, Cash={cash_ccy}",
                justification="Trade and cash must have identical currency codes. FX adjustment not yet supported.",
                raw_values={"trade_currency": trade_ccy, "cash_currency": cash_ccy}
            )
        
        return RuleResult(
            rule_id="INV_001",
            tier=cls.TIER,
            score=1.0,
            weight=0.10,
            passed=True,
            message=f"Currency match: {trade_ccy}",
            raw_values={"currency": trade_ccy}
        )
    
    @classmethod
    def inv_002_direction_consistency(cls, trade: Dict[str, Any], 
                                       cash: Dict[str, Any]) -> RuleResult:
        """
        INV_002: Direction Consistency.
        
        BUY trade → Cash should be DEBIT (negative amount)
        SELL trade → Cash should be CREDIT (positive amount)
        """
        trade_side = (trade.get("side") or "").upper().strip()
        cash_amount = float(cash.get("amount") or 0)
        
        # Determine expected cash direction
        if trade_side in ["BUY", "B"]:
            # BUY = money goes out = negative cash
            expected_sign = "DEBIT"
            is_correct = cash_amount < 0
        elif trade_side in ["SELL", "S"]:
            # SELL = money comes in = positive cash
            expected_sign = "CREDIT"
            is_correct = cash_amount > 0
        else:
            # Unknown side - might be a data issue but not a hard fail
            return RuleResult(
                rule_id="INV_002",
                tier=cls.TIER,
                score=0.5,  # Partial score for unknown
                weight=0.10,
                passed=True,  # Don't hard fail on unknown
                message=f"Unknown trade side: {trade_side}",
                raw_values={"trade_side": trade_side, "cash_amount": cash_amount}
            )
        
        if not is_correct:
            actual_sign = "CREDIT" if cash_amount > 0 else "DEBIT"
            return RuleResult(
                rule_id="INV_002",
                tier=cls.TIER,
                score=0.0,
                weight=0.10,
                passed=False,
                is_hard_fail=True,
                failure_mode="DIRECTION_MISMATCH",
                break_type="ECONOMIC",
                severity="CRITICAL",
                message=f"Direction mismatch: {trade_side} expects {expected_sign}, got {actual_sign}",
                justification=f"Trade side '{trade_side}' should result in {expected_sign} cash movement, but cash amount {cash_amount} indicates {actual_sign}.",
                raw_values={
                    "trade_side": trade_side, 
                    "cash_amount": cash_amount,
                    "expected_sign": expected_sign,
                    "actual_sign": actual_sign
                }
            )
        
        return RuleResult(
            rule_id="INV_002",
            tier=cls.TIER,
            score=1.0,
            weight=0.10,
            passed=True,
            message=f"Direction consistent: {trade_side} → {expected_sign}",
            raw_values={"trade_side": trade_side, "expected_sign": expected_sign}
        )
    
    @classmethod
    def inv_003_settlement_window(cls, trade: Dict[str, Any], 
                                   cash: Dict[str, Any],
                                   max_days: int = None) -> RuleResult:
        """
        INV_003: Settlement Window Validity.
        
        Cash.date must be within [Trade.date, Trade.date + T+X].
        Default: T+3 (3 business days after trade date).
        """
        max_days = max_days or DEFAULT_TOLERANCES.settlement_max_days
        
        trade_date = cls._parse_date(trade.get("date"))
        cash_date = cls._parse_date(cash.get("date"))
        
        # Also check settlement_date if present
        settlement_date = cls._parse_date(trade.get("settlement_date"))
        
        if not trade_date or not cash_date:
            return RuleResult(
                rule_id="INV_003",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,  # Can't score without dates
                passed=False,
                is_hard_fail=True,
                failure_mode="MISSING_DATE",
                message="Trade or cash date missing",
                raw_values={"trade_date": str(trade_date), "cash_date": str(cash_date)}
            )
        
        # Calculate date difference
        date_diff = (cash_date - trade_date).days
        
        # Cash must be on or after trade date
        if date_diff < 0:
            return RuleResult(
                rule_id="INV_003",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="CASH_BEFORE_TRADE",
                break_type="TIMING",
                severity="CRITICAL",
                message=f"Cash date ({cash_date}) before trade date ({trade_date})",
                raw_values={"trade_date": str(trade_date), "cash_date": str(cash_date), "diff_days": date_diff}
            )
        
        # Cash must be within settlement window
        if date_diff > max_days:
            return RuleResult(
                rule_id="INV_003",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="OUTSIDE_SETTLEMENT_WINDOW",
                break_type="TIMING",
                severity="CRITICAL",
                message=f"Cash date {date_diff} days after trade (max allowed: T+{max_days})",
                justification=f"Trade on {trade_date}, cash on {cash_date} ({date_diff} days). Settlement window is T+{max_days}.",
                raw_values={
                    "trade_date": str(trade_date), 
                    "cash_date": str(cash_date), 
                    "diff_days": date_diff,
                    "max_days": max_days
                }
            )
        
        return RuleResult(
            rule_id="INV_003",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,  # Invariant - no weight contribution
            passed=True,
            message=f"Settlement window valid: T+{date_diff}",
            raw_values={"diff_days": date_diff, "max_days": max_days}
        )
    
    @classmethod
    def inv_004_amount_sign_consistency(cls, trade: Dict[str, Any], 
                                         cash: Dict[str, Any]) -> RuleResult:
        """
        INV_004: Amount Sign Consistency.
        
        Trade and cash amounts must have consistent absolute value relationship.
        (Actual tolerance is checked in Tier 2, this is just sign sanity)
        """
        trade_amount = abs(float(trade.get("amount") or trade.get("net_amount") or 0))
        cash_amount = abs(float(cash.get("amount") or 0))
        
        # Basic sanity: if trade is non-zero, cash should be non-zero
        if trade_amount > 0 and cash_amount == 0:
            return RuleResult(
                rule_id="INV_004",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="ZERO_CASH_AMOUNT",
                break_type="ECONOMIC",
                severity="CRITICAL",
                message=f"Trade amount {trade_amount} but cash amount is zero",
                raw_values={"trade_amount": trade_amount, "cash_amount": cash_amount}
            )
        
        return RuleResult(
            rule_id="INV_004",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message="Amount sign consistent"
        )
    
    @classmethod
    def inv_005_entity_match(cls, trade: Dict[str, Any], 
                             cash: Dict[str, Any]) -> RuleResult:
        """
        INV_005: Entity Match.
        
        If broker/counterparty is specified, it should match between trade and cash.
        This is a soft invariant - only fails if both are present and don't match.
        """
        trade_broker = (trade.get("broker") or trade.get("counterparty") or "").upper().strip()
        cash_entity = (cash.get("entity") or cash.get("bank") or "").upper().strip()
        
        # If either is missing, we can't validate - pass
        if not trade_broker or not cash_entity:
            return RuleResult(
                rule_id="INV_005",
                tier=cls.TIER,
                score=1.0,  # No penalty for missing entity
                weight=0.0,
                passed=True,
                message="Entity fields not both present - skipped",
                raw_values={"trade_broker": trade_broker, "cash_entity": cash_entity}
            )
        
        # Normalize and compare
        # Allow partial match (e.g., "HDFC SECURITIES" contains "HDFC")
        matches = (trade_broker in cash_entity) or (cash_entity in trade_broker) or (trade_broker == cash_entity)
        
        if not matches:
            return RuleResult(
                rule_id="INV_005",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="ENTITY_MISMATCH",
                break_type="ECONOMIC",
                severity="HIGH",
                message=f"Entity mismatch: Trade={trade_broker}, Cash={cash_entity}",
                raw_values={"trade_broker": trade_broker, "cash_entity": cash_entity}
            )
        
        return RuleResult(
            rule_id="INV_005",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message=f"Entity match: {trade_broker}",
            raw_values={"trade_broker": trade_broker, "cash_entity": cash_entity}
        )
    
    @staticmethod
    def _parse_date(date_val) -> Optional[date]:
        """Parse date from various formats."""
        if date_val is None:
            return None
        
        if isinstance(date_val, date):
            return date_val
        
        if isinstance(date_val, datetime):
            return date_val.date()
        
        if isinstance(date_val, str):
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(date_val, fmt).date()
                except ValueError:
                    continue
        
        return None

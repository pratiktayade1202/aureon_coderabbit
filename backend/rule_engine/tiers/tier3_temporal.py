# backend/rule_engine/tiers/tier3_temporal.py
"""
Tier 3: Temporal Rules (Settlement Cycle Logic).

These rules validate timing relationships between trades and cash.
Weight: Date (25%) - Settlement timing is critical.

AI is FORBIDDEN at this tier (except holiday list maintenance).
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from ..core.result import RuleResult
from ..core.config import DEFAULT_TOLERANCES, DEFAULT_WEIGHTS
import logging

logger = logging.getLogger(__name__)


class TemporalScorer:
    """
    Settlement timing and date alignment rules.
    
    Weight: 25% of decision (second most important after amount).
    """
    
    TIER = 3
    
    # Known market holidays (India NSE 2026 - placeholder)
    # In production, load from database or config
    MARKET_HOLIDAYS = {
        date(2026, 1, 26),  # Republic Day
        date(2026, 3, 17),  # Holi
        date(2026, 4, 10),  # Good Friday
        date(2026, 4, 14),  # Dr. Ambedkar Jayanti
        date(2026, 5, 1),   # May Day
        date(2026, 8, 15),  # Independence Day
        date(2026, 10, 2),  # Gandhi Jayanti
        date(2026, 11, 4),  # Diwali
        date(2026, 11, 5),  # Diwali (day 2)
        date(2026, 12, 25), # Christmas
    }
    
    @classmethod
    def run_all(cls, trade: Dict[str, Any], cash: Dict[str, Any],
                tolerances=None) -> List[RuleResult]:
        """
        Run all temporal checks on a trade-cash pair.
        """
        tolerances = tolerances or DEFAULT_TOLERANCES
        results = []
        
        results.append(cls.tmp_001_same_day_match(trade, cash))
        results.append(cls.tmp_002_t_plus_1(trade, cash))
        results.append(cls.tmp_003_extended_settlement(trade, cash))
        results.append(cls.tmp_004_value_date_alignment(trade, cash))
        
        return results
    
    @classmethod
    def tmp_001_same_day_match(cls, trade: Dict[str, Any], 
                                cash: Dict[str, Any]) -> RuleResult:
        """
        TMP_001: Same-Day (T+0) Match.
        
        Highest score for same-day settlement.
        """
        trade_date = cls._parse_date(trade.get("date"))
        cash_date = cls._parse_date(cash.get("date"))
        
        if not trade_date or not cash_date:
            return RuleResult(
                rule_id="TMP_001",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                message="Missing date for T+0 check"
            )
        
        if trade_date == cash_date:
            return RuleResult(
                rule_id="TMP_001",
                tier=cls.TIER,
                score=1.0,
                weight=DEFAULT_WEIGHTS.date_match,
                passed=True,
                message=f"Same-day settlement (T+0): {trade_date}",
                raw_values={"trade_date": str(trade_date), "cash_date": str(cash_date)}
            )
        
        # Not T+0 - let other temporal rules score
        return RuleResult(
            rule_id="TMP_001",
            tier=cls.TIER,
            score=0.0,  # No score from this rule
            weight=0.0,  # Other rules will provide date scoring
            passed=True,  # Not a failure
            message="Not T+0 settlement"
        )
    
    @classmethod
    def tmp_002_t_plus_1(cls, trade: Dict[str, Any], 
                          cash: Dict[str, Any]) -> RuleResult:
        """
        TMP_002: T+1 Standard Settlement.
        
        Default for Indian equity markets since 2024.
        Score: 1.0 for T+1, decay for other days.
        """
        trade_date = cls._parse_date(trade.get("date"))
        cash_date = cls._parse_date(cash.get("date"))
        
        if not trade_date or not cash_date:
            return RuleResult(
                rule_id="TMP_002",
                tier=cls.TIER,
                score=0.5,
                weight=DEFAULT_WEIGHTS.date_match,
                passed=True,
                message="Missing date - assuming valid"
            )
        
        # Calculate business days between
        calendar_days = (cash_date - trade_date).days
        business_days = cls._count_business_days(trade_date, cash_date)
        
        # Score based on business days
        if business_days == 1:
            # Perfect T+1
            score = 1.0
            message = f"T+1 settlement: Trade {trade_date} → Cash {cash_date}"
        elif business_days == 0:
            # T+0 (same day) - also good
            score = 1.0
            message = f"T+0 settlement: same day {trade_date}"
        elif business_days == 2:
            # T+2 - slightly lower score
            score = 0.90
            message = f"T+2 settlement: {business_days} business days"
        elif business_days == 3:
            # T+3 - acceptable but lower
            score = 0.80
            message = f"T+3 settlement: {business_days} business days"
        elif calendar_days < 0:
            # Cash before trade - suspicious
            score = 0.0
            message = f"Cash before trade ({calendar_days} days)"
        else:
            # Beyond T+3 - significant decay
            score = max(0.0, 0.7 - (business_days - 3) * 0.1)
            message = f"Extended settlement: T+{business_days}"
        
        return RuleResult(
            rule_id="TMP_002",
            tier=cls.TIER,
            score=score,
            weight=DEFAULT_WEIGHTS.date_match,
            passed=score >= 0.7,
            message=message,
            justification=f"Trade: {trade_date}, Cash: {cash_date}, Calendar days: {calendar_days}, Business days: {business_days}",
            raw_values={
                "trade_date": str(trade_date),
                "cash_date": str(cash_date),
                "calendar_days": calendar_days,
                "business_days": business_days
            }
        )
    
    @classmethod
    def tmp_003_extended_settlement(cls, trade: Dict[str, Any], 
                                     cash: Dict[str, Any]) -> RuleResult:
        """
        TMP_003: Extended Settlement Handling.
        
        Accounts for holidays and weekends that extend settlement.
        This is a supplementary check that adjusts scoring.
        """
        trade_date = cls._parse_date(trade.get("date"))
        cash_date = cls._parse_date(cash.get("date"))
        
        if not trade_date or not cash_date:
            return RuleResult(
                rule_id="TMP_003",
                tier=cls.TIER,
                score=1.0,
                weight=0.0,
                passed=True,
                message="Missing date for holiday check"
            )
        
        calendar_days = (cash_date - trade_date).days
        business_days = cls._count_business_days(trade_date, cash_date)
        holiday_adjustment = calendar_days - business_days
        
        if holiday_adjustment > 0:
            # Some days were holidays/weekends
            return RuleResult(
                rule_id="TMP_003",
                tier=cls.TIER,
                score=1.0,  # Full score - holidays accounted for
                weight=0.02,
                passed=True,
                message=f"Holiday-adjusted: {holiday_adjustment} non-business days between dates",
                raw_values={
                    "calendar_days": calendar_days,
                    "business_days": business_days,
                    "holiday_adjustment": holiday_adjustment
                }
            )
        
        return RuleResult(
            rule_id="TMP_003",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message="No holiday adjustment needed"
        )
    
    @classmethod
    def tmp_004_value_date_alignment(cls, trade: Dict[str, Any], 
                                      cash: Dict[str, Any]) -> RuleResult:
        """
        TMP_004: Value Date Alignment.
        
        If value_date is specified on cash, it should match settlement date.
        """
        settlement_date = cls._parse_date(
            trade.get("settlement_date") or trade.get("date")
        )
        value_date = cls._parse_date(cash.get("value_date") or cash.get("date"))
        
        if not settlement_date or not value_date:
            return RuleResult(
                rule_id="TMP_004",
                tier=cls.TIER,
                score=1.0,
                weight=0.0,
                passed=True,
                message="Value date check skipped - dates missing"
            )
        
        diff_days = abs((value_date - settlement_date).days)
        
        if diff_days == 0:
            score = 1.0
            message = "Value date aligned with settlement"
        elif diff_days == 1:
            score = 0.95
            message = f"Value date 1 day off from settlement"
        elif diff_days <= 3:
            score = 0.85
            message = f"Value date {diff_days} days from settlement"
        else:
            score = max(0.5, 1.0 - (diff_days * 0.1))
            message = f"Value date misalignment: {diff_days} days"
        
        return RuleResult(
            rule_id="TMP_004",
            tier=cls.TIER,
            score=score,
            weight=0.02,  # Low weight - supplementary
            passed=score >= 0.7,
            message=message,
            raw_values={
                "settlement_date": str(settlement_date),
                "value_date": str(value_date),
                "diff_days": diff_days
            }
        )
    
    @staticmethod
    def _parse_date(date_val) -> Optional[date]:
        """Parse date from various formats."""
        if date_val is None:
            return None
        
        if isinstance(date_val, date) and not isinstance(date_val, datetime):
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
    
    @classmethod
    def _count_business_days(cls, start: date, end: date) -> int:
        """
        Count business days between two dates (exclusive of start, inclusive of end).
        Accounts for weekends and known holidays.
        """
        if start >= end:
            return 0
        
        count = 0
        current = start + timedelta(days=1)
        
        while current <= end:
            # Skip weekends
            if current.weekday() < 5:  # Mon=0, Fri=4
                # Skip holidays
                if current not in cls.MARKET_HOLIDAYS:
                    count += 1
            current += timedelta(days=1)
        
        return count

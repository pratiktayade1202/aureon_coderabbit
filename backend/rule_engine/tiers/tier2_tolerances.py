# backend/rule_engine/tiers/tier2_tolerances.py
"""
Tier 2: Financial Tolerance Rules.

These rules perform numeric comparisons with configurable tolerances.
They DRIVE the matching process by scoring candidate pairs.

AI is FORBIDDEN at this tier.
"""

from typing import Dict, Any, List
from ..core.result import RuleResult
from ..core.config import DEFAULT_TOLERANCES, DEFAULT_WEIGHTS
import logging

logger = logging.getLogger(__name__)


class FinancialToleranceScorer:
    """
    Financial tolerance scoring rules.
    
    These rules emit weighted scores that contribute to confidence.
    Weight: Amount (30%) - Primary matching criterion.
    """
    
    TIER = 2
    
    @classmethod
    def run_all(cls, trade: Dict[str, Any], cash: Dict[str, Any],
                tolerances=None) -> List[RuleResult]:
        """
        Run all financial tolerance checks on a trade-cash pair.
        
        Args:
            trade: Trade record dict
            cash: Cash record dict
            tolerances: Optional ToleranceConfig override
            
        Returns:
            List of RuleResult with weighted scores
        """
        tolerances = tolerances or DEFAULT_TOLERANCES
        results = []
        
        results.append(cls.ft_001_amount_tolerance(trade, cash, tolerances))
        results.append(cls.ft_002_rounding_tolerance(trade, cash, tolerances))
        results.append(cls.ft_003_fee_decomposition(trade, cash))
        results.append(cls.ft_004_stt_validation(trade, cash, tolerances))
        results.append(cls.ft_005_gst_validation(trade, cash, tolerances))
        
        return results
    
    @classmethod
    def ft_001_amount_tolerance(cls, trade: Dict[str, Any], 
                                 cash: Dict[str, Any],
                                 tolerances=None) -> RuleResult:
        """
        FT_001: Amount Tolerance Check.
        
        Primary matching criterion (30% weight).
        Uses configurable absolute and percentage tolerance.
        
        Score decay:
        - Exact (< 0.01%): 1.0
        - Near exact (< 0.1%): 0.95
        - Close (< 0.5%): 0.85
        - Acceptable (< 1%): 0.75
        - Linear decay beyond
        """
        tolerances = tolerances or DEFAULT_TOLERANCES
        
        # Get trade amount (prefer net_amount for trade, gross_amount as fallback)
        trade_amount = abs(float(
            trade.get("net_amount") or trade.get("amount") or 0
        ))
        cash_amount = abs(float(cash.get("amount") or 0))
        
        if trade_amount == 0:
            return RuleResult(
                rule_id="FT_001",
                tier=cls.TIER,
                score=0.0,
                weight=DEFAULT_WEIGHTS.amount_match,
                passed=False,
                failure_mode="ZERO_TRADE_AMOUNT",
                message="Trade amount is zero"
            )
        
        # Calculate difference
        diff = abs(trade_amount - cash_amount)
        pct_diff = diff / trade_amount
        
        # Apply tolerance thresholds
        abs_tol = tolerances.amount_abs_tolerance
        pct_tol = tolerances.amount_pct_tolerance
        
        # Score calculation with decay
        if diff <= abs_tol or pct_diff <= pct_tol:
            score = 1.0
            message = f"Exact match within tolerance"
        elif pct_diff <= 0.001:  # < 0.1%
            score = 0.95
            message = f"Near-exact match ({pct_diff*100:.3f}% diff)"
        elif pct_diff <= 0.005:  # < 0.5%
            score = 0.85
            message = f"Close match ({pct_diff*100:.2f}% diff)"
        elif pct_diff <= 0.01:  # < 1%
            score = 0.75
            message = f"Acceptable match ({pct_diff*100:.2f}% diff)"
        else:
            # Linear decay beyond 1%
            score = max(0.0, 1.0 - (pct_diff * 10))
            message = f"Large difference ({pct_diff*100:.2f}% diff)"
        
        passed = score >= 0.70
        
        return RuleResult(
            rule_id="FT_001",
            tier=cls.TIER,
            score=score,
            weight=DEFAULT_WEIGHTS.amount_match,
            passed=passed,
            failure_mode="AMOUNT_MISMATCH" if not passed else None,
            break_type="ECONOMIC" if not passed else None,
            severity="HIGH" if not passed else "INFO",
            amount_diff=diff,
            message=message,
            justification=f"Trade: ₹{trade_amount:,.2f}, Cash: ₹{cash_amount:,.2f}, Diff: ₹{diff:,.2f} ({pct_diff*100:.4f}%)",
            raw_values={
                "trade_amount": trade_amount,
                "cash_amount": cash_amount,
                "diff": diff,
                "pct_diff": pct_diff,
                "abs_tolerance": abs_tol,
                "pct_tolerance": pct_tol
            }
        )
    
    @classmethod
    def ft_002_rounding_tolerance(cls, trade: Dict[str, Any], 
                                   cash: Dict[str, Any],
                                   tolerances=None) -> RuleResult:
        """
        FT_002: Rounding Tolerance Check.
        
        Checks if difference is within rounding precision (₹0.01).
        This is a sub-check of amount that specifically identifies rounding diffs.
        Low weight as it's supplementary.
        """
        tolerances = tolerances or DEFAULT_TOLERANCES
        
        trade_amount = abs(float(trade.get("net_amount") or trade.get("amount") or 0))
        cash_amount = abs(float(cash.get("amount") or 0))
        
        diff = abs(trade_amount - cash_amount)
        precision = tolerances.rounding_precision
        
        # Check if diff is purely a rounding issue
        is_rounding = diff <= precision * 100  # Up to 100 paisa / cents
        
        if is_rounding:
            score = 1.0
            message = f"Within rounding tolerance (₹{diff:.2f})"
        else:
            # Score based on how many multiples of precision
            score = max(0.0, 1.0 - (diff / (precision * 1000)))
            message = f"Exceeds rounding tolerance by ₹{diff - precision:.2f}"
        
        return RuleResult(
            rule_id="FT_002",
            tier=cls.TIER,
            score=score,
            weight=0.02,  # Low weight - supplementary check
            passed=score >= 0.5,
            message=message,
            raw_values={"diff": diff, "precision": precision}
        )
    
    @classmethod
    def ft_003_fee_decomposition(cls, trade: Dict[str, Any], 
                                  cash: Dict[str, Any]) -> RuleResult:
        """
        FT_003: Fee Decomposition.
        
        Validates: Gross - Net = Sum(fees)
        If fees are itemized on trade, verify they sum correctly.
        """
        gross = float(trade.get("gross_amount") or 0)
        net = float(trade.get("net_amount") or trade.get("amount") or 0)
        
        if gross == 0:
            # No gross amount - can't validate fee decomposition
            return RuleResult(
                rule_id="FT_003",
                tier=cls.TIER,
                score=1.0,  # No penalty for missing data
                weight=0.05,
                passed=True,
                message="Gross amount not provided - fee decomposition skipped"
            )
        
        # Sum up known fee fields
        fees = [
            float(trade.get("brokerage") or 0),
            float(trade.get("stt") or 0),
            float(trade.get("gst") or 0),
            float(trade.get("stamp_duty") or 0),
            float(trade.get("exchange_fee") or 0),
            float(trade.get("sebi_fee") or 0),
        ]
        total_fees = sum(fees)
        
        expected_net = gross + total_fees if trade.get("side", "").upper() == "BUY" else gross - total_fees
        
        # For BUY: Net = Gross + Fees (paying more)
        # For SELL: Net = Gross - Fees (receiving less)
        side = trade.get("side", "").upper()
        if side in ["BUY", "B"]:
            calculated_net = gross + total_fees
        else:
            calculated_net = gross - total_fees
        
        diff = abs(net - calculated_net)
        
        if diff <= 1.0:  # Within ₹1
            score = 1.0
            message = "Fee decomposition validated"
        elif diff <= 5.0:  # Within ₹5
            score = 0.9
            message = f"Minor fee variance: ₹{diff:.2f}"
        elif diff <= 10.0:
            score = 0.8
            message = f"Fee variance: ₹{diff:.2f}"
        else:
            score = max(0.5, 1.0 - (diff / 100))
            message = f"Significant fee variance: ₹{diff:.2f}"
        
        return RuleResult(
            rule_id="FT_003",
            tier=cls.TIER,
            score=score,
            weight=0.05,
            passed=score >= 0.7,
            message=message,
            justification=f"Gross: ₹{gross:,.2f}, Fees: ₹{total_fees:,.2f}, Expected Net: ₹{calculated_net:,.2f}, Actual Net: ₹{net:,.2f}",
            raw_values={
                "gross": gross,
                "net": net,
                "total_fees": total_fees,
                "calculated_net": calculated_net,
                "diff": diff,
                "side": side
            }
        )
    
    @classmethod
    def ft_004_stt_validation(cls, trade: Dict[str, Any], 
                               cash: Dict[str, Any],
                               tolerances=None) -> RuleResult:
        """
        FT_004: STT (Securities Transaction Tax) Validation.
        
        For equity trades in India:
        - Delivery BUY: 0.1% of trade value
        - Delivery SELL: 0.1% of trade value  
        - Intraday: 0.025% on sell side
        """
        tolerances = tolerances or DEFAULT_TOLERANCES
        
        stt_actual = float(trade.get("stt") or 0)
        
        if stt_actual == 0:
            # No STT on trade - might be exempt or not applicable
            return RuleResult(
                rule_id="FT_004",
                tier=cls.TIER,
                score=1.0,
                weight=0.02,
                passed=True,
                message="No STT on trade - possibly exempt"
            )
        
        # Calculate expected STT
        gross = float(trade.get("gross_amount") or trade.get("amount") or 0)
        trade_type = (trade.get("trade_type") or "delivery").lower()
        side = (trade.get("side") or "").upper()
        
        if trade_type == "intraday":
            # Intraday: 0.025% on sell only
            if side in ["SELL", "S"]:
                expected_stt = gross * 0.00025
            else:
                expected_stt = 0
        else:
            # Delivery: 0.1%
            expected_stt = gross * 0.001
        
        diff = abs(stt_actual - expected_stt)
        tolerance = tolerances.stt_tolerance
        
        if diff <= tolerance:
            score = 1.0
            message = f"STT validated: ₹{stt_actual:.2f}"
        else:
            score = max(0.5, 1.0 - (diff / (tolerance * 10)))
            message = f"STT variance: Expected ₹{expected_stt:.2f}, Actual ₹{stt_actual:.2f}"
        
        return RuleResult(
            rule_id="FT_004",
            tier=cls.TIER,
            score=score,
            weight=0.02,
            passed=score >= 0.7,
            message=message,
            raw_values={
                "stt_actual": stt_actual,
                "expected_stt": expected_stt,
                "diff": diff,
                "trade_type": trade_type
            }
        )
    
    @classmethod
    def ft_005_gst_validation(cls, trade: Dict[str, Any], 
                               cash: Dict[str, Any],
                               tolerances=None) -> RuleResult:
        """
        FT_005: GST Validation.
        
        GST is 18% of (Brokerage + Exchange/Transaction Charges).
        """
        tolerances = tolerances or DEFAULT_TOLERANCES
        
        gst_actual = float(trade.get("gst") or 0)
        
        if gst_actual == 0:
            return RuleResult(
                rule_id="FT_005",
                tier=cls.TIER,
                score=1.0,
                weight=0.02,
                passed=True,
                message="No GST on trade"
            )
        
        # Calculate expected GST
        brokerage = float(trade.get("brokerage") or 0)
        exchange_fee = float(trade.get("exchange_fee") or 0)
        base = brokerage + exchange_fee
        expected_gst = base * 0.18
        
        diff = abs(gst_actual - expected_gst)
        tolerance = tolerances.gst_tolerance
        
        if diff <= tolerance:
            score = 1.0
            message = f"GST validated: ₹{gst_actual:.2f}"
        else:
            score = max(0.5, 1.0 - (diff / (tolerance * 10)))
            message = f"GST variance: Expected ₹{expected_gst:.2f}, Actual ₹{gst_actual:.2f}"
        
        return RuleResult(
            rule_id="FT_005",
            tier=cls.TIER,
            score=score,
            weight=0.02,
            passed=score >= 0.7,
            message=message,
            raw_values={
                "gst_actual": gst_actual,
                "expected_gst": expected_gst,
                "base": base,
                "diff": diff
            }
        )

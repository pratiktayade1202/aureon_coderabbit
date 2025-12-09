# backend/rule_engine/domains/data_quality.py
"""
Data Quality Rules for Stress Testing

These rules detect specific data quality issues commonly found in financial data:
- Weekend/holiday trading
- Negative prices
- Missing identifiers
- Suspicious transactions (suspense withdrawals)
- NAV glitches (sudden spikes)
- Security identifier mismatches
"""

from typing import Any
from datetime import datetime, date
from ..core.rule import BaseRule
from ..core.result import RuleResult
from ..core.registry import RuleRegistry
from ..core.context import RuleContext


def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        s_val = str(value).replace(",", "").replace("$", "").replace("₹", "").replace("€", "")
        return float(s_val)
    except:
        return default


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _to_date(value: Any) -> date:
    """Convert various date formats to date object."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            # Try common formats
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(value[:10], fmt).date()
                except:
                    continue
        except:
            pass
    return None


# ==============================================================================
# SECTION 1: DATE VALIDATION RULES (DQ_001 - DQ_010)
# ==============================================================================

class DQ_001_WeekendTradingRule(BaseRule):
    """Detect trades executed on weekends (market closed)."""
    
    def __init__(self):
        super().__init__("DQ_001", "Weekend Trading Detection", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        trade_date = _to_date(_get(trade, "date"))
        
        if trade_date is None:
            return self.pass_rule("Date not available")
        
        # 5 = Saturday, 6 = Sunday
        weekday = trade_date.weekday()
        
        if weekday == 5:
            return self.fail(
                f"Weekend Trading: Trade dated {trade_date} is a SATURDAY (Market Closed)",
                "DATA_QUALITY"
            )
        elif weekday == 6:
            return self.fail(
                f"Weekend Trading: Trade dated {trade_date} is a SUNDAY (Market Closed)",
                "DATA_QUALITY"
            )
        
        return self.pass_rule(f"Valid trading day ({trade_date.strftime('%A')})")


class DQ_002_FutureDateRule(BaseRule):
    """Detect trades with future dates."""
    
    def __init__(self):
        super().__init__("DQ_002", "Future Date Detection", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        trade_date = _to_date(_get(trade, "date"))
        
        if trade_date is None:
            return self.pass_rule("Date not available")
        
        today = date.today()
        
        if trade_date > today:
            days_future = (trade_date - today).days
            return self.fail(
                f"Future Date: Trade dated {trade_date} is {days_future} days in the future",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Date is not in future")


class DQ_003_HolidayTradingRule(BaseRule):
    """Detect trades on known market holidays (placeholder for holiday calendar)."""
    
    def __init__(self):
        super().__init__("DQ_003", "Holiday Trading Detection", severity="MEDIUM")
        
        # Common Indian market holidays (sample - should be loaded from config)
        self.holidays = {
            date(2025, 1, 26),  # Republic Day
            date(2025, 3, 14),  # Holi
            date(2025, 8, 15),  # Independence Day
            date(2025, 10, 2),  # Gandhi Jayanti
            date(2025, 11, 1),  # Diwali
        }

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        trade_date = _to_date(_get(trade, "date"))
        
        if trade_date is None:
            return self.pass_rule("Date not available")
        
        if trade_date in self.holidays:
            return self.fail(
                f"Holiday Trading: Trade dated {trade_date} is a market holiday",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Not a holiday")


# ==============================================================================
# SECTION 2: PRICE VALIDATION RULES (DQ_011 - DQ_020)
# ==============================================================================

class DQ_011_NegativePriceRule(BaseRule):
    """Detect negative stock prices (impossible in equity markets)."""
    
    def __init__(self):
        super().__init__("DQ_011", "Negative Price Detection", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        price = _to_float(_get(trade, "price"))
        symbol = _to_str(_get(trade, "symbol")) or "UNKNOWN"
        
        if price < 0:
            return self.fail(
                f"Negative Price: {symbol} has price {price} (impossible for equity)",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Price is non-negative")


class DQ_012_ZeroPriceRule(BaseRule):
    """Detect zero prices on trades with quantity."""
    
    def __init__(self):
        super().__init__("DQ_012", "Zero Price Detection", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        price = _to_float(_get(trade, "price"))
        quantity = _to_float(_get(trade, "quantity"))
        symbol = _to_str(_get(trade, "symbol")) or "UNKNOWN"
        
        if quantity > 0 and price == 0:
            return self.fail(
                f"Zero Price: {symbol} trade with {quantity} units but zero price",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Price is valid")


class DQ_013_PriceOutlierRule(BaseRule):
    """Detect extreme price outliers (potential fat-finger errors)."""
    
    def __init__(self):
        super().__init__("DQ_013", "Price Outlier Detection", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        price = _to_float(_get(trade, "price"))
        symbol = _to_str(_get(trade, "symbol")) or "UNKNOWN"
        
        # Get reference price from context if available
        ref_prices = context.metadata.get("reference_prices", {})
        ref_price = _to_float(ref_prices.get(symbol, 0))
        
        if ref_price > 0 and price > 0:
            deviation = abs(price - ref_price) / ref_price
            
            # Flag if price deviates more than 50% from reference
            if deviation > 0.50:
                return self.fail(
                    f"Price Outlier: {symbol} price {price} deviates {deviation:.1%} from reference {ref_price}",
                    "DATA_QUALITY"
                )
        
        # Also flag suspiciously high prices (e.g., ₹50,000 for a typical stock)
        if price > 50000:
            return self.fail(
                f"Extreme Price: {symbol} has unusually high price {price} (potential data error)",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Price within expected range")


# ==============================================================================
# SECTION 3: IDENTIFIER VALIDATION RULES (DQ_021 - DQ_030)
# ==============================================================================

class DQ_021_MissingSymbolRule(BaseRule):
    """Detect transactions with missing symbol/ticker."""
    
    def __init__(self):
        super().__init__("DQ_021", "Missing Symbol Detection", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        symbol = _to_str(_get(trade, "symbol"))
        isin = _to_str(_get(trade, "isin"))
        quantity = _to_float(_get(trade, "quantity"))
        
        if quantity > 0 and not symbol and not isin:
            return self.fail(
                f"Missing Identifier: Trade has {quantity} units but no symbol or ISIN",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Identifier present")


class DQ_022_ISINFormatRule(BaseRule):
    """Validate ISIN format (12 characters, starts with country code)."""
    
    def __init__(self):
        super().__init__("DQ_022", "ISIN Format Validation", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        isin = _to_str(_get(trade, "isin"))
        
        if not isin:
            return self.pass_rule("No ISIN to validate")
        
        # ISIN should be 12 characters
        if len(isin) != 12:
            return self.fail(
                f"Invalid ISIN Length: {isin} has {len(isin)} characters (expected 12)",
                "DATA_QUALITY"
            )
        
        # Should start with 2-letter country code
        if not isin[:2].isalpha():
            return self.fail(
                f"Invalid ISIN Format: {isin} doesn't start with country code",
                "DATA_QUALITY"
            )
        
        return self.pass_rule(f"Valid ISIN format: {isin}")


class DQ_023_SecurityMismatchRule(BaseRule):
    """Detect NSDL vs CDSL security identifier mismatches (DVR shares vs ordinary)."""
    
    def __init__(self):
        super().__init__("DQ_023", "Security Type Mismatch", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        symbol = _to_str(_get(trade, "symbol"))
        description = _to_str(_get(trade, "description") or _get(trade, "narrative"))
        
        # Detect DVR (Differential Voting Rights) shares mixed with ordinary
        dvr_indicators = ["DVR", "DIFFERENTIAL VOTING", "-DVR"]
        
        is_dvr_symbol = any(ind in symbol for ind in dvr_indicators)
        is_dvr_desc = any(ind in description for ind in dvr_indicators)
        
        if is_dvr_symbol != is_dvr_desc and (is_dvr_symbol or is_dvr_desc):
            return self.fail(
                f"Security Mismatch: Symbol={symbol} but description suggests different share class",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Security type consistent")


# ==============================================================================
# SECTION 4: TRANSACTION VALIDATION RULES (DQ_031 - DQ_040)
# ==============================================================================

class DQ_031_SuspenseTransactionRule(BaseRule):
    """Detect suspicious 'SUSPENSE' transactions that need investigation."""
    
    def __init__(self):
        super().__init__("DQ_031", "Suspense Transaction Detection", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        description = _to_str(_get(cash, "description") or _get(cash, "narrative"))
        amount = _to_float(_get(cash, "amount"))
        
        suspense_keywords = ["SUSPENSE", "UNIDENTIFIED", "UNKNOWN", "PENDING INVESTIGATION", "TO BE IDENTIFIED"]
        
        for keyword in suspense_keywords:
            if keyword in description:
                return self.fail(
                    f"Suspense Transaction: '{description}' amount {amount} requires investigation",
                    "DATA_QUALITY"
                )
        
        return self.pass_rule("Not a suspense transaction")


class DQ_032_LargeWithdrawalRule(BaseRule):
    """Detect unusually large withdrawals that may indicate errors or fraud."""
    
    def __init__(self):
        super().__init__("DQ_032", "Large Withdrawal Detection", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        amount = _to_float(_get(cash, "amount"))
        description = _to_str(_get(cash, "description"))
        
        # Threshold for unusual withdrawal (configurable)
        threshold = _to_float(context.metadata.get("large_withdrawal_threshold", 500000))
        
        # Check for large debits (negative amounts)
        if amount < -threshold:
            return self.fail(
                f"Large Withdrawal: {abs(amount):,.2f} exceeds threshold ({threshold:,.2f}). Description: {description}",
                "RISK"
            )
        
        return self.pass_rule("Withdrawal within normal range")


class DQ_033_NegativeQuantityRule(BaseRule):
    """Detect negative quantities (should use side instead)."""
    
    def __init__(self):
        super().__init__("DQ_033", "Negative Quantity Detection", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        quantity = _to_float(_get(trade, "quantity"))
        symbol = _to_str(_get(trade, "symbol"))
        
        if quantity < 0:
            return self.fail(
                f"Negative Quantity: {symbol} has quantity {quantity} (should be positive with SELL side)",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("Quantity is non-negative")


# ==============================================================================
# SECTION 5: NAV & VALUATION RULES (DQ_041 - DQ_050)
# ==============================================================================

class DQ_041_NAVSpikeRule(BaseRule):
    """Detect sudden NAV spikes that may indicate data errors."""
    
    def __init__(self):
        super().__init__("DQ_041", "NAV Spike Detection", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        nav_value = _to_float(_get(trade, "nav_value") or _get(trade, "nav"))
        prev_nav = _to_float(context.metadata.get("previous_nav", 0))
        fund_name = _to_str(_get(trade, "fund_name") or _get(trade, "scheme_name"))
        
        if prev_nav > 0 and nav_value > 0:
            change_pct = (nav_value - prev_nav) / prev_nav
            
            # Flag changes > 10% in a single day (extremely rare for mutual funds)
            if abs(change_pct) > 0.10:
                direction = "SPIKE" if change_pct > 0 else "CRASH"
                return self.fail(
                    f"NAV {direction}: {fund_name} NAV changed {change_pct:.1%} ({prev_nav} -> {nav_value})",
                    "DATA_QUALITY"
                )
        
        # Also flag unrealistic NAV values
        if nav_value > 10000:
            return self.fail(
                f"Unrealistic NAV: {fund_name} NAV of {nav_value} exceeds typical range",
                "DATA_QUALITY"
            )
        
        return self.pass_rule("NAV within expected range")


class DQ_042_HoldingsQuantityMismatchRule(BaseRule):
    """Detect when holding quantities don't match expected (post corporate actions)."""
    
    def __init__(self):
        super().__init__("DQ_042", "Holdings Quantity Reconciliation", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        symbol = _to_str(_get(trade, "symbol"))
        quantity = _to_float(_get(trade, "quantity"))
        
        # Get expected quantity from trade records
        expected_qty = context.metadata.get("expected_quantities", {}).get(symbol, 0)
        
        if expected_qty > 0 and quantity != expected_qty:
            diff = quantity - expected_qty
            
            # Check if difference could be from a corporate action
            corp_actions = context.metadata.get("corporate_actions", [])
            has_corp_action = any(
                ca.get("symbol") == symbol 
                for ca in corp_actions
            )
            
            if has_corp_action:
                return self.fail(
                    f"Quantity Mismatch (Corp Action): {symbol} shows {quantity} but expected {expected_qty} (diff: {diff})",
                    "CORPORATE_ACTION"
                )
            else:
                return self.fail(
                    f"Quantity Mismatch: {symbol} shows {quantity} but expected {expected_qty} (diff: {diff})",
                    "DATA_QUALITY"
                )
        
        return self.pass_rule("Quantity matches expected")


# ==============================================================================
# REGISTRATION
# ==============================================================================

def register_data_quality_rules():
    r = RuleRegistry
    
    # Date Validation
    r.register(DQ_001_WeekendTradingRule())
    r.register(DQ_002_FutureDateRule())
    r.register(DQ_003_HolidayTradingRule())
    
    # Price Validation
    r.register(DQ_011_NegativePriceRule())
    r.register(DQ_012_ZeroPriceRule())
    r.register(DQ_013_PriceOutlierRule())
    
    # Identifier Validation
    r.register(DQ_021_MissingSymbolRule())
    r.register(DQ_022_ISINFormatRule())
    r.register(DQ_023_SecurityMismatchRule())
    
    # Transaction Validation
    r.register(DQ_031_SuspenseTransactionRule())
    r.register(DQ_032_LargeWithdrawalRule())
    r.register(DQ_033_NegativeQuantityRule())
    
    # NAV & Valuation
    r.register(DQ_041_NAVSpikeRule())
    r.register(DQ_042_HoldingsQuantityMismatchRule())
    
    print("✅ Registered 14 Data Quality Rules (DQ_001 - DQ_042)")


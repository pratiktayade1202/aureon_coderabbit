# backend/rule_engine/domains/positions.py

from typing import Any
from datetime import datetime
from difflib import SequenceMatcher

from ..core.rule import BaseRule
from ..core.result import RuleResult
from ..core.registry import RuleRegistry
from ..core.context import RuleContext

# ==============================================================================
# HELPER FUNCTIONS (Safe Accessors)
# ==============================================================================

def _get(obj: Any, attr: str, default: Any = None) -> Any:
    """Safe getter for dicts, objects, or Pydantic models."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)

def _to_float(value: Any, default: float = 0.0) -> float:
    """Safely convert to float, handling None and strings."""
    try:
        if value is None or value == "":
            return default
        # Remove currency symbols or commas if present in raw data
        s_val = str(value).replace(",", "").replace("$", "").replace("₹", "")
        return float(s_val)
    except Exception:
        return default

def _to_str(value: Any) -> str:
    """Safely convert to normalized uppercase string."""
    if value is None:
        return ""
    return str(value).strip().upper()

def _to_date(value: Any) -> Any:
    """Attempt to parse date or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    # Basic string parsing could be added here if needed, 
    # usually handled by ingestion layer
    return value

# ==============================================================================
# SECTION 1: CORE ECONOMIC RULES (POS_001 - POS_010)
# Fundamental identity and quantity checks.
# ==============================================================================

class POS_001_QuantityExactMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_001", "Position Quantity Exact Match", severity="CRITICAL")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_qty = _to_float(_get(internal, "quantity"))
        c_qty = _to_float(_get(custodian, "quantity"))
        diff = abs(i_qty - c_qty)
        
        # Strict tolerance for equity, slight flex for mutual fund units
        if diff <= 0.0001:
            return self.pass_rule(f"Quantity Match: {i_qty}")
        
        return self.fail(
            message=f"Quantity Mismatch: Internal={i_qty} vs Custodian={c_qty}",
            break_type="ECONOMIC",
            amount_diff=diff
        )

class POS_002_ISINIdentityRule(BaseRule):
    def __init__(self):
        super().__init__("POS_002", "ISIN Identity Match", severity="CRITICAL")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_isin = _to_str(_get(internal, "isin"))
        c_isin = _to_str(_get(custodian, "isin"))

        if not i_isin or not c_isin:
            return self.pass_rule("ISIN check skipped (missing data)")
        
        if i_isin == c_isin:
            return self.pass_rule(f"ISIN Match: {i_isin}")
        
        return self.fail(
            message=f"ISIN Mismatch: Int={i_isin} vs Cust={c_isin}",
            break_type="DATA"
        )

class POS_003_SymbolMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_003", "Symbol/Ticker Identity Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_sym = _to_str(_get(internal, "symbol"))
        c_sym = _to_str(_get(custodian, "symbol"))
        
        if i_sym == c_sym:
            return self.pass_rule(f"Symbol Match: {i_sym}")
        
        return self.fail(f"Symbol Mismatch: {i_sym} vs {c_sym}", "DATA")

class POS_004_MarketValueToleranceRule(BaseRule):
    def __init__(self):
        super().__init__("POS_004", "Market Value Tolerance Match", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_val = _to_float(_get(internal, "total_value"))
        c_val = _to_float(_get(custodian, "total_value"))
        
        diff = abs(i_val - c_val)
        
        # FIX: Fetch from context, default to 1% (0.01)
        tol_pct = _to_float(context.metadata.get("POS_004_tolerance_pct", 0.01))
        
        if i_val == 0:
            # FIX: Absolute tolerance for zero-value checks is also configurable
            tol_abs_zero = _to_float(context.metadata.get("POS_004_tolerance_abs_zero", 1.0))
            if diff < tol_abs_zero: return self.pass_rule("Zero Value Match")
            return self.fail(f"Value mismatch vs Zero: {c_val}", "VALUATION", diff)

        pct_diff = diff / abs(i_val)
        if pct_diff <= tol_pct:
            return self.pass_rule(f"Value match within {pct_diff:.4%} (Limit {tol_pct:.2%})")
            
        return self.fail(
            message=f"Valuation Discrepancy: {pct_diff:.2%} (Limit {tol_pct:.2%})",
            break_type="VALUATION",
            amount_diff=diff
        )

class POS_005_MissingISINRule(BaseRule):
    def __init__(self):
        super().__init__("POS_005", "Missing ISIN Check", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_isin = _to_str(_get(internal, "isin"))
        c_isin = _to_str(_get(custodian, "isin"))
        
        if not i_isin and not c_isin:
            return self.fail("ISIN missing on BOTH sides", "DATA_QUALITY")
        if not i_isin:
            return self.fail("Internal ISIN missing", "DATA_QUALITY")
        if not c_isin:
            return self.fail("Custodian ISIN missing", "DATA_QUALITY")
            
        return self.pass_rule("ISINs present")

class POS_006_NegativeQuantityRule(BaseRule):
    def __init__(self):
        super().__init__("POS_006", "Negative Quantity Sanity", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_qty = _to_float(_get(internal, "quantity"))
        c_qty = _to_float(_get(custodian, "quantity"))
        
        if i_qty < 0 or c_qty < 0:
            return self.fail(f"Negative Quantity Detected: Int={i_qty}, Cust={c_qty}", "DATA_QUALITY")
            
        return self.pass_rule("Quantities are positive")

class POS_007_ZeroPriceWarningRule(BaseRule):
    def __init__(self):
        super().__init__("POS_007", "Zero Price Warning", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_price = _to_float(_get(internal, "market_price"))
        c_price = _to_float(_get(custodian, "market_price"))
        
        if i_price == 0 or c_price == 0:
            return self.fail(f"Asset priced at zero: Int={i_price}, Cust={c_price}", "VALUATION")
            
        return self.pass_rule("Prices non-zero")

class POS_008_ValueCalculationCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_008", "Value Math Consistency (Qty * Price)", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Checks if Qty * Price roughly equals Reported Total Value."""
        qty = _to_float(_get(internal, "quantity"))
        price = _to_float(_get(internal, "market_price"))
        reported = _to_float(_get(internal, "total_value"))
        
        calc = qty * price
        diff = abs(calc - reported)
        
        if diff > 1.0: # 1.0 currency unit tolerance for rounding
            return self.fail(f"Internal Math Error: Qty*Price={calc} != Reported={reported}", "DATA_QUALITY", diff)
            
        return self.pass_rule("Internal value math consistent")

class POS_009_PriceSourceDiscrepancyRule(BaseRule):
    def __init__(self):
        super().__init__("POS_009", "Unit Price Divergence", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_price = _to_float(_get(internal, "market_price"))
        c_price = _to_float(_get(custodian, "market_price"))
        
        if i_price == 0: return self.pass_rule("Skip zero price")
        
        diff_pct = abs(i_price - c_price) / i_price
        if diff_pct > 0.02: # 2% tolerance for different feed sources
            return self.fail(f"Price Source Mismatch: {diff_pct:.2%} variance", "VALUATION")
            
        return self.pass_rule("Prices align")

class POS_010_StaleDateCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_010", "Stale Position Date", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        as_of = _to_date(context.metadata.get("as_of_date"))
        pos_date = _to_date(_get(internal, "date"))
        
        if as_of and pos_date:
            delta = (as_of - pos_date).days
            if delta > 3:
                return self.fail(f"Position date stale by {delta} days", "TIMING")
                
        return self.pass_rule("Date fresh")

# ==============================================================================
# SECTION 2: CUSTODY BUCKETS & SEGREGATION (POS_011 - POS_020)
# Handling pledged, free, locked, and missing records.
# ==============================================================================

class POS_011_InternalOnlyRule(BaseRule):
    def __init__(self):
        super().__init__("POS_011", "Internal Only Position", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        if custodian is None:
            return self.fail("Position exists internally but missing at Custodian", "ECONOMIC", _to_float(_get(internal, "total_value")))
        return self.pass_rule("Matched")

class POS_012_CustodianOnlyRule(BaseRule):
    def __init__(self):
        super().__init__("POS_012", "Custodian Only Position", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        # Note: In the standard flow, 'internal' drives the loop. 
        # This rule executes if we iterate custodian records.
        if internal is None:
            return self.fail("Position exists at Custodian but missing Internally", "ECONOMIC", _to_float(_get(custodian, "total_value")))
        return self.pass_rule("Matched")

class POS_013_ResidualDustRule(BaseRule):
    def __init__(self):
        super().__init__("POS_013", "Residual Dust Tolerance", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Matches if difference is tiny 'dust' (e.g. < 0.01 qty)."""
        i_qty = _to_float(_get(internal, "quantity"))
        c_qty = _to_float(_get(custodian, "quantity"))
        diff = abs(i_qty - c_qty)
        
        if diff > 0 and diff < 0.01:
            return self.pass_rule(f"Ignored Dust Difference: {diff}")
        if diff >= 0.01:
            return self.fail(f"Difference {diff} exceeds dust threshold", "ECONOMIC", diff)
        return self.pass_rule("Exact match")

class POS_014_InternalBucketSumRule(BaseRule):
    def __init__(self):
        super().__init__("POS_014", "Internal Bucket Check (Free+Locked)", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        total = _to_float(_get(internal, "quantity"))
        free = _to_float(_get(internal, "quantity_free"))
        locked = _to_float(_get(internal, "quantity_locked"))
        
        if (free + locked) != 0 and abs(total - (free + locked)) > 0.001:
            return self.fail(f"Internal Buckets Invalid: Free({free}) + Locked({locked}) != Total({total})", "DATA_QUALITY")
        return self.pass_rule("Buckets align")

class POS_015_CustodianBucketSumRule(BaseRule):
    def __init__(self):
        super().__init__("POS_015", "Custodian Bucket Check", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        total = _to_float(_get(custodian, "quantity"))
        free = _to_float(_get(custodian, "quantity_free"))
        locked = _to_float(_get(custodian, "quantity_locked"))
        
        if (free + locked) != 0 and abs(total - (free + locked)) > 0.001:
            return self.fail(f"Custodian Buckets Invalid: Free({free}) + Locked({locked}) != Total({total})", "DATA_QUALITY")
        return self.pass_rule("Buckets align")

class POS_016_FreeQuantityMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_016", "Free Quantity Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_free = _to_float(_get(internal, "quantity_free"))
        c_free = _to_float(_get(custodian, "quantity_free"))
        
        # Skip if buckets aren't used (both zero)
        if i_free == 0 and c_free == 0: return self.pass_rule("Skipped")
        
        diff = abs(i_free - c_free)
        if diff > 0.001:
            return self.fail(f"Free Qty Mismatch: {i_free} vs {c_free}", "ECONOMIC", diff)
        return self.pass_rule("Free Qty Matches")

class POS_017_LockedQuantityMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_017", "Locked/Pledged Quantity Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_locked = _to_float(_get(internal, "quantity_locked"))
        c_locked = _to_float(_get(custodian, "quantity_locked"))
        
        if i_locked == 0 and c_locked == 0: return self.pass_rule("Skipped")
        
        diff = abs(i_locked - c_locked)
        if diff > 0.001:
            return self.fail(f"Locked Qty Mismatch: {i_locked} vs {c_locked}", "ECONOMIC", diff)
        return self.pass_rule("Locked Qty Matches")

class POS_018_SourceValidationRule(BaseRule):
    def __init__(self):
        super().__init__("POS_018", "Source System Validation", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        src = _to_str(_get(custodian, "source_system"))
        if src and src not in ["NSDL", "CDSL", "DTCC", "EUROCLEAR", "INTERNAL"]:
            return self.fail(f"Unknown Custodian Source: {src}", "DATA_QUALITY")
        return self.pass_rule("Source Valid")

class POS_019_TenantIDAlignmentRule(BaseRule):
    def __init__(self):
        super().__init__("POS_019", "Tenant ID Safety Check", severity="CRITICAL")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_tid = _to_str(_get(internal, "tenant_id"))
        c_tid = _to_str(_get(custodian, "tenant_id"))
        
        if i_tid and c_tid and i_tid != c_tid:
            return self.fail(f"Cross-Tenant Data Leak! Int={i_tid} vs Cust={c_tid}", "SECURITY")
        return self.pass_rule("Tenant IDs match")

class POS_020_LargeDifferenceWarningRule(BaseRule):
    def __init__(self):
        super().__init__("POS_020", "Large Notional Break Warning", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_val = _to_float(_get(internal, "total_value"))
        c_val = _to_float(_get(custodian, "total_value"))
        diff = abs(i_val - c_val)
        
        # FIX: Configurable threshold
        threshold = _to_float(context.metadata.get("POS_020_large_break_threshold", 1_000_000.0))
        
        if diff > threshold:
            return self.fail(f"Massive Break Detected: >{threshold:,.0f} ({diff:,.2f})", "RISK", diff)
        return self.pass_rule("Break within safety net")

# ==============================================================================
# SECTION 3: COST BASIS, P&L & FX (POS_021 - POS_030)
# ==============================================================================

class POS_021_AvgCostSanityRule(BaseRule):
    def __init__(self):
        super().__init__("POS_021", "Average Cost Non-Negative", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        cost = _to_float(_get(internal, "avg_cost"))
        if cost < 0:
            return self.fail(f"Negative Average Cost: {cost}", "DATA_QUALITY")
        return self.pass_rule("Cost positive")

class POS_022_CurrencyConsistencyRule(BaseRule):
    def __init__(self):
        super().__init__("POS_022", "Currency Tag Match", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_ccy = _to_str(_get(internal, "currency"))
        c_ccy = _to_str(_get(custodian, "currency"))
        
        if i_ccy and c_ccy and i_ccy != c_ccy:
            return self.fail(f"Currency Mismatch: {i_ccy} vs {c_ccy}", "DATA_QUALITY")
        return self.pass_rule("Currency tags match")

class POS_023_FXNormalizedValueRule(BaseRule):
    def __init__(self):
        super().__init__("POS_023", "FX Normalized Value Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Gemini - 4.1 Multi-currency]
        Converts Custodian Value to Internal Currency using provided FX rates.
        """
        i_ccy = _to_str(_get(internal, "currency"))
        c_ccy = _to_str(_get(custodian, "currency"))
        
        if i_ccy == c_ccy: 
            return self.pass_rule("Skipped (Same Currency)")
        
        # FIX: Actual Logic
        fx_rates = context.metadata.get("fx_rates", {}) # Expecting dict: {'USD': 1.0, 'EUR': 1.05}
        
        # 1. Get rates to Base (assuming rates are relative to a common base or direct pairs)
        # Simplified: We assume rates are "To Base" or we look up "C_CCY/I_CCY"
        pair_key = f"{c_ccy}/{i_ccy}"
        rate = fx_rates.get(pair_key)
        
        if not rate:
            # Fallback: Try converting both to a common base (e.g. USD) found in context
            rate_c = fx_rates.get(c_ccy)
            rate_i = fx_rates.get(i_ccy)
            if rate_c and rate_i:
                rate = rate_c / rate_i
        
        if not rate:
            return self.fail(f"Missing FX Rate for {c_ccy}->{i_ccy}", "DATA_QUALITY")
            
        c_val = _to_float(_get(custodian, "total_value"))
        i_val = _to_float(_get(internal, "total_value"))
        
        c_val_converted = c_val * rate
        diff = abs(i_val - c_val_converted)
        
        # Use a slightly looser tolerance for FX calculations (0.5%)
        tol_pct = _to_float(context.metadata.get("POS_023_fx_tolerance_pct", 0.005))
        
        if i_val != 0 and (diff / abs(i_val)) > tol_pct:
             return self.fail(f"FX Value Mismatch: Int={i_val} vs Cust({c_ccy})={c_val} (@{rate:.4f})", "VALUATION", diff)
             
        return self.pass_rule(f"FX Match (@{rate:.4f})")

class POS_024_UnrealizedPnLCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_024", "Unrealized P&L Calculation Check", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        qty = _to_float(_get(internal, "quantity"))
        cost = _to_float(_get(internal, "avg_cost"))
        mkt = _to_float(_get(internal, "market_price"))
        reported_pnl = _to_float(_get(internal, "unrealized_pnl"))
        
        calc_pnl = (mkt - cost) * qty
        diff = abs(calc_pnl - reported_pnl)
        
        if diff > 1.0:
            return self.fail(f"PnL Calc Error: Calc={calc_pnl} vs Reported={reported_pnl}", "DATA_QUALITY")
        return self.pass_rule("PnL Math Valid")

class POS_025_ZeroCostBasisWarningRule(BaseRule):
    def __init__(self):
        super().__init__("POS_025", "Zero Cost Basis Warning", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        cost = _to_float(_get(internal, "avg_cost"))
        qty = _to_float(_get(internal, "quantity"))
        
        if qty > 0 and cost == 0:
            return self.fail("Position has Quantity but Zero Cost (Bonus issue?)", "DATA_QUALITY")
        return self.pass_rule("Cost present")

class POS_026_TotalCostMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_026", "Total Cost Basis Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Compares Total Cost (Book Cost) if provided by custodian."""
        i_cost = _to_float(_get(internal, "total_cost"))
        c_cost = _to_float(_get(custodian, "total_cost"))
        
        if i_cost == 0 or c_cost == 0: return self.pass_rule("Skipped")
        
        diff = abs(i_cost - c_cost)
        if diff > 5.0:
            return self.fail(f"Total Cost Mismatch: {i_cost} vs {c_cost}", "ECONOMIC", diff)
        return self.pass_rule("Total Cost Match")

class POS_027_MarketPriceAgeRule(BaseRule):
    def __init__(self):
        super().__init__("POS_027", "Internal Price Age Check", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        price_dt = _to_date(_get(internal, "price_date"))
        as_of = _to_date(context.metadata.get("as_of_date"))
        
        if price_dt and as_of:
            days = (as_of - price_dt).days
            if days > 5:
                return self.fail(f"Internal Price is {days} days old", "VALUATION")
        return self.pass_rule("Price recent")

class POS_028_ConcentrationRiskRule(BaseRule):
    def __init__(self):
        super().__init__("POS_028", "Single Asset Concentration Check", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Flags if a single position > 20% of portfolio (sanity check)."""
        pos_val = _to_float(_get(internal, "total_value"))
        port_val = _to_float(context.metadata.get("portfolio_total_value", 0))
        
        if port_val > 0:
            ratio = pos_val / port_val
            if ratio > 0.20:
                return self.fail(f"Concentration Alert: {ratio:.1%} of Portfolio", "RISK")
        return self.pass_rule("Concentration OK")

class POS_029_CurrencyMajorPairCheck(BaseRule):
    def __init__(self):
        super().__init__("POS_029", "Major Currency Validation", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        ccy = _to_str(_get(internal, "currency"))
        majors = ["USD", "EUR", "GBP", "JPY", "INR", "AUD", "CAD", "CHF", "CNY"]
        if ccy and ccy not in majors:
            return self.fail(f"Non-Major Currency: {ccy}", "DATA_QUALITY")
        return self.pass_rule("Major currency")

class POS_030_CostPerShareConsistencyRule(BaseRule):
    def __init__(self):
        super().__init__("POS_030", "Cost Per Share vs Total Cost", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        unit = _to_float(_get(internal, "avg_cost"))
        qty = _to_float(_get(internal, "quantity"))
        total = _to_float(_get(internal, "total_cost"))
        
        if unit > 0 and qty > 0 and total > 0:
            calc = unit * qty
            if abs(calc - total) > 1.0:
                return self.fail(f"Cost Math Mismatch: Unit*Qty={calc} vs Total={total}", "DATA_QUALITY")
        return self.pass_rule("Cost math valid")

# ==============================================================================
# SECTION 4: FIXED INCOME & ACCRUALS (POS_031 - POS_040)
# Rules specific to bonds, debt, and interest.
# ==============================================================================

class POS_031_AccruedInterestMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_031", "Accrued Interest Match", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_acc = _to_float(_get(internal, "accrued_interest"))
        c_acc = _to_float(_get(custodian, "accrued_interest"))
        
        diff = abs(i_acc - c_acc)
        if diff > 5.0:
            return self.fail(f"Accrued Int Mismatch: {i_acc} vs {c_acc}", "ECONOMIC", diff)
        return self.pass_rule("Accruals Match")

class POS_032_PendingSettlementMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_032", "Pending Settlement Quantity", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Matches 'Pending Delivery/Receipt' buckets."""
        i_pend = _to_float(_get(internal, "quantity_pending"))
        c_pend = _to_float(_get(custodian, "quantity_pending"))
        
        if i_pend != c_pend:
            return self.fail(f"Pending Settlement Mismatch: {i_pend} vs {c_pend}", "TIMING", abs(i_pend - c_pend))
        return self.pass_rule("Pending Match")

class POS_033_CouponRateCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_033", "Bond Coupon Rate Verify", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_rate = _to_float(_get(internal, "coupon_rate"))
        c_rate = _to_float(_get(custodian, "coupon_rate"))
        
        if i_rate == 0 and c_rate == 0: return self.pass_rule("Skipped")
        
        if i_rate != c_rate:
            return self.fail(f"Coupon Rate Mismatch: {i_rate} vs {c_rate}", "DATA_QUALITY")
        return self.pass_rule("Coupon Match")

class POS_034_MaturityDateCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_034", "Bond Maturity Date Verify", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_mat = _to_str(_get(internal, "maturity_date"))
        c_mat = _to_str(_get(custodian, "maturity_date"))
        
        if i_mat and c_mat and i_mat != c_mat:
            return self.fail(f"Maturity Date Mismatch: {i_mat} vs {c_mat}", "DATA_QUALITY")
        return self.pass_rule("Maturity Match")

class POS_035_PrincipalFactorCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_035", "Bond Principal Factor", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Checks amortizing bond factors."""
        i_fac = _to_float(_get(internal, "principal_factor", 1.0))
        c_fac = _to_float(_get(custodian, "principal_factor", 1.0))
        
        if i_fac != c_fac:
            return self.fail(f"Principal Factor Mismatch: {i_fac} vs {c_fac}", "DATA_QUALITY")
        return self.pass_rule("Factor Match")

class POS_036_CleanVsDirtyPriceRule(BaseRule):
    def __init__(self):
        super().__init__("POS_036", "Clean vs Dirty Price Sanity", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Heuristic: Dirty price should usually be >= Clean price (unless negative interest)."""
        clean = _to_float(_get(internal, "clean_price"))
        dirty = _to_float(_get(internal, "dirty_price"))
        
        if clean > 0 and dirty > 0 and clean > dirty:
            return self.fail(f"Dirty Price ({dirty}) < Clean Price ({clean}) - Unusual", "DATA_QUALITY")
        return self.pass_rule("Price logic OK")

class POS_037_BondFaceValueMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_037", "Bond Face Value / Unit Scaling", severity="CRITICAL")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_qty = _to_float(_get(internal, "face_value")) or _to_float(_get(internal, "quantity"))
        c_qty = _to_float(_get(custodian, "face_value")) or _to_float(_get(custodian, "quantity"))
        
        if i_qty == 0 or c_qty == 0: return self.pass_rule("Skipped (Zero Qty)")
        
        # FIX: Check exact match first
        if abs(i_qty - c_qty) < 0.001:
            return self.pass_rule("Exact Match")
            
        # FIX: Check for common Bond Scaling Factors (100, 1000)
        # Custodian reports Face (1,000,000), Internal reports Units (1,000)
        ratio = i_qty / c_qty
        
        if 99.9 < ratio < 100.1:
            return self.pass_rule("Matched with Factor 100 (Units vs Face)")
        if 0.009 < ratio < 0.011:
            return self.pass_rule("Matched with Factor 0.01 (Face vs Units)")
        if 999.9 < ratio < 1000.1:
            return self.pass_rule("Matched with Factor 1000")
        if 0.0009 < ratio < 0.0011:
            return self.pass_rule("Matched with Factor 0.001")

        return self.fail(
            message=f"Bond Qty Mismatch: {i_qty} vs {c_qty} (No scaling factor found)", 
            break_type="ECONOMIC", 
            amount_diff=abs(i_qty - c_qty)
        )

class POS_038_SecondaryID_CUSIPRule(BaseRule):
    def __init__(self):
        super().__init__("POS_038", "Secondary ID (CUSIP) Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_id = _to_str(_get(internal, "cusip"))
        c_id = _to_str(_get(custodian, "cusip"))
        
        if i_id and c_id and i_id != c_id:
            return self.fail(f"CUSIP Mismatch: {i_id} vs {c_id}", "DATA_QUALITY")
        return self.pass_rule("CUSIP Match")

class POS_039_SecondaryID_SEDOLRule(BaseRule):
    def __init__(self):
        super().__init__("POS_039", "Secondary ID (SEDOL) Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_id = _to_str(_get(internal, "sedol"))
        c_id = _to_str(_get(custodian, "sedol"))
        
        if i_id and c_id and i_id != c_id:
            return self.fail(f"SEDOL Mismatch: {i_id} vs {c_id}", "DATA_QUALITY")
        return self.pass_rule("SEDOL Match")

class POS_040_AssetClassMismatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_040", "Asset Class Classification", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_cls = _to_str(_get(internal, "asset_class"))
        c_cls = _to_str(_get(custodian, "asset_class"))
        
        if i_cls and c_cls and i_cls != c_cls:
            return self.fail(f"Asset Class Divergence: {i_cls} vs {c_cls}", "DATA_QUALITY")
        return self.pass_rule("Class Match")

# ==============================================================================
# SECTION 5: ADVANCED LOGIC, HEURISTICS & RISK (POS_041 - POS_052)
# ==============================================================================

class POS_041_DescriptionFuzzyMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_041", "Description Fuzzy Match Check", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_desc = _to_str(_get(internal, "description"))
        c_desc = _to_str(_get(custodian, "description"))
        
        if not i_desc or not c_desc: return self.pass_rule("Skip")
        
        ratio = SequenceMatcher(None, i_desc, c_desc).ratio()
        
        # FIX: Configurable threshold
        threshold = _to_float(context.metadata.get("POS_041_fuzzy_threshold", 0.6))
        
        if ratio < threshold: 
            return self.fail(f"Description Low Similarity ({ratio:.2f}): {i_desc} vs {c_desc}", "DATA_QUALITY")
        return self.pass_rule(f"Description Match {ratio:.2f}")

class POS_042_ScalingFactorErrorRule(BaseRule):
    def __init__(self):
        super().__init__("POS_042", "Scaling Factor Error (100x/1000x)", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Detects if one side is reporting in 'Thousands' vs 'Units'."""
        i_qty = _to_float(_get(internal, "quantity"))
        c_qty = _to_float(_get(custodian, "quantity"))
        
        if i_qty == 0 or c_qty == 0: return self.pass_rule("Skip")
        
        ratio = i_qty / c_qty
        if 99 < ratio < 101 or 0.009 < ratio < 0.011:
            return self.fail("Potential 100x Scaling Error Detected", "DATA_QUALITY")
        return self.pass_rule("Scaling OK")

class POS_043_PostSplitHeuristicRule(BaseRule):
    def __init__(self):
        super().__init__("POS_043", "Post-Split Quantity Heuristic", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Checks if discrepancy looks exactly like a 2:1 or 10:1 split."""
        i_qty = _to_float(_get(internal, "quantity"))
        c_qty = _to_float(_get(custodian, "quantity"))
        
        if c_qty == 0: return self.pass_rule("Skip")
        ratio = i_qty / c_qty
        
        if 1.99 < ratio < 2.01 or 0.49 < ratio < 0.51:
            return self.fail("Possible Unrecorded 2:1 Split", "CORPORATE_ACTION")
        return self.pass_rule("No Split Pattern")

class POS_044_HaircutValidationRule(BaseRule):
    def __init__(self):
        super().__init__("POS_044", "Collateral Haircut Validation", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        hc_pct = _to_float(_get(internal, "haircut_pct"))
        if hc_pct > 1.0:
            return self.fail(f"Haircut > 100%: {hc_pct}", "DATA_QUALITY")
        return self.pass_rule("Haircut Valid")

class POS_045_RestrictedHoldingCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_045", "Restricted Holding Flag", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        restricted = _get(internal, "is_restricted", False)
        if restricted:
            return self.pass_rule("Notice: Restricted Asset Held")
        return self.pass_rule("Asset Unrestricted")

class POS_046_DuplicateISINCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_046", "Duplicate ISIN in Source", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        # This requires context to know if duplicates exist, handled by Orchestrator typically
        # Here we check if metadata flags it
        if context.metadata.get("is_duplicate_record"):
            return self.fail("Duplicate ISIN found in source file", "DATA_QUALITY")
        return self.pass_rule("Unique")

class POS_047_NullRecordCheckRule(BaseRule):
    def __init__(self):
        super().__init__("POS_047", "Null Record Safety Check", severity="CRITICAL")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        if not internal and not custodian:
            return self.fail("Both records Null - Logic Error", "SYSTEM")
        return self.pass_rule("Records exist")

class POS_048_SignFlipErrorRule(BaseRule):
    def __init__(self):
        super().__init__("POS_048", "Sign Flip Error Detection", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_qty = _to_float(_get(internal, "quantity"))
        c_qty = _to_float(_get(custodian, "quantity"))
        
        if i_qty == -c_qty and i_qty != 0:
            return self.fail("Sign Flip Detected (Long vs Short)", "DATA_QUALITY")
        return self.pass_rule("Signs align")

class POS_049_MarketCodeMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_049", "Market Code (MIC) Match", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_mic = _to_str(_get(internal, "market_code"))
        c_mic = _to_str(_get(custodian, "market_code"))
        
        if i_mic and c_mic and i_mic != c_mic:
            return self.fail(f"Market Mismatch: {i_mic} vs {c_mic}", "DATA_QUALITY")
        return self.pass_rule("MIC Match")

class POS_050_SecurityTypeMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_050", "Security Type Match", severity="MEDIUM")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        i_type = _to_str(_get(internal, "security_type"))
        c_type = _to_str(_get(custodian, "security_type"))
        
        if i_type and c_type and i_type != c_type:
            return self.fail(f"Type Mismatch: {i_type} vs {c_type}", "DATA_QUALITY")
        return self.pass_rule("Type Match")

class POS_051_PriceCurrencyMatchRule(BaseRule):
    def __init__(self):
        super().__init__("POS_051", "Price Currency Alignment", severity="HIGH")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Checks if the price is quoted in the same currency (e.g. GBp vs GBP)."""
        i_p_ccy = _to_str(_get(internal, "price_currency"))
        c_p_ccy = _to_str(_get(custodian, "price_currency"))
        
        if i_p_ccy and c_p_ccy and i_p_ccy != c_p_ccy:
            return self.fail(f"Price Currency Mismatch: {i_p_ccy} vs {c_p_ccy}", "DATA_QUALITY")
        return self.pass_rule("Price Ccy Match")

class POS_052_SettlementDateLagRule(BaseRule):
    def __init__(self):
        super().__init__("POS_052", "Settlement Date Lag Check", severity="LOW")

    def execute(self, internal: Any, custodian: Any, context: RuleContext) -> RuleResult:
        """Checks if internal position date lags custodian date."""
        i_date = _to_date(_get(internal, "date"))
        c_date = _to_date(_get(custodian, "date"))
        
        if i_date and c_date and i_date != c_date:
            return self.fail(f"Report Date Mismatch: {i_date} vs {c_date}", "TIMING")
        return self.pass_rule("Dates align")

# ==============================================================================
# REGISTRATION (52 Rules)
# ==============================================================================

def register_position_rules():
    """Register all 50+ Position rules."""
    registry = RuleRegistry
    
    # 1. Core
    registry.register(POS_001_QuantityExactMatchRule())
    registry.register(POS_002_ISINIdentityRule())
    registry.register(POS_003_SymbolMatchRule())
    registry.register(POS_004_MarketValueToleranceRule())
    registry.register(POS_005_MissingISINRule())
    registry.register(POS_006_NegativeQuantityRule())
    registry.register(POS_007_ZeroPriceWarningRule())
    registry.register(POS_008_ValueCalculationCheckRule())
    registry.register(POS_009_PriceSourceDiscrepancyRule())
    registry.register(POS_010_StaleDateCheckRule())
    
    # 2. Custody
    registry.register(POS_011_InternalOnlyRule())
    registry.register(POS_012_CustodianOnlyRule())
    registry.register(POS_013_ResidualDustRule())
    registry.register(POS_014_InternalBucketSumRule())
    registry.register(POS_015_CustodianBucketSumRule())
    registry.register(POS_016_FreeQuantityMatchRule())
    registry.register(POS_017_LockedQuantityMatchRule())
    registry.register(POS_018_SourceValidationRule())
    registry.register(POS_019_TenantIDAlignmentRule())
    registry.register(POS_020_LargeDifferenceWarningRule())
    
    # 3. Cost/P&L
    registry.register(POS_021_AvgCostSanityRule())
    registry.register(POS_022_CurrencyConsistencyRule())
    registry.register(POS_023_FXNormalizedValueRule())
    registry.register(POS_024_UnrealizedPnLCheckRule())
    registry.register(POS_025_ZeroCostBasisWarningRule())
    registry.register(POS_026_TotalCostMatchRule())
    registry.register(POS_027_MarketPriceAgeRule())
    registry.register(POS_028_ConcentrationRiskRule())
    registry.register(POS_029_CurrencyMajorPairCheck())
    registry.register(POS_030_CostPerShareConsistencyRule())
    
    # 4. Fixed Income
    registry.register(POS_031_AccruedInterestMatchRule())
    registry.register(POS_032_PendingSettlementMatchRule())
    registry.register(POS_033_CouponRateCheckRule())
    registry.register(POS_034_MaturityDateCheckRule())
    registry.register(POS_035_PrincipalFactorCheckRule())
    registry.register(POS_036_CleanVsDirtyPriceRule())
    registry.register(POS_037_BondFaceValueMatchRule())
    registry.register(POS_038_SecondaryID_CUSIPRule())
    registry.register(POS_039_SecondaryID_SEDOLRule())
    registry.register(POS_040_AssetClassMismatchRule())
    
    # 5. Advanced
    registry.register(POS_041_DescriptionFuzzyMatchRule())
    registry.register(POS_042_ScalingFactorErrorRule())
    registry.register(POS_043_PostSplitHeuristicRule())
    registry.register(POS_044_HaircutValidationRule())
    registry.register(POS_045_RestrictedHoldingCheckRule())
    registry.register(POS_046_DuplicateISINCheckRule())
    registry.register(POS_047_NullRecordCheckRule())
    registry.register(POS_048_SignFlipErrorRule())
    registry.register(POS_049_MarketCodeMatchRule())
    registry.register(POS_050_SecurityTypeMatchRule())
    registry.register(POS_051_PriceCurrencyMatchRule())
    registry.register(POS_052_SettlementDateLagRule())

    print("✅ Registered 52 Position Rules (POS_001 - POS_052)")
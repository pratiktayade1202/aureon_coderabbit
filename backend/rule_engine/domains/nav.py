# backend/rule_engine/domains/nav.py

from typing import Any
from ..core.rule import BaseRule
from ..core.result import RuleResult
from ..core.registry import RuleRegistry
from ..core.context import RuleContext

# ==============================================================================
# HELPER FUNCTIONS (Safe Accessors)
# ==============================================================================

def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None: return default
    if isinstance(obj, dict): return obj.get(attr, default)
    return getattr(obj, attr, default)

def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None: return default
        s_val = str(value).replace(",", "").replace("$", "").replace("₹", "")
        return float(s_val)
    except:
        return default

def _to_str(value: Any) -> str:
    if value is None: return ""
    return str(value).strip().upper()

def _to_date(value: Any) -> Any:
    return value

# ==============================================================================
# SECTION 1: CORE NAV VALIDATION (NAV_001 - NAV_010)
# Top-level checks: NAV per Unit, Total AUM, and Unit Counts.
# ==============================================================================

class NAV_001_ExactNAVMatchRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_001", "NAV Per Unit Exact Match", severity="CRITICAL")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        The 'Gold Standard': Internal NAV must match Admin/Custodian NAV.
        NOW: Supports configurable precision (Crypto funds need 8 decimals, Equity needs 2-4).
        """
        i_nav = _to_float(_get(internal, "nav_per_unit"))
        a_nav = _to_float(_get(admin, "nav_per_unit"))
        
        diff = abs(i_nav - a_nav)
        
        # FIX: Get tolerance from metadata, default to 0.0001 (4 decimals)
        tolerance = _to_float(context.metadata.get("NAV_001_tolerance", 0.0001))
        
        if diff <= tolerance:
            return self.pass_rule(f"NAV Match: {i_nav}")
            
        return self.fail(
            message=f"NAV Mismatch: Int={i_nav} vs Admin={a_nav} (Diff {diff} > {tolerance})",
            break_type="VALUATION",
            amount_diff=diff
        )

class NAV_002_TotalAUMMatchRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_002", "Total AUM Match", severity="CRITICAL")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Kimi NAV_002, ChatGPT NAV_002]
        Validates Total Net Assets (AUM). Mismatch implies missing position/cash or fee.
        """
        i_aum = _to_float(_get(internal, "total_aum"))
        a_aum = _to_float(_get(admin, "total_aum"))
        
        diff = abs(i_aum - a_aum)
        
        # Configurable tolerance (e.g. 0.01%)
        tol_pct = _to_float(context.metadata.get("NAV_002_aum_tolerance_pct", 0.0001))
        
        if i_aum == 0: return self.pass_rule("Skipped (Zero AUM)")
        
        pct_diff = diff / i_aum
        if pct_diff <= tol_pct:
            return self.pass_rule(f"AUM Match: variance {pct_diff:.4%} within limit {tol_pct:.4%}")
            
        return self.fail(f"AUM Mismatch: {pct_diff:.4%} variance ({diff:,.2f})", "VALUATION", diff)

class NAV_003_UnitCountCheckRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_003", "Outstanding Units Verification", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        Validates the denominator (Total Units). Mismatch means subscription/redemption missing.
        """
        i_units = _to_float(_get(internal, "total_units"))
        a_units = _to_float(_get(admin, "total_units"))
        
        if i_units != a_units:
            return self.fail(f"Unit Count Error: Int={i_units} vs Admin={a_units}", "DATA_QUALITY", abs(i_units - a_units))
            
        return self.pass_rule("Units Match")

class NAV_004_NAVMathConsistencyRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_004", "NAV Math Consistency (AUM / Units)", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Perplexity NAV_VAL_002]
        Internal Sanity Check: Does AUM / Units = NAV?
        """
        aum = _to_float(_get(internal, "total_aum"))
        units = _to_float(_get(internal, "total_units"))
        reported_nav = _to_float(_get(internal, "nav_per_unit"))
        
        if units == 0: return self.pass_rule("Skipped (Zero Units)")
        
        calc_nav = aum / units
        diff = abs(calc_nav - reported_nav)
        
        if diff > 0.01:
            return self.fail(f"Math Logic Error: Calc {calc_nav:.4f} != Reported {reported_nav:.4f}", "DATA_QUALITY")
            
        return self.pass_rule("NAV Math Valid")

class NAV_005_CurrencyConsistencyRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_005", "Base Currency Check", severity="CRITICAL")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        i_ccy = _to_str(_get(internal, "currency"))
        a_ccy = _to_str(_get(admin, "currency"))
        
        # Hard check against fund config base currency
        base_ccy = _to_str(context.metadata.get("base_currency"))
        
        if base_ccy and i_ccy != base_ccy:
            return self.fail(f"Internal Currency {i_ccy} != Base {base_ccy}", "DATA_QUALITY")
            
        if i_ccy != a_ccy:
            return self.fail(f"Admin Currency Mismatch: {i_ccy} vs {a_ccy}", "DATA_QUALITY")
            
        return self.pass_rule("Currency Valid")

class NAV_006_NegativeNAVRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_006", "Negative NAV Sanity Check", severity="CRITICAL")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Kimi NAV_011]
        NAV per unit generally cannot be negative (unless liabilities > assets).
        """
        nav = _to_float(_get(internal, "nav_per_unit"))
        if nav < 0:
            return self.fail(f"Negative NAV Detected: {nav}", "RISK")
        return self.pass_rule("Positive NAV")

class NAV_007_LargeSwingWarningRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_007", "Large Daily NAV Swing", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Gemini 3.4.3]
        Fat-finger check: Did NAV jump > 5% in one day?
        """
        current = _to_float(_get(internal, "nav_per_unit"))
        prev = _to_float(_get(internal, "prev_nav_per_unit"))
        
        if prev == 0: return self.pass_rule("Skipped (No Prev NAV)")
        
        change_pct = abs((current - prev) / prev)
        threshold = _to_float(context.metadata.get("NAV_007_swing_threshold", 0.05)) # 5%
        
        if change_pct > threshold:
            return self.fail(f"Large NAV Swing: {change_pct:.2%} exceeds limit {threshold:.2%}", "RISK")
            
        return self.pass_rule("Stable NAV")

class NAV_008_SubscriptionRedemptionCheckRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_008", "CapTable vs Cash Flow Check", severity="CRITICAL")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Improvement #2]
        Validates: Net Unit Change * NAV ≈ Net Cash Flow from Subs/Reds.
        Prevents 'Phantom Units' created without cash, or cash received without units issued.
        """
        units_issued = _to_float(_get(internal, "units_issued"))
        units_redeemed = _to_float(_get(internal, "units_redeemed"))
        net_units = units_issued - units_redeemed
        
        cash_subs = _to_float(_get(internal, "cash_subscriptions"))
        cash_reds = _to_float(_get(internal, "cash_redemptions"))
        net_cash = cash_subs - cash_reds
        
        nav = _to_float(_get(internal, "nav_per_unit"))
        if nav == 0: return self.pass_rule("Skipped (Zero NAV)")
        
        # Expected Cash Impact = Units * NAV
        expected_cash = net_units * nav
        
        diff = abs(net_cash - expected_cash)
        
        # Tolerance for entry loads/exit fees (e.g. 1%)
        if diff > (abs(net_cash) * 0.01) + 10.0:
             return self.fail(f"CapTable Mismatch: Unit Value {expected_cash} != Cash Flow {net_cash}", "DATA_QUALITY", diff)
             
        return self.pass_rule("Subs/Reds Align")

# ==============================================================================
# SECTION 2: COMPONENT VALIDATION (NAV_011 - NAV_020)
# Rebuilding NAV from Parts (Assets + Cash - Fees).
# ==============================================================================

class NAV_011_AssetValueSumRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_011", "Total Asset Value Reconciliation", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Perplexity NAV_VAL_001]
        Checks if 'Positions Total' matches the Asset line in NAV breakdown.
        """
        # Sum of positions calculated in Orchestrator/Aggregation layer
        pos_sum = _to_float(_get(internal, "calculated_position_sum"))
        nav_assets = _to_float(_get(internal, "nav_assets_component"))
        
        diff = abs(pos_sum - nav_assets)
        if diff > 10.0:
            return self.fail(f"Asset Sum Mismatch: Positions={pos_sum} vs NAV_Line={nav_assets}", "VALUATION", diff)
            
        return self.pass_rule("Asset Component Matches")

class NAV_012_CashComponentCheckRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_012", "Cash Component Verification", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: ChatGPT NAV_003]
        Verifies that 'Total Cash' from Trade-Cash recon matches NAV Cash line.
        """
        ledger_cash = _to_float(_get(internal, "calculated_cash_balance"))
        nav_cash = _to_float(_get(internal, "nav_cash_component"))
        
        diff = abs(ledger_cash - nav_cash)
        if diff > 5.0:
            return self.fail(f"Cash Inclusion Error: Ledger={ledger_cash} vs NAV_Line={nav_cash}", "VALUATION", diff)
            
        return self.pass_rule("Cash Component Matches")

class NAV_013_UninvestedCashDragRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_013", "High Uninvested Cash (Cash Drag)", severity="LOW")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: ChatGPT NAV_007]
        Operational Warning: Is >20% of the fund sitting in cash?
        """
        aum = _to_float(_get(internal, "total_aum"))
        cash = _to_float(_get(internal, "nav_cash_component"))
        
        if aum == 0: return self.pass_rule("Skipped")
        
        ratio = cash / aum
        threshold = _to_float(context.metadata.get("NAV_013_cash_threshold", 0.20))
        
        if ratio > threshold:
            return self.fail(f"High Cash Drag: {ratio:.1%} of AUM is uninvested", "RISK")
            
        return self.pass_rule("Cash level normal")

class NAV_014_ManagementFeeAccrualRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_014", "Management Fee Accrual Check", severity="MEDIUM")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Perplexity NAV_VAL_007, ChatGPT NAV_006]
        Approximates daily fee accrual: (AUM * Rate) / 365.
        """
        aum = _to_float(_get(internal, "total_aum"))
        fee_rate = _to_float(context.metadata.get("management_fee_rate", 0.02)) # 2% default
        
        expected_daily = (aum * fee_rate) / 365.0
        actual_accrual = _to_float(_get(internal, "daily_fee_accrual"))
        
        diff = abs(expected_daily - actual_accrual)
        
        # 5% tolerance on the fee amount itself (for day count conventions)
        if expected_daily > 0 and (diff / expected_daily) > 0.05:
            return self.fail(f"Fee Accrual Suspicious: Exp={expected_daily:.2f} vs Act={actual_accrual:.2f}", "VALUATION")
            
        return self.pass_rule("Fee Accrual Reasonable")

class NAV_015_PerformanceFeeLogicRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_015", "Performance Fee / High Water Mark", severity="MEDIUM")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Kimi FEE_005, Perplexity NAV_VAL_008]
        Only allows Perf Fee if NAV > High Water Mark (HWM).
        """
        nav = _to_float(_get(internal, "nav_per_unit"))
        hwm = _to_float(context.metadata.get("high_water_mark", 0.0))
        perf_fee = _to_float(_get(internal, "perf_fee_accrual"))
        
        if nav < hwm and perf_fee > 0:
            return self.fail(f"Illegal Perf Fee: NAV {nav} < HWM {hwm}", "REGULATORY")
            
        return self.pass_rule("Perf Fee Logic Valid")

class NAV_016_InterestAccrualMatchRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_016", "Interest Accrual Reconciliation", severity="MEDIUM")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Improvement #3]
        Compares aggregated Bond Accrued Interest.
        """
        i_acc = _to_float(_get(internal, "total_accrued_interest"))
        a_acc = _to_float(_get(admin, "total_accrued_interest"))
        
        diff = abs(i_acc - a_acc)
        # Tolerance: 100 units (often due to day-count conventions 30/360 vs Act/Act)
        if diff > 100.0:
            return self.fail(f"Interest Accrual Mismatch: {i_acc} vs {a_acc}", "VALUATION", diff)
        return self.pass_rule("Interest Accrual OK")

class NAV_017_DividendAccrualMatchRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_017", "Dividend Accrual Reconciliation", severity="MEDIUM")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Improvement #3]
        Compares aggregated Dividend Receivables (ex-date passed, not paid).
        """
        i_div = _to_float(_get(internal, "dividend_receivable"))
        a_div = _to_float(_get(admin, "dividend_receivable"))
        
        if i_div != a_div:
             return self.fail(f"Dividend Rec. Mismatch: {i_div} vs {a_div}", "VALUATION", abs(i_div - a_div))
        return self.pass_rule("Dividend Accrual OK")
# ==============================================================================
# SECTION 3: PRICING & STALE DATA (NAV_021 - NAV_025)
# ==============================================================================

class NAV_021_StalePricingCheckRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_021", "Stale Asset Pricing in NAV", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Gemini 3.4.2, Kimi NAV_005]
        Checks if >X% of AUM is priced using old dates.
        """
        stale_pct = _to_float(_get(internal, "stale_asset_pct")) # Pre-calc from Positions
        limit = _to_float(context.metadata.get("NAV_021_stale_limit", 0.05))
        
        if stale_pct > limit:
            return self.fail(f"Stale Pricing Risk: {stale_pct:.1%} of AUM is stale", "VALUATION")
            
        return self.pass_rule("Pricing Fresh")

class NAV_022_FairValueAdjustmentCheckRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_022", "Manual Fair Value Override", severity="MEDIUM")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Perplexity NAV_VAL_009]
        Flags if manual 'Fair Value' overrides are present.
        """
        fv_flag = _get(internal, "has_manual_fair_value", False)
        if fv_flag:
            return self.fail("Notice: NAV includes Manual Fair Value Adjustments", "VALUATION_OVERRIDE")
        return self.pass_rule("Market Pricing Used")

class NAV_023_ZeroPriceAssetRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_023", "Assets Priced at Zero", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Kimi NAV_004]
        Prevents NAV calculation if material assets have 0.00 price.
        """
        zero_assets = _to_float(_get(internal, "count_zero_priced_assets"))
        if zero_assets > 0:
            return self.fail(f"Data Gap: {int(zero_assets)} assets have 0.00 price", "DATA_QUALITY")
        return self.pass_rule("All Assets Priced")

class NAV_024_AssetPriceVarianceRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_024", "Day-over-Day Price Jump", severity="HIGH")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Improvement #5]
        Checks if the portfolio's weighted average price moved suspiciously fast.
        (Alternatively, checks specific assets if passed in 'breakdown').
        """
        curr_price = _to_float(_get(internal, "weighted_avg_price"))
        prev_price = _to_float(_get(internal, "prev_weighted_avg_price"))
        
        if prev_price == 0: return self.pass_rule("Skipped")
        
        move_pct = abs(curr_price - prev_price) / prev_price
        limit = _to_float(context.metadata.get("NAV_024_price_jump_limit", 0.10)) # 10%
        
        if move_pct > limit:
            return self.fail(f"Market Movement Alert: Portfolio Price moved {move_pct:.1%}", "RISK")
        return self.pass_rule("Price Move Normal")

# ==============================================================================
# SECTION 4: MULTI-CURRENCY & HEDGING (NAV_031 - NAV_035)
# ==============================================================================

class NAV_031_FXImpactConsistencyRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_031", "FX P&L Consistency Check", severity="MEDIUM")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: ChatGPT NAV_004]
        Checks if NAV Change ≈ Asset P&L + FX P&L.
        """
        nav_chg = _to_float(_get(internal, "nav_change_amount"))
        asset_pnl = _to_float(_get(internal, "asset_pnl"))
        fx_pnl = _to_float(_get(internal, "fx_pnl"))
        
        calc_change = asset_pnl + fx_pnl
        diff = abs(nav_chg - calc_change)
        
        # Tolerance for fees/rounding
        if diff > 100.0:
            return self.fail(f"P&L Attribution Fail: NAV Chg {nav_chg} != (Asset {asset_pnl} + FX {fx_pnl})", "VALUATION")
            
        return self.pass_rule("Attribution Consistent")

class NAV_032_MultiCurrencyAUMRule(BaseRule):
    def __init__(self):
        super().__init__("NAV_032", "Multi-Currency AUM Rollup", severity="MEDIUM")

    def execute(self, internal: Any, admin: Any, context: RuleContext) -> RuleResult:
        """
        [Improvement #4]
        Real Implementation: Sum(Bucket_Value * FX_Rate) vs Reported AUM.
        """
        # Expecting a dict like {"USD": 1000, "EUR": 500} in 'currency_breakdown'
        buckets = _get(internal, "currency_breakdown", {})
        if not buckets: return self.pass_rule("Skipped (No Currency Breakdown)")
        
        fx_rates = context.metadata.get("fx_rates", {})
        base_ccy = context.metadata.get("base_currency", "USD")
        
        calc_aum = 0.0
        missing_rates = []
        
        for ccy, amount in buckets.items():
            if ccy == base_ccy:
                calc_aum += float(amount)
            else:
                rate = _to_float(fx_rates.get(f"{ccy}/{base_ccy}"))
                if not rate:
                    # Try inverse
                    inv = _to_float(fx_rates.get(f"{base_ccy}/{ccy}"))
                    if inv: rate = 1.0 / inv
                
                if rate:
                    calc_aum += float(amount) * rate
                else:
                    missing_rates.append(ccy)
        
        if missing_rates:
            return self.fail(f"Missing FX Rates for: {', '.join(missing_rates)}", "DATA_QUALITY")
            
        reported_aum = _to_float(_get(internal, "total_aum"))
        diff = abs(calc_aum - reported_aum)
        
        # 0.5% tolerance for FX triangulation noise
        if reported_aum > 0 and (diff / reported_aum) > 0.005:
             return self.fail(f"FX Rollup Mismatch: Calc {calc_aum:,.2f} != Reported {reported_aum:,.2f}", "VALUATION", diff)
             
        return self.pass_rule("Multi-Currency Rollup Valid")

# ==============================================================================
# REGISTRATION
# ==============================================================================

def register_nav_rules():
    r = RuleRegistry
    # Core
    r.register(NAV_001_ExactNAVMatchRule())
    r.register(NAV_002_TotalAUMMatchRule())
    r.register(NAV_003_UnitCountCheckRule())
    r.register(NAV_004_NAVMathConsistencyRule())
    r.register(NAV_005_CurrencyConsistencyRule())
    r.register(NAV_006_NegativeNAVRule())
    r.register(NAV_007_LargeSwingWarningRule())
    r.register(NAV_008_SubscriptionRedemptionCheckRule()) # NEW
    
    # Components
    r.register(NAV_011_AssetValueSumRule())
    r.register(NAV_012_CashComponentCheckRule())
    r.register(NAV_013_UninvestedCashDragRule())
    r.register(NAV_014_ManagementFeeAccrualRule())
    r.register(NAV_015_PerformanceFeeLogicRule())
    r.register(NAV_016_InterestAccrualMatchRule()) # NEW
    r.register(NAV_017_DividendAccrualMatchRule()) # NEW
    
    # Pricing
    r.register(NAV_021_StalePricingCheckRule())
    r.register(NAV_022_FairValueAdjustmentCheckRule())
    r.register(NAV_023_ZeroPriceAssetRule())
    r.register(NAV_024_AssetPriceVarianceRule()) # NEW
    
    # FX
    r.register(NAV_031_FXImpactConsistencyRule())
    r.register(NAV_032_MultiCurrencyAUMRule()) # UPDATED

    print("✅ Registered 22+ NAV Rules")
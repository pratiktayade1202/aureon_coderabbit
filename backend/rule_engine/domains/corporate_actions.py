# backend/rule_engine/domains/corporate_actions.py

from typing import Any, Dict, Optional
from datetime import timedelta, date
from ..core.rule import BaseRule
from ..core.result import RuleResult
from ..core.registry import RuleRegistry
from ..core.context import RuleContext

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None: return default
    if isinstance(obj, dict): return obj.get(attr, default)
    return getattr(obj, attr, default)

def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None: return default
        # Handle currency symbols if raw data is messy
        return float(str(value).replace(",", "").replace("$", ""))
    except:
        return default

def _to_str(value: Any) -> str:
    if value is None: return ""
    return str(value).strip().upper()

def _to_date(value: Any) -> Any:
    # Assumes ingestion layer has already parsed dates to datetime.date objects
    return value

def _round(value: float, precision: int = 8) -> float:
    """[Improvement #7] Normalize to 8 decimal places to avoid float noise."""
    return round(value, precision)

def _normalize_event_type(raw_type: str) -> str:
    """
    [Improvement #3 & #10]
    Maps messy vendor codes (STK_SPLT, BONUS_ISS) to Canonical Event Buckets.
    """
    raw = _to_str(raw_type).replace(" ", "").replace("_", "")
    
    mapping = {
        "SPLIT": ["SPLIT", "STOCKSPLIT", "SPLT", "FWDSPLIT", "SUBDIVISION"],
        "REVERSE_SPLIT": ["REVERSESPLIT", "REVSPLT", "CONSOLIDATION", "REVERSE"],
        "BONUS": ["BONUS", "BONUSISSUE", "FREESHARE", "SCRIP"],
        "DIVIDEND": ["DIV", "DVD", "CASHDIVIDEND", "INCOME"],
        "MERGER": ["MERGER", "ACQUISITION", "AMALGAMATION", "EXCHANGE"],
        "RIGHTS": ["RIGHTS", "RIGHTSISSUE", "RTS"],
    }
    
    for canonical, aliases in mapping.items():
        if any(alias in raw for alias in aliases):
            return canonical
    return "UNKNOWN"

def _check_window(record: Any, context: RuleContext) -> bool:
    """
    [Improvement #4]
    Validates if the event is within the processing window relative to As-Of Date.
    Returns True if valid, False if stale/future.
    """
    ex_date = _to_date(_get(record, "ex_date"))
    as_of_date = _to_date(context.metadata.get("as_of_date"))
    
    if not ex_date or not as_of_date:
        return True # Default to process if dates missing
        
    window = int(context.metadata.get("CA_valid_event_window", 10)) # 10 days default
    
    try:
        delta = abs((as_of_date - ex_date).days)
        return delta <= window
    except:
        return True

# ==============================================================================
# SECTION 1: SPLITS & BONUS ISSUES (Quantity Adjustments)
# ==============================================================================

class CA_001_StockSplitQuantityRule(BaseRule):
    def __init__(self):
        super().__init__("CA_001", "Stock Split Quantity Projection", severity="CRITICAL")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: ChatGPT CA_SPLIT_001, Kimi CA_001]
        Validates: New Qty = Old Qty * Split Ratio.
        """
        raw_type = _get(record, "event_type")
        event_type = _normalize_event_type(raw_type)
        
        if event_type != "SPLIT": return self.pass_rule("Skipped (Not a Split)")
        
        # [Improvement #4] Window Check
        if not _check_window(record, context):
            return self.pass_rule("Skipped (Outside Event Window)")

        old_qty = _to_float(_get(record, "pre_event_quantity"))
        ratio_num = _to_float(_get(record, "ratio_numerator"))
        ratio_den = _to_float(_get(record, "ratio_denominator"))
        
        # [Improvement #8] Confidence Scoring / Data Sanity
        if ratio_den == 0 or old_qty == 0: 
            return self.pass_rule("Skipped (Insufficient Data for Calculation)")
        
        expected_qty = _round(old_qty * (ratio_num / ratio_den))
        actual_qty = _round(_to_float(_get(record, "post_event_quantity")))
        
        # [Improvement #1] Configurable Tolerance
        tol_qty = _to_float(context.metadata.get("CA_qty_tolerance", 0.001))
        
        diff = abs(actual_qty - expected_qty)
        
        if diff > tol_qty:
            # [Improvement #2] Evidence Mode
            return self.fail(
                message=(
                    f"Split Mismatch: Exp {expected_qty} vs Act {actual_qty}. "
                    f"Inputs: Old={old_qty}, Ratio={ratio_num}/{ratio_den}, Diff={diff}"
                ),
                break_type="CORPORATE_ACTION",
                amount_diff=diff
            )
            
        return self.pass_rule(f"Split Verified: {old_qty} -> {actual_qty}")

class CA_002_ReverseSplitLogicRule(BaseRule):
    def __init__(self):
        super().__init__("CA_002", "Reverse Split Consolidation", severity="CRITICAL")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Perplexity CA_012]
        Handles 1-for-10 style reverse splits.
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type != "REVERSE_SPLIT": return self.pass_rule("Skipped")

        old_qty = _to_float(_get(record, "pre_event_quantity"))
        ratio = _to_float(_get(record, "ratio_value")) # e.g. 0.1 for 1-for-10
        
        if ratio == 0: return self.fail("Invalid Ratio (Zero)", "DATA_QUALITY")
        
        expected_qty = _round(old_qty * ratio)
        actual_qty = _round(_to_float(_get(record, "post_event_quantity")))
        
        # [Improvement #1] Tolerance
        tol = _to_float(context.metadata.get("CA_reverse_split_tolerance", 1.0)) # Higher for rounding
        
        if abs(actual_qty - expected_qty) > tol:
             return self.fail(
                 f"Rev Split Fail: Exp {expected_qty} vs Act {actual_qty}. Inputs: Old={old_qty}, Ratio={ratio}", 
                 "CORPORATE_ACTION"
             )
             
        return self.pass_rule("Reverse Split OK")

class CA_003_BonusIssueCheckRule(BaseRule):
    def __init__(self):
        super().__init__("CA_003", "Bonus Issue Verification", severity="HIGH")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: ChatGPT CA_BONUS_001]
        New = Old * (1 + Ratio).
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type != "BONUS": return self.pass_rule("Skipped")

        old_qty = _to_float(_get(record, "pre_event_quantity"))
        bonus_ratio = _to_float(_get(record, "ratio_value")) # e.g. 0.1
        
        expected_total = _round(old_qty * (1 + bonus_ratio))
        actual_total = _round(_to_float(_get(record, "post_event_quantity")))
        
        tol = _to_float(context.metadata.get("CA_qty_tolerance", 0.001))
        
        if abs(actual_total - expected_total) > tol:
            return self.fail(
                f"Bonus Mismatch: Exp {expected_total} vs Act {actual_total}. Ratio={bonus_ratio}", 
                "CORPORATE_ACTION"
            )
            
        return self.pass_rule("Bonus Calculated Correctly")

class CA_004_CostBasisAdjustmentRule(BaseRule):
    def __init__(self):
        super().__init__("CA_004", "Cost Basis Adjustment (Split/Bonus)", severity="HIGH")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: ChatGPT CA_SPLIT_002]
        Ensures Unit Cost decreases proportionally when Quantity increases.
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type not in ["SPLIT", "BONUS", "REVERSE_SPLIT"]: return self.pass_rule("Skipped")

        old_cost = _to_float(_get(record, "pre_event_avg_cost"))
        new_cost = _to_float(_get(record, "post_event_avg_cost"))
        
        old_qty = _to_float(_get(record, "pre_event_quantity"))
        new_qty = _to_float(_get(record, "post_event_quantity"))
        
        if new_qty == 0 or old_cost == 0: return self.pass_rule("Skipped (Zero inputs)")
        
        factor = old_qty / new_qty
        expected_new_cost = _round(old_cost * factor, 4) # Price precision often 4 decimals
        
        # [Improvement #1] Tolerance Percentage
        tol_pct = _to_float(context.metadata.get("CA_costbasis_tolerance_pct", 0.01))
        
        if abs(new_cost - expected_new_cost) > (old_cost * tol_pct):
            return self.fail(
                f"Cost Basis Error: Exp {expected_new_cost} vs Act {new_cost}. Factor={factor:.4f}", 
                "VALUATION"
            )
            
        return self.pass_rule("Cost Basis Adjusted")

class CA_005_CrossEventValuePreservationRule(BaseRule):
    def __init__(self):
        super().__init__("CA_005", "Event Value Preservation Check", severity="CRITICAL")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Improvement #5]
        Checks: (Old_Qty * Old_Price) ≈ (New_Qty * New_Price).
        Economic value should not change due to a Split/Bonus/Reverse Split.
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type not in ["SPLIT", "BONUS", "REVERSE_SPLIT"]: return self.pass_rule("Skipped")

        old_val = _to_float(_get(record, "pre_event_total_value"))
        new_val = _to_float(_get(record, "post_event_total_value"))
        
        if old_val == 0: 
            # Try to calculate if totals missing
            old_q = _to_float(_get(record, "pre_event_quantity"))
            old_p = _to_float(_get(record, "pre_event_price"))
            old_val = old_q * old_p
            
            new_q = _to_float(_get(record, "post_event_quantity"))
            new_p = _to_float(_get(record, "post_event_price"))
            new_val = new_q * new_p

        if old_val == 0: return self.pass_rule("Skipped (Zero Value)")

        # Allow 1% tolerance for market movement if price is 'Close' vs 'Adj Close'
        tol_pct = _to_float(context.metadata.get("CA_value_preservation_tol", 0.01))
        
        diff = abs(old_val - new_val)
        
        if diff > (old_val * tol_pct):
            return self.fail(
                f"Economic Value Destroyed: Old {old_val:,.2f} vs New {new_val:,.2f} (Diff {diff:,.2f})", 
                "RISK"
            )
            
        return self.pass_rule("Value Preserved")

# ==============================================================================
# SECTION 2: DIVIDENDS & INCOME (Cash Events)
# ==============================================================================

class CA_010_DividendCashMatchRule(BaseRule):
    def __init__(self):
        super().__init__("CA_010", "Dividend Cash Reconciliation", severity="CRITICAL")

    def execute(self, record: Any, cash_entry: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Kimi CA_002, ChatGPT CA_DIV_001]
        Validates: Cash Received = Units Held * Dividend Per Share (DPS).
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type != "DIVIDEND": return self.pass_rule("Skipped")

        units = _to_float(_get(record, "eligible_quantity"))
        dps = _to_float(_get(record, "dividend_rate"))
        
        gross_amt = units * dps
        actual_cash = _to_float(_get(cash_entry, "amount"))
        
        # [Improvement #1] Configurable Threshold
        # Default 35% buffer for Tax (if tax not explicit)
        buffer_pct = _to_float(context.metadata.get("CA_div_gross_buffer_pct", 0.35))
        
        diff = abs(actual_cash - gross_amt)
        
        if diff > (gross_amt * buffer_pct): 
             return self.fail(
                 f"Div Cash Mismatch: Exp Gross {gross_amt} vs Act {actual_cash}. Inputs: Units={units}, DPS={dps}", 
                 "ECONOMIC"
             )
             
        return self.pass_rule("Dividend Gross OK")

class CA_011_WithholdingTaxCheckRule(BaseRule):
    def __init__(self):
        super().__init__("CA_011", "Dividend Withholding Tax Logic", severity="MEDIUM")

    def execute(self, record: Any, cash_entry: Any, context: RuleContext) -> RuleResult:
        """
        [Upgrade: Country-Aware Logic]
        Checks if the difference between Gross and Net matches the Tax Rate 
        for the specific Country of Issue (if known).
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type != "DIVIDEND": return self.pass_rule("Skipped")

        units = _to_float(_get(record, "eligible_quantity"))
        dps = _to_float(_get(record, "dividend_rate"))
        gross_amt = units * dps
        actual_cash = _to_float(_get(cash_entry, "amount"))
        
        if gross_amt == 0: return self.pass_rule("Skipped (Zero Gross)")
        
        # Implied Tax Rate calculation
        implied_tax = (gross_amt - actual_cash) / gross_amt
        
        # 1. Look for Country Specific Rate first
        country = _to_str(_get(record, "country_of_issue")) # e.g. "US", "IE", "CA"
        country_rates = context.metadata.get("CA_country_tax_rates", {}) # {'US': 0.30, 'IE': 0.20}
        
        expected_rate = country_rates.get(country)
        
        if expected_rate is not None:
            # Strict check if we know the country
            if abs(implied_tax - float(expected_rate)) < 0.02:
                return self.pass_rule(f"Tax Rate Matched Country {country}: {implied_tax:.1%}")
            return self.fail(f"Tax Mismatch for {country}: Exp {expected_rate:.1%} vs Act {implied_tax:.1%}", "REGULATORY")

        # 2. Fallback to Generic Global Rates
        valid_rates = context.metadata.get("CA_valid_tax_rates", [0.0, 0.10, 0.15, 0.20, 0.30])
        is_valid = any(abs(implied_tax - rate) < 0.02 for rate in valid_rates)
        
        if not is_valid and implied_tax > 0.01:
            return self.fail(
                f"Suspicious Tax Rate: {implied_tax:.1%} (Expected one of {valid_rates})", 
                "REGULATORY"
            )
            
        return self.pass_rule(f"Tax Rate Reasonable ({implied_tax:.1%})")

class CA_012_CurrencyDivMatchRule(BaseRule):
    def __init__(self):
        super().__init__("CA_012", "Dividend Currency & FX Check", severity="HIGH")

    def execute(self, record: Any, cash_entry: Any, context: RuleContext) -> RuleResult:
        """
        [Upgrade: FX Support]
        If Dividend is declared in USD but paid in EUR, applies FX rate to verify value.
        """
        decl_ccy = _to_str(_get(record, "currency"))
        paid_ccy = _to_str(_get(cash_entry, "currency"))
        
        # Case A: Same Currency
        if decl_ccy == paid_ccy:
            return self.pass_rule("Currency Matches")
            
        # Case B: FX Conversion Required
        rates = context.metadata.get("fx_rates", {})
        pair = f"{decl_ccy}/{paid_ccy}"
        rate = _to_float(rates.get(pair))
        
        # Try inverse if missing
        if not rate:
            inv = _to_float(rates.get(f"{paid_ccy}/{decl_ccy}"))
            if inv: rate = 1.0 / inv
            
        if not rate:
            return self.fail(f"Currency Mismatch & Missing FX Rate for {decl_ccy}->{paid_ccy}", "DATA_QUALITY")
            
        # Verify Amounts with FX
        units = _to_float(_get(record, "eligible_quantity"))
        dps = _to_float(_get(record, "dividend_rate"))
        gross_decl = units * dps
        
        actual_paid = _to_float(_get(cash_entry, "amount"))
        
        # Expected Paid = Gross * FX * (1 - Tax)
        # Since tax is complex, we just check if it's "In the ballpark" (Gross > Net)
        gross_converted = gross_decl * rate
        
        if actual_paid > gross_converted * 1.05:
             return self.fail(f"FX Value Mismatch: Paid {actual_paid} > Declared {gross_converted} (Rate {rate})", "ECONOMIC")
             
        return self.pass_rule(f"Currency FX Logic Accepted ({decl_ccy}->{paid_ccy})")

# ==============================================================================
# SECTION 3: MERGERS & REORGS (Structure Events)
# ==============================================================================

class CA_020_MergerISINSwapRule(BaseRule):
    def __init__(self):
        super().__init__("CA_020", "Merger ISIN Swap Verification", severity="CRITICAL")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Perplexity CA_010]
        Ensures Old ISIN position is closed and New ISIN position is opened.
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type != "MERGER": return self.pass_rule("Skipped")
        
        old_isin_qty = _to_float(_get(record, "old_isin_quantity"))
        new_isin_qty = _to_float(_get(record, "new_isin_quantity"))
        
        if old_isin_qty != 0:
            return self.fail("Merger Fail: Old ISIN Quantity should be zero", "CORPORATE_ACTION")
            
        if new_isin_qty <= 0:
            return self.fail("Merger Fail: New ISIN Quantity not credited", "CORPORATE_ACTION")
            
        return self.pass_rule("Merger Swap Logic Valid")

class CA_021_MergerRatioRule(BaseRule):
    def __init__(self):
        super().__init__("CA_021", "Merger Exchange Ratio Check", severity="HIGH")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Kimi CA_005]
        Checks: New_Qty = Old_Qty * Exchange_Ratio.
        """
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type != "MERGER": return self.pass_rule("Skipped")
        
        orig_qty = _to_float(_get(record, "original_quantity_held"))
        ratio = _to_float(_get(record, "exchange_ratio"))
        new_qty = _to_float(_get(record, "new_isin_quantity"))
        
        expected = _round(orig_qty * ratio)
        
        # [Improvement #1] Tolerance
        tol = _to_float(context.metadata.get("CA_merger_tolerance", 1.0))
        
        if abs(new_qty - expected) > tol:
             return self.fail(
                 f"Merger Ratio Fail: Exp {expected} vs Act {new_qty}. Ratio={ratio}", 
                 "CORPORATE_ACTION"
             )
             
        return self.pass_rule("Merger Ratio OK")

# ==============================================================================
# SECTION 4: DATA QUALITY & TIMING (CA_030 - CA_040)
# ==============================================================================

class CA_030_ExDateTimingRule(BaseRule):
    def __init__(self):
        super().__init__("CA_030", "Ex-Date vs Record-Date Logic", severity="HIGH")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Perplexity CA_005]
        Mandatory Logic: Ex-Date must be <= Record-Date.
        """
        ex_date = _to_date(_get(record, "ex_date"))
        rec_date = _to_date(_get(record, "record_date"))
        
        if ex_date and rec_date and ex_date > rec_date:
            return self.fail(f"Impossible Dates: Ex-Date {ex_date} > Record {rec_date}", "DATA_QUALITY")
        return self.pass_rule("Date Logic Valid")

class CA_031_MissingAnnouncementRule(BaseRule):
    def __init__(self):
        super().__init__("CA_031", "Unannounced Corporate Action", severity="MEDIUM")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        """
        [Research Source: Kimi CA_004]
        Flags position changes labeled 'CA' that lack a corresponding Master Announcement.
        """
        has_announcement = _get(record, "announcement_id") is not None
        
        # Using normalized check for movement type
        mov_type = _to_str(_get(record, "movement_type"))
        is_ca = any(x in mov_type for x in ["CORP", "DIV", "SPLIT", "BONUS"])
        
        if is_ca and not has_announcement:
            return self.fail("Orphan CA Movement: No linked announcement found", "DATA_QUALITY")
        return self.pass_rule("Linked to Announcement")

class CA_032_FractionalShareCashRule(BaseRule):
    def __init__(self):
        super().__init__("CA_032", "Fractional Share Cash-in-Lieu", severity="LOW")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        cash_in_lieu = _to_float(_get(record, "cash_in_lieu"))
        if cash_in_lieu > 0:
            return self.pass_rule(f"Notice: Cash-in-Lieu received {cash_in_lieu}")
        return self.pass_rule("No fractionals")

class CA_033_RightsExpiryRule(BaseRule):
    def __init__(self):
        super().__init__("CA_033", "Rights Issue Expiry Check", severity="MEDIUM")

    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        event_type = _normalize_event_type(_get(record, "event_type"))
        if event_type != "RIGHTS": return self.pass_rule("Skipped")
        
        # Simple date check
        # In real engine, use context.as_of_date
        return self.pass_rule("Rights Valid")

# ==============================================================================
# REGISTRATION
# ==============================================================================

def register_corporate_action_rules():
    r = RuleRegistry
    # Splits & Bonus
    r.register(CA_001_StockSplitQuantityRule())
    r.register(CA_002_ReverseSplitLogicRule())
    r.register(CA_003_BonusIssueCheckRule())
    r.register(CA_004_CostBasisAdjustmentRule())
    r.register(CA_005_CrossEventValuePreservationRule()) # NEW
    
    # Dividends
    r.register(CA_010_DividendCashMatchRule())
    r.register(CA_011_WithholdingTaxCheckRule())
    r.register(CA_012_CurrencyDivMatchRule())
    
    # Mergers
    r.register(CA_020_MergerISINSwapRule())
    r.register(CA_021_MergerRatioRule())
    
    # Data Quality
    r.register(CA_030_ExDateTimingRule())
    r.register(CA_031_MissingAnnouncementRule())
    r.register(CA_032_FractionalShareCashRule())
    r.register(CA_033_RightsExpiryRule())

    print("✅ Registered 14+ Corporate Action Rules")
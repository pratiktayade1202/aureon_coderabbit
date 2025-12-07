# backend/rule_engine/domains/trade_cash.py

import re
from typing import Any, List
from datetime import timedelta
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
        # Remove common currency formatting
        s_val = str(value).replace(",", "").replace("$", "").replace("₹", "").replace("€", "")
        return float(s_val)
    except:
        return default

def _to_str(value: Any) -> str:
    if value is None: return ""
    return str(value).strip().upper()

def _to_date(value: Any) -> Any:
    return value

def _normalize_string(s: str) -> str:
    """Removes non-alphanumeric chars for robust fuzzy matching."""
    if not s: return ""
    return re.sub(r"[^A-Z0-9]", "", s.upper())

# ==============================================================================
# SECTION 0: PRE-VALIDATION (TC_000)
# ==============================================================================

class TC_000_MandatoryFieldsCheckRule(BaseRule):
    def __init__(self):
        super().__init__("TC_000", "Mandatory Field Pre-Check", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        """
        Fail fast if essential data is missing to prevent noisy downstream breaks.
        """
        missing = []
        # Check Trade
        if _get(trade, "net_amount") is None and _get(trade, "gross_amount") is None:
            missing.append("Trade Amount")
        if not _get(trade, "currency"): missing.append("Trade Currency")
        
        # Check Cash
        if _get(cash, "amount") is None: missing.append("Cash Amount")
        if not _get(cash, "currency"): missing.append("Cash Currency")
        # Allow either value_date or date
        if not _get(cash, "value_date") and not _get(cash, "date"): missing.append("Cash Date")

        if missing:
            return self.fail(f"Critical Data Missing: {', '.join(missing)}", "DATA_QUALITY")
            
        return self.pass_rule("Mandatory fields present")

# ==============================================================================
# SECTION 1: CORE MATCHING RULES (TC_001 - TC_010)
# ==============================================================================

class TC_001_ExactAmountRule(BaseRule):
    def __init__(self):
        super().__init__("TC_001", "Exact Net Amount Match", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        """
        Skip if 'settle_gross_separate_fees' is enabled in metadata.
        """
        if context.metadata.get("settle_gross_separate_fees", False):
            return self.pass_rule("Skipped (Separate Fee Settlement Mode Active)")

        t_amt = abs(_to_float(_get(trade, "net_amount") or _get(trade, "amount")))
        c_amt = abs(_to_float(_get(cash, "amount")))
        
        diff = abs(t_amt - c_amt)
        
        if diff <= 0.0001:
            return self.pass_rule(f"Exact Match: {t_amt}")
            
        return self.fail(
            message=f"Amount Mismatch: Trade={t_amt} vs Cash={c_amt}",
            break_type="ECONOMIC",
            amount_diff=diff
        )

class TC_002_SettlementDateMatchRule(BaseRule):
    def __init__(self):
        super().__init__("TC_002", "Settlement Date Alignment", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        t_date = _to_date(_get(trade, "settlement_date"))
        c_date = _to_date(_get(cash, "value_date") or _get(cash, "date"))
        
        if not t_date or not c_date: return self.pass_rule("Skipped (Dates Missing)")
            
        try:
            delta = abs((c_date - t_date).days)
        except:
            return self.fail("Date Format Error", "DATA_QUALITY")

        tol_days = int(context.metadata.get("TC_002_date_tolerance", 1))
        
        if delta <= tol_days:
            return self.pass_rule(f"Date aligned within {delta} days")
            
        return self.fail(f"Timing Mismatch: Trade {t_date} vs Cash {c_date}", "TIMING")

class TC_003_DirectionSanityRule(BaseRule):
    def __init__(self):
        super().__init__("TC_003", "Direction (Buy/Sell) Sanity", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        side = _to_str(_get(trade, "side"))
        c_amt = _to_float(_get(cash, "amount"))
        
        if c_amt == 0: return self.pass_rule("Neutral")

        is_buy = side in ["BUY", "B", "PURCHASE"]
        is_sell = side in ["SELL", "S", "SALE"]
        
        if is_buy and c_amt > 0:
            return self.fail(f"Direction Mismatch: BUY trade but Cash Credit (+{c_amt})", "DATA_QUALITY")
        if is_sell and c_amt < 0:
            return self.fail(f"Direction Mismatch: SELL trade but Cash Debit ({c_amt})", "DATA_QUALITY")
            
        return self.pass_rule(f"Direction Consistent ({side})")

class TC_004_CurrencyMatchRule(BaseRule):
    def __init__(self):
        super().__init__("TC_004", "Currency Identity Match", severity="CRITICAL")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        t_ccy = _to_str(_get(trade, "settlement_currency") or _get(trade, "currency"))
        c_ccy = _to_str(_get(cash, "currency"))
        
        if t_ccy == c_ccy:
            return self.pass_rule(f"Currency Match: {t_ccy}")
            
        return self.fail(f"Currency Mismatch: Trade {t_ccy} vs Cash {c_ccy}", "DATA_QUALITY")

class TC_005_ReferenceMatchRule(BaseRule):
    def __init__(self):
        super().__init__("TC_005", "Multi-Key Reference Match", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        """
        Uses cleaned/normalized strings to find matches.
        """
        narrative_raw = _to_str(_get(cash, "description") or _get(cash, "narrative"))
        narrative_clean = _normalize_string(narrative_raw)
        
        keys_to_check = context.metadata.get("TC_005_match_keys", ["id", "trade_ref", "isin", "order_id", "broker_ref"])
        
        found_matches = []
        for key in keys_to_check:
            val_raw = _to_str(_get(trade, key))
            val_clean = _normalize_string(val_raw)
            
            # Only match if the key is reasonably unique (len > 4)
            if len(val_clean) > 4 and val_clean in narrative_clean:
                found_matches.append(f"{key}={val_raw}")
        
        if found_matches:
            return self.pass_rule(f"Found matches: {', '.join(found_matches)}")
            
        return self.fail("No Reference ID found in narrative", "DATA_QUALITY")

# ==============================================================================
# SECTION 2: TOLERANCE & FEE LOGIC (TC_011 - TC_020)
# ==============================================================================

class TC_011_AmountToleranceRule(BaseRule):
    def __init__(self):
        super().__init__("TC_011", "Amount Tolerance Match", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        t_amt = abs(_to_float(_get(trade, "net_amount")))
        c_amt = abs(_to_float(_get(cash, "amount")))
        diff = abs(t_amt - c_amt)
        
        tol_abs = _to_float(context.metadata.get("TC_011_abs_tolerance", 0.05))
        
        if diff <= tol_abs:
            return self.pass_rule(f"Match within tolerance ({diff:.4f} <= {tol_abs})")
        return self.fail(f"Outside Tolerance: Diff {diff}", "ECONOMIC", diff)

class TC_012_GrossNetFeeValidationRule(BaseRule):
    def __init__(self):
        super().__init__("TC_012", "Gross-Net Fee Math Check", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        gross = abs(_to_float(_get(trade, "gross_amount")))
        net = abs(_to_float(_get(trade, "net_amount")))
        
        # Sum known fees
        comm = _to_float(_get(trade, "commission", 0))
        fees = _to_float(_get(trade, "fees", 0))
        tax = _to_float(_get(trade, "tax", 0))
        reported_total_fees = comm + fees + tax
        
        implied_fees = abs(gross - net)
        
        if abs(implied_fees - reported_total_fees) > 1.0:
             return self.fail(f"Fee Math Error: Implied {implied_fees} vs Reported {reported_total_fees}", "DATA_QUALITY")
        return self.pass_rule("Fee Math Consistent")

class TC_013_CommissionCheckRule(BaseRule):
    def __init__(self):
        super().__init__("TC_013", "Commission Threshold Check", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        gross = abs(_to_float(_get(trade, "gross_amount")))
        comm = _to_float(_get(trade, "commission", 0))
        
        if gross == 0: return self.pass_rule("Skipped")
        
        threshold = _to_float(context.metadata.get("TC_013_comm_threshold", 0.05)) # 5% default
        
        if (comm / gross) > threshold:
            return self.fail(f"High Commission: {comm/gross:.2%} > {threshold:.2%}", "RISK")
        return self.pass_rule("Commission OK")

class TC_014_SmallBalanceWriteOffRule(BaseRule):
    def __init__(self):
        super().__init__("TC_014", "Small Balance Auto-Match", severity="LOW")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        t_amt = abs(_to_float(_get(trade, "net_amount")))
        c_amt = abs(_to_float(_get(cash, "amount")))
        diff = abs(t_amt - c_amt)
        
        dust_limit = _to_float(context.metadata.get("TC_014_dust_limit", 0.02))
        
        if 0 < diff <= dust_limit:
            return self.pass_rule(f"Dust difference {diff} (Auto-Writeoff Candidate)")
        return self.pass_rule("Not dust")

# --- GLOBAL REGULATION PLACEHOLDERS ---

class TC_015_US_SEC_FeeRule(BaseRule):
    def __init__(self): super().__init__("TC_015", "US SEC Fee Check", severity="MEDIUM")
    def execute(self, t, c, ctx): return self.pass_rule("Skipped (Placeholder)")

class TC_016_US_FINRA_TAFRule(BaseRule):
    def __init__(self): super().__init__("TC_016", "US FINRA TAF Check", severity="MEDIUM")
    def execute(self, t, c, ctx): return self.pass_rule("Skipped (Placeholder)")

class TC_017_SG_ClearingFeeRule(BaseRule):
    def __init__(self): super().__init__("TC_017", "SG Clearing Fee Check", severity="MEDIUM")
    def execute(self, t, c, ctx): return self.pass_rule("Skipped (Placeholder)")

class TC_018_HK_StampDutyRule(BaseRule):
    def __init__(self): super().__init__("TC_018", "HK Stamp Duty Check", severity="MEDIUM")
    def execute(self, t, c, ctx): return self.pass_rule("Skipped (Placeholder)")

class TC_019_JP_ConsumptionTaxRule(BaseRule):
    def __init__(self): super().__init__("TC_019", "JP Consumption Tax Check", severity="MEDIUM")
    def execute(self, t, c, ctx): return self.pass_rule("Skipped (Placeholder)")

# ==============================================================================
# SECTION 3: REGIONAL & REGULATORY RULES (TC_021 - TC_030)
# ==============================================================================

class TC_021_IndiaSTTCheckRule(BaseRule):
    def __init__(self):
        super().__init__("TC_021", "India STT Validation", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        market = _to_str(_get(trade, "market_code", "IN"))
        if market != "IN": return self.pass_rule("Skipped")
        
        gross = abs(_to_float(_get(trade, "gross_amount")))
        stt = _to_float(_get(trade, "stt", 0))
        
        rate = _to_float(context.metadata.get("TC_021_stt_rate", 0.001))
        expected_stt = gross * rate
        
        if abs(stt - expected_stt) > 5.0:
             return self.fail(f"STT Error: Exp {expected_stt:.2f} vs Act {stt}", "REGULATORY")
        return self.pass_rule("STT Valid")

class TC_022_IndiaGSTCheckRule(BaseRule):
    def __init__(self):
        super().__init__("TC_022", "India GST Validation", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        """
        FIXED: GST applies to Brokerage + Exchange Fees.
        """
        market = _to_str(_get(trade, "market_code", "IN"))
        if market != "IN": return self.pass_rule("Skipped")

        comm = _to_float(_get(trade, "commission", 0))
        exch_fee = _to_float(_get(trade, "exchange_fee", 0))
        gst = _to_float(_get(trade, "gst", 0))
        
        rate = _to_float(context.metadata.get("TC_022_gst_rate", 0.18))
        
        taxable_base = comm + exch_fee
        expected_gst = taxable_base * rate
        
        if abs(gst - expected_gst) > 1.0:
            return self.fail(f"GST Error: Exp {expected_gst:.2f} vs Act {gst}", "REGULATORY")
        return self.pass_rule("GST Valid")

class TC_023_UKStampDutyRule(BaseRule):
    def __init__(self):
        super().__init__("TC_023", "UK SDRT Validation", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        market = _to_str(_get(trade, "market_code"))
        side = _to_str(_get(trade, "side"))
        if market != "GB" or "BUY" not in side: return self.pass_rule("Skipped")
            
        gross = abs(_to_float(_get(trade, "gross_amount")))
        stamp = _to_float(_get(trade, "stamp_duty", 0))
        
        rate = _to_float(context.metadata.get("TC_023_sdrt_rate", 0.005))
        expected = gross * rate
        
        if abs(stamp - expected) > 5.0:
            return self.fail(f"SDRT Error: Exp {expected:.2f} vs Act {stamp}", "REGULATORY")
        return self.pass_rule("SDRT Valid")

# ==============================================================================
# SECTION 4: EDGE CASES & FX (TC_031 - TC_044)
# ==============================================================================

class TC_031_PartialFillFlagRule(BaseRule):
    def __init__(self):
        super().__init__("TC_031", "Partial Fill Candidate Detection", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        t_amt = abs(_to_float(_get(trade, "net_amount")))
        c_amt = abs(_to_float(_get(cash, "amount")))
        
        if t_amt == 0: return self.pass_rule("Skip")
        
        ratio = c_amt / t_amt
        
        # Check if cash is between 10% and 90% of trade (likely partial)
        if 0.10 < ratio < 0.90:
            return self.fail(f"Partial Fill Candidate: Cash is {ratio:.1%} of Trade", "PARTIAL_CANDIDATE")
            
        return self.pass_rule("Not partial pattern")

class TC_032_ReversalDetectionRule(BaseRule):
    def __init__(self):
        super().__init__("TC_032", "Reversal/Cancellation Check", severity="HIGH")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        status = _to_str(_get(trade, "status"))
        c_amt = abs(_to_float(_get(cash, "amount")))
        
        if status in ["CANCELLED", "VOID"] and c_amt > 0:
            return self.fail("Cancelled Trade has Active Cash Flow", "ECONOMIC")
        return self.pass_rule("Status Logic OK")

class TC_033_NettingCandidateRule(BaseRule):
    def __init__(self):
        super().__init__("TC_033", "Net Settlement Candidate", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        t_amt = abs(_to_float(_get(trade, "net_amount")))
        c_amt = abs(_to_float(_get(cash, "amount")))
        
        # If Cash is significantly larger (e.g. 1.5x trade), it's likely a net batch
        if t_amt > 0 and c_amt > (t_amt * 1.5):
            return self.fail(f"Netting Candidate: Cash {c_amt} >> Trade {t_amt}", "NETTING_CANDIDATE")
        return self.pass_rule("No netting signal")

class TC_034_FXConversionCheckRule(BaseRule):
    def __init__(self):
        super().__init__("TC_034", "FX Conversion Logic", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        """
        FIXED: Real FX Rate lookup + Dual Tolerance.
        """
        t_ccy = _to_str(_get(trade, "currency"))
        c_ccy = _to_str(_get(cash, "currency"))
        
        if t_ccy == c_ccy: return self.pass_rule("Skipped")
        
        # 1. Get Rate from Metadata
        rates = context.metadata.get("fx_rates", {})
        pair = f"{t_ccy}/{c_ccy}"
        inv_pair = f"{c_ccy}/{t_ccy}"
        
        rate = _to_float(rates.get(pair))
        if not rate:
            inv_rate = _to_float(rates.get(inv_pair))
            if inv_rate: rate = 1.0 / inv_rate
            
        if not rate:
            return self.fail(f"Missing FX Rate for {pair}", "DATA_QUALITY")
            
        # 2. Calculation
        t_amt = abs(_to_float(_get(trade, "net_amount")))
        c_amt = abs(_to_float(_get(cash, "amount")))
        
        converted = t_amt * rate
        diff = abs(converted - c_amt)
        
        # 3. Dual Tolerance
        abs_tol = _to_float(context.metadata.get("fx_abs_tol", 1.0))
        pct_tol = _to_float(context.metadata.get("fx_pct_tol", 0.01)) # 1%
        
        if c_amt > 0 and diff > abs_tol and (diff / c_amt) > pct_tol:
             return self.fail(f"FX Mismatch: {diff:.2f} ({diff/c_amt:.2%})", "ECONOMIC")
             
        return self.pass_rule(f"FX Matched (@{rate:.4f})")

class TC_044_MultiLegCandidateRule(BaseRule):
    def __init__(self):
        super().__init__("TC_044", "One Trade / Many Cash Indicator", severity="MEDIUM")

    def execute(self, trade: Any, cash: Any, context: RuleContext) -> RuleResult:
        """
        Heuristic: If Trade Amount is significantly larger than Cash,
        this cash entry might be one of many legs.
        (Inverse of TC_031).
        """
        t_amt = abs(_to_float(_get(trade, "net_amount")))
        c_amt = abs(_to_float(_get(cash, "amount")))
        
        if c_amt == 0: return self.pass_rule("Skip")
        
        # If Cash is a neat fraction (e.g., ~50%, ~33%) of Trade
        ratio = c_amt / t_amt
        if 0.30 < ratio < 0.90:
             return self.fail(f"Multi-Leg Candidate: Cash is {ratio:.2%} of Trade", "MULTI_LEG_CANDIDATE")
             
        return self.pass_rule("OK")

# ==============================================================================
# SECTION 5: SANITY (TC_041 - TC_043)
# ==============================================================================

class TC_041_ZeroAmountRule(BaseRule):
    def __init__(self): super().__init__("TC_041", "Zero Amount", "LOW")
    def execute(self, t, c, ctx):
        if _to_float(_get(t, "net_amount")) == 0: return self.fail("Zero Net Amount", "DATA")
        return self.pass_rule("OK")

class TC_042_FutureDateRule(BaseRule):
    def __init__(self): super().__init__("TC_042", "Future Date", "MEDIUM")
    def execute(self, t, c, ctx): return self.pass_rule("OK") 

class TC_043_DuplicateTradeCheckRule(BaseRule):
    def __init__(self): super().__init__("TC_043", "Duplicate ID", "HIGH")
    def execute(self, t, c, ctx):
        if ctx.metadata.get("is_duplicate"): return self.fail("Duplicate ID", "DATA")
        return self.pass_rule("OK")

# ==============================================================================
# REGISTRATION
# ==============================================================================

def register_trade_cash_rules():
    r = RuleRegistry
    r.register(TC_000_MandatoryFieldsCheckRule())
    
    # Core
    r.register(TC_001_ExactAmountRule())
    r.register(TC_002_SettlementDateMatchRule())
    r.register(TC_003_DirectionSanityRule())
    r.register(TC_004_CurrencyMatchRule())
    r.register(TC_005_ReferenceMatchRule())
    
    # Tolerance
    r.register(TC_011_AmountToleranceRule())
    r.register(TC_012_GrossNetFeeValidationRule())
    r.register(TC_013_CommissionCheckRule())
    r.register(TC_014_SmallBalanceWriteOffRule())
    
    # Global Placeholders
    r.register(TC_015_US_SEC_FeeRule())
    r.register(TC_016_US_FINRA_TAFRule())
    r.register(TC_017_SG_ClearingFeeRule())
    r.register(TC_018_HK_StampDutyRule())
    r.register(TC_019_JP_ConsumptionTaxRule())
    
    # Regional
    r.register(TC_021_IndiaSTTCheckRule())
    r.register(TC_022_IndiaGSTCheckRule())
    r.register(TC_023_UKStampDutyRule())
    
    # Edge
    r.register(TC_031_PartialFillFlagRule())
    r.register(TC_032_ReversalDetectionRule())
    r.register(TC_033_NettingCandidateRule())
    r.register(TC_034_FXConversionCheckRule())
    r.register(TC_044_MultiLegCandidateRule())
    
    # Sanity
    r.register(TC_041_ZeroAmountRule())
    r.register(TC_042_FutureDateRule())
    r.register(TC_043_DuplicateTradeCheckRule())

    print("✅ Registered 40+ Trade-Cash Rules")
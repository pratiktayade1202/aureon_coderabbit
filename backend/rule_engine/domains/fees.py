# backend/rule_engine/domains/fees.py

from typing import Any
from ..core.rule import BaseRule, requires
from ..core.result import RuleResult
from ..core.registry import RuleRegistry
from ..core.context import RuleContext

class FeeRule(BaseRule):
    domain = "FEE"

def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None: return default
    if isinstance(obj, dict): return obj.get(attr, default)
    return getattr(obj, attr, default)

def _to_float(value: Any) -> float:
    try: return float(str(value).replace(",", ""))
    except: return 0.0

# --- RULES ---

class FEE_001_BrokerageCheckRule(FeeRule):
    def __init__(self):
        super().__init__("FEE_001", "Brokerage Rate Verification", severity="MEDIUM")
        self.tags = ["cost_control", "audit"]

    # [Improvement 4] Requires Gross AND (Comm OR Fees)
    @requires("gross_amount", "broker_code", any_of=["commission", "fees"])
    def execute(self, trade: Any, invoice: Any, context: RuleContext) -> RuleResult:
        gross = _to_float(_get(trade, "gross_amount"))
        comm = _to_float(_get(trade, "commission") or _get(trade, "fees"))
        broker = _get(trade, "broker_code")
        
        # Dynamic rate lookup
        rate_key = f"rate_card_{broker}"
        agreed_rate = float(context.metadata.get(rate_key, 0.0005)) 
        
        expected_comm = gross * agreed_rate
        diff = abs(comm - expected_comm)
        
        # [Improvement 3] Asset-Aware Tolerance (Equities vs Bonds have diff tolerances)
        asset_class = _get(trade, "asset_class", "EQUITY")
        abs_tol, pct_tol = self.resolve_tol(context, "brokerage", 1.0, 0.05, asset_class=asset_class)
        
        if diff > abs_tol and (diff / expected_comm) > pct_tol:
            return self.fail_with(
                "Brokerage Overcharge", "ECONOMIC",
                actual=comm, expected=expected_comm, 
                diff=diff, rate_used=agreed_rate,
                amount_diff=diff # [Improvement 12] Triggers Autotune
            )
            
        return self.pass_rule("Commission Valid")

class FEE_011_SmartMgmtFeeRule(FeeRule):
    def __init__(self):
        super().__init__("FEE_011", "Management Fee Accrual", severity="HIGH")

    @requires("aum", "daily_accrual")
    def execute(self, record: Any, comparison: Any, context: RuleContext) -> RuleResult:
        aum = _to_float(_get(record, "aum"))
        accrual = _to_float(_get(record, "daily_accrual"))
        
        z = self.skip_if_zero(aum, "Zero AUM")
        if z: return z
        
        rate = float(context.metadata.get("mgmt_fee_rate", 0.02))
        expected = (aum * rate) / 365.0
        
        diff = abs(accrual - expected)
        
        # [Improvement 7] Time Sensitivity Check
        # If data is stale, skip rule
        if context.metadata.get("is_data_stale"):
            return self.skip("Skipped due to stale data")

        if diff > 1000:
            return self.fail_with(
                "Significant Fee Leakage", "VALUATION",
                expected=expected, actual=accrual, amount_diff=diff
            )
        elif diff > 5.0:
            return self.warn(
                f"Minor Accrual Drift: {diff:.2f}",
                details={"expected": expected, "actual": accrual}
            )
            
        return self.pass_rule("Accrual Correct")

# --- REGISTRATION ---
def register_fee_rules():
    r = RuleRegistry
    r.register(FEE_001_BrokerageCheckRule())
    r.register(FEE_011_SmartMgmtFeeRule())
    print("✅ Registered Intelligent Fee Rules")
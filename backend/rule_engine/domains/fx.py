# backend/rule_engine/domains/fx.py

from typing import Any
from ..core.rule import BaseRule, requires
from ..core.result import RuleResult
from ..core.registry import RuleRegistry
from ..core.context import RuleContext

class FXRule(BaseRule):
    domain = "FX"
    
    def _normalize_rate(self, rate: float) -> float:
        if rate == 0: return 0.0
        # Simple heuristic: standardize to 0.0 - 100.0 range if possible
        return rate

    def _get_market_rate(self, pair: str, context: RuleContext) -> float:
        rates = context.metadata.get("fx_rates", {})
        return float(rates.get(pair, 0.0))

def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None: return default
    if isinstance(obj, dict): return obj.get(attr, default)
    return getattr(obj, attr, default)

def _to_float(value: Any) -> float:
    try: return float(str(value).replace(",", ""))
    except: return 0.0

# --- RULES ---

class FX_001_SmartRateToleranceRule(FXRule):
    def __init__(self):
        super().__init__("FX_001", "Smart FX Rate Validation", severity="HIGH")
        self.tags = ["market_data", "valuation"]

    @requires("fx_rate", "pair")
    def execute(self, record: Any, market_data: Any, context: RuleContext) -> RuleResult:
        deal_rate = self._normalize_rate(_to_float(_get(record, "fx_rate")))
        pair = _get(record, "pair")
        
        # [Improvement 5] Zero check
        z_check = self.skip_if_zero(deal_rate, "Zero Deal Rate")
        if z_check: return z_check

        mkt_rate = _to_float(_get(market_data, "mid_rate"))
        if mkt_rate == 0:
            mkt_rate = self._get_market_rate(pair, context)
            
        if mkt_rate == 0:
            return self.skip(f"No market rate found for {pair}")

        # [Improvement 3] Asset-Aware Tolerance (e.g. Swaps vs Spot)
        asset_type = _get(record, "instrument_type", "SPOT")
        abs_tol, pct_tol = self.resolve_tol(context, "fx_rate", 0.0001, 0.01, asset_class=asset_type)

        diff_pct = abs(deal_rate - mkt_rate) / mkt_rate
        
        if diff_pct > pct_tol:
            # Check Inverse
            inverse_deal = 1.0 / deal_rate
            if abs(inverse_deal - mkt_rate) / mkt_rate < pct_tol:
                return self.fail_with(
                    "Inverse Rate Detected", "DATA_QUALITY",
                    deal_rate=deal_rate, market_rate=mkt_rate,
                    hint=f"Rate seems inverted. Did you mean {inverse_deal:.4f}?"
                )
            
            return self.fail_with(
                "Off-Market Rate", "VALUATION",
                deal_rate=deal_rate, market_rate=mkt_rate, variance_pct=diff_pct,
                amount_diff=diff_pct # Triggers severity tuning
            )

        return self.pass_rule(f"Rate valid within {diff_pct:.4%}")

class FX_005_SpreadSanityRule(FXRule):
    def __init__(self):
        super().__init__("FX_005", "High Spread Warning", severity="LOW")
        self.depends_on = ["FX_001"] # [Improvement 1] Orchestrator respects this

    @requires("fx_rate")
    def execute(self, record: Any, market_data: Any, context: RuleContext) -> RuleResult:
        deal = _to_float(_get(record, "fx_rate"))
        mid = _to_float(_get(market_data, "mid_rate")) or self._get_market_rate(_get(record, "pair"), context)
        
        if mid == 0: return self.skip("No market data")
        
        spread = abs(deal - mid) / mid
        
        if spread > 0.02:
            return self.warn(
                f"High Execution Spread: {spread:.2%}", 
                details={"deal": deal, "mid": mid}
            )
            
        return self.pass_rule("Spread reasonable")

# --- REGISTRATION ---
def register_fx_rules():
    r = RuleRegistry
    r.register(FX_001_SmartRateToleranceRule())
    r.register(FX_005_SpreadSanityRule())
    print("✅ Registered FX Rules (Smart)")
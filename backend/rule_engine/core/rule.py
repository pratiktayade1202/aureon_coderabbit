# backend/rule_engine/core/rule.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Union
import json
from .result import RuleResult

class BaseRule(ABC):
    """
    Enterprise-Grade Base Rule Class.
    Features: Structured JSON Logging, Asset-Class Overrides, DAG Helpers, Dynamic Severity.
    """
    
    # Metadata Defaults
    domain: str = "GENERIC"
    category: str = "General"
    tags: List[str] = []
    depends_on: List[str] = []  # Dependency Rule IDs

    def __init__(self, rule_id: str, description: str, severity: str = "MEDIUM"):
        self.rule_id = rule_id
        self.description = description
        self.severity = severity

    @abstractmethod
    def execute(self, record: Any, comparison_data: Any, context: Dict = None) -> RuleResult:
        pass

    # --- DAG / Execution Logic [Improvement 1] ---
    
    def should_run(self, previous_results: Dict[str, RuleResult]) -> bool:
        """
        Checks if dependencies are met. 
        Orchestrator calls this before .execute().
        """
        if not self.depends_on:
            return True
        
        for parent_id in self.depends_on:
            parent_result = previous_results.get(parent_id)
            # If parent didn't run or failed/warned, we skip
            if not parent_result or not parent_result.passed:
                return False
        return True

    # --- Standardized Output Helpers ---

    def _result(self, passed: bool, message: str, score: float, 
                severity: str, break_type: str = None, 
                details: Dict = None, json_details: Dict = None) -> RuleResult:
        
        # [Improvement 2] Auto-inject metadata into result
        meta = {
            "domain": self.domain,
            "category": self.category,
            "tags": self.tags,
            "prior_severity": self.severity
        }
        
        final_details = details or {}
        final_details.update(meta)
        
        # [Improvement 6] Machine-parsable payload
        if json_details:
            final_details["raw_context"] = json_details

        return RuleResult(
            rule_id=self.rule_id,
            passed=passed,
            score=score,
            severity=severity,
            break_type=break_type,
            message=message,
            details=final_details
        )

    def pass_rule(self, message: str = "Match found", details: Dict = None) -> RuleResult:
        return self._result(True, message, 1.0, "INFO", details=details)

    def fail(self, message: str, break_type: str, amount_diff: float = 0.0, severity: str = None, hint: str = None, context_values: Dict = None) -> RuleResult:
        """Standard failure return."""
        sev = severity or self.severity
        
        # [Improvement 12] Severity Autotuning check
        if amount_diff > 0:
            sev = self._autotune_severity(amount_diff, sev)

        details = {"hint": hint} if hint else {}
        if amount_diff: details["amount_diff"] = amount_diff

        return self._result(False, message, 0.0, sev, break_type, details, context_values)

    def warn(self, message: str, break_type: str = "WARNING", details: Dict = None) -> RuleResult:
        """Soft Fail."""
        return self._result(False, message, 0.5, "LOW", break_type, details)

    def skip(self, message: str) -> RuleResult:
        """Explicit Skip."""
        return self._result(True, message, -1.0, "INFO", "SKIPPED")

    def fail_with(self, message: str, code: str, **context_values) -> RuleResult:
        """
        [Improvement 6] Structured Error Envelope with JSON payload.
        """
        diff = float(context_values.get("amount_diff", 0.0))
        
        # Human readable message
        context_str = " | ".join([f"{k}={v}" for k, v in context_values.items() if k != "json_details"])
        full_msg = f"{message} [{context_str}]"
        
        return self.fail(
            message=full_msg,
            break_type=code,
            amount_diff=diff,
            context_values=context_values # Passes raw dict for ML
        )

    # --- Smart Helpers ---

    def skip_if_zero(self, value: Any, field_name: str) -> Optional[RuleResult]:
        """[Improvement 5] Cleaner Zero Check."""
        try:
            if float(value) == 0:
                return self.skip(f"Skipped: {field_name} is zero")
        except:
            pass
        return None

    def _autotune_severity(self, amount_diff: float, current_sev: str) -> str:
        # Hardcoded safety net, usually context-driven
        if abs(amount_diff) >= 100_000.0:
            return "CRITICAL"
        return current_sev

    def resolve_tol(self, context, key: str, default_abs: float = 1.0, default_pct: float = 0.001, asset_class: str = None):
        """
        [Improvement 3] Asset-Class Aware Tolerance Resolver.
        Order: Asset-Specific -> Global Tenant -> Default
        """
        if not context: return default_abs, default_pct
        
        meta = context.metadata
        
        # 1. Check Asset Class Override (e.g. "fx_rate_equity_abs")
        if asset_class:
            ac_key = f"{key}_{asset_class.lower()}"
            if f"{ac_key}_abs" in meta:
                return float(meta[f"{ac_key}_abs"]), float(meta.get(f"{ac_key}_pct", default_pct))

        # 2. Check Global Tenant Config
        abs_tol = float(meta.get(f"{key}_abs", default_abs))
        pct_tol = float(meta.get(f"{key}_pct", default_pct))
        
        return abs_tol, pct_tol

# --- Enhanced Decorators [Improvement 4] ---

def requires(*fields, any_of: List[str] = None):
    """
    Checks mandatory fields. 
    Supports OR logic via 'any_of'=[list_of_fields].
    """
    def decorator(func):
        def wrapper(self, record, comparison, context):
            # Check mandatory AND fields
            missing = []
            getter = lambda o, f: o.get(f) if isinstance(o, dict) else getattr(o, f, None)
            
            for f in fields:
                val = getter(record, f)
                if val is None or val == "":
                    missing.append(f)
            
            if missing:
                return self.skip(f"Missing required input fields: {', '.join(missing)}")
                
            # Check optional OR fields (at least one must exist)
            if any_of:
                has_any = any(getter(record, f) is not None for f in any_of)
                if not has_any:
                    return self.skip(f"Missing at least one of: {', '.join(any_of)}")

            return func(self, record, comparison, context)
        return wrapper
    return decorator
# backend/rule_engine/core/context.py

from typing import Dict, Any, List
import logging

class RuleContext:
    """
    Runtime context for rule execution.
    Holds metadata (tolerances, flags) and global settings.
    """
    def __init__(self, metadata: Dict[str, Any] = None, custom_settings: Dict[str, Any] = None):
        self.metadata = metadata or {}
        self.custom_settings = custom_settings or {}
        self.validate_schema()

    def get_tolerance(self, key: str, default: float = 0.0) -> float:
        """Safe accessor for float tolerances."""
        try:
            return float(self.metadata.get(key, default))
        except:
            return default

    def validate_schema(self):
        """
        [Structural Fix #2]
        Validates that critical metadata exists and has correct types.
        """
        required_floats = [
            "fx_rate_tolerance", "valuation_tolerance_pct", 
            "FX_rate_tolerance", "mgmt_fee_rate"
        ]
        required_dicts = ["fx_rates"]
        
        errors = []
        
        # 1. Type Check Floats
        for key in required_floats:
            if key in self.metadata:
                try:
                    float(self.metadata[key])
                except ValueError:
                    errors.append(f"Metadata key '{key}' must be a float/number")

        # 2. Type Check Dicts
        for key in required_dicts:
            if key in self.metadata and not isinstance(self.metadata[key], dict):
                errors.append(f"Metadata key '{key}' must be a dictionary")

        if errors:
            logging.warning(f"Context Validation Warnings: {'; '.join(errors)}")
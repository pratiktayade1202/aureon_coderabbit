# backend/rule_engine/core/registry.py
from typing import List, Optional, Any

# Attempt to import BaseRule, fallback to Any if not yet defined to prevent crash
try:
    from .rule import BaseRule
except ImportError:
    BaseRule = Any

class RuleRegistry:
    """
    Static registry to hold all instantiated rules.
    Acts as the Single Source of Truth for the Engine.
    """
    # We use a List as requested, which preserves insertion order
    _rules: List[BaseRule] = []

    @classmethod
    def register(cls, rule: BaseRule):
        """
        Registers a rule instance. 
        Idempotent: Prevents duplicate registration of the same Rule ID.
        """
        # Simple deduplication by ID
        if not any(r.rule_id == rule.rule_id for r in cls._rules):
            cls._rules.append(rule)
            # print(f"✅ Rule Registered: {rule.rule_id}") # Uncomment for debug
        else:
            # Logic for updates could go here, but we skip to keep it safe
            pass

    @classmethod
    def get_all(cls) -> List[BaseRule]:
        """Returns all registered rules."""
        return cls._rules

    @classmethod
    def get_all_rules(cls) -> List[BaseRule]:
        """
        Alias for compatibility with Orchestrator.
        """
        return cls._rules

    @classmethod
    def get_rule(cls, rule_id: str) -> Optional[BaseRule]:
        """
        Helper to find a specific rule by ID.
        """
        return next((r for r in cls._rules if r.rule_id == rule_id), None)

    @classmethod
    def reset(cls):
        """
        Clears the registry. 
        CRITICAL: Used by main.py during 'System Reset'.
        """
        cls._rules = []
        print("🧹 Rule Registry Cleared.")
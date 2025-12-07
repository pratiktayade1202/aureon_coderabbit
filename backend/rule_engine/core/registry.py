# backend/rule_engine/core/registry.py

from typing import Dict, List
from .rule import BaseRule

class RuleRegistry:
    _registry: Dict[str, BaseRule] = {}

    @classmethod
    def register(cls, rule_instance: BaseRule):
        """Registers a rule instance."""
        if rule_instance.rule_id in cls._registry:
            # Overwrite is allowed for updates, but warn
            pass 
        cls._registry[rule_instance.rule_id] = rule_instance

    @classmethod
    def clear(cls):
        """clears the registry to prevent cross-request pollution."""
        cls._registry = {}

    @classmethod
    def get_all_rules(cls) -> List[BaseRule]:
        return list(cls._registry.values())